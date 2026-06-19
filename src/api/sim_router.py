"""시뮬레이션 세션 API — 스텝별 간트 시각화용."""
from __future__ import annotations

import copy
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.simulation.domain.problem import Move, ProblemInstance
from src.simulation.domain.state import SimState
from src.simulation.kernel.simulator import Simulator
from src.utils.json_io import load_problem

router = APIRouter(prefix="/api/sim", tags=["simulation"])

_sessions: dict[str, dict] = {}


class StartRequest(BaseModel):
    dataset: str


class MoveRequest(BaseModel):
    model: str
    from_index: int
    to_index: int


def _parse_timekey(tk: str) -> datetime:
    return datetime.strptime(str(tk)[:12].ljust(12, "0"), "%Y%m%d%H%M")


def _stable_assign(
    eqp_ids: list[str],
    assignment: dict[int, int],
    prev: dict[str, int],
) -> dict[str, int]:
    """eqp_id → task_index 매핑. 이전 시간의 배치를 최대한 유지."""
    result: dict[str, int] = {}
    remaining = {ti: cnt for ti, cnt in assignment.items() if cnt > 0}
    free_ids: list[str] = []

    for eid in eqp_ids:
        prev_ti = prev.get(eid)
        if prev_ti is not None and remaining.get(prev_ti, 0) > 0:
            result[eid] = prev_ti
            remaining[prev_ti] -= 1
        else:
            free_ids.append(eid)

    fi = 0
    for ti in sorted(remaining.keys()):
        for _ in range(remaining[ti]):
            if fi < len(free_ids):
                result[free_ids[fi]] = ti
                fi += 1

    return result


def _build_gantt(problem: ProblemInstance, snapshots: list[SimState]) -> list[dict]:
    """스냅샷 이력으로 간트 세그먼트 생성. snapshots[h] = hour h 시작 직전 상태."""
    if len(snapshots) < 2:
        return []

    base_dt = _parse_timekey(problem.rule_timekey)
    eqp_ids_by_model = {
        model: [f"{model}_{i + 1:02d}" for i in range(qty)]
        for model, qty in sorted(problem.eqp_qty.items())
    }

    # 시간별 id_map: model -> {eqp_id -> task_index}
    id_maps: list[dict[str, dict[str, int]]] = []
    for h in range(len(snapshots) - 1):
        state = snapshots[h]
        prev_map = id_maps[-1] if id_maps else {}
        hour_map: dict[str, dict[str, int]] = {}
        for model, eqp_ids in eqp_ids_by_model.items():
            assignment = {
                ti: cnt
                for (m, ti), cnt in state.assign.items()
                if m == model and cnt > 0
            }
            hour_map[model] = _stable_assign(eqp_ids, assignment, prev_map.get(model, {}))
        id_maps.append(hour_map)

    segments: list[dict] = []
    for model, eqp_ids in eqp_ids_by_model.items():
        for eqp_id in eqp_ids:
            h = 0
            while h < len(id_maps):
                ti = id_maps[h].get(model, {}).get(eqp_id)
                if ti is None:
                    h += 1
                    continue

                state_h = snapshots[h]
                is_switching = state_h.switching.get((model, ti), 0) > 0

                # 같은 task + 같은 switching 상태가 연속되는 구간 탐색
                end_h = h + 1
                while end_h < len(id_maps):
                    next_ti = id_maps[end_h].get(model, {}).get(eqp_id)
                    next_sw = snapshots[end_h].switching.get((model, ti), 0) > 0 if next_ti == ti else False
                    if next_ti != ti or next_sw != is_switching:
                        break
                    end_h += 1

                task = problem.tasks[ti]
                start_dt = base_dt + timedelta(hours=h)
                end_dt = base_dt + timedelta(hours=end_h)

                # 이 구간의 생산량(단위 기여분 추정)
                total_qty = 0
                if not is_switching:
                    for hh in range(h, end_h):
                        prod_delta = snapshots[hh + 1].produced[ti] - snapshots[hh].produced[ti]
                        uph = problem.uph_of(model, ti) or 0.0
                        total_cap = sum(
                            max(0, snapshots[hh].assign.get((m2, ti), 0)
                                - snapshots[hh].switching.get((m2, ti), 0))
                            * (problem.uph_of(m2, ti) or 0.0)
                            for m2 in problem.models()
                        )
                        if total_cap > 0:
                            total_qty += int(prod_delta * uph / total_cap)

                kind = "CONV" if is_switching else "RUN"
                seg: dict = {
                    "kind": kind,
                    "eqp_id": eqp_id,
                    "model": model,
                    "plan_prod_key": task.plan_prod_key,
                    "oper_id": task.oper_id,
                    "batch_id": task.batch_id,
                    "task": f"{task.plan_prod_key}/{task.oper_id}",
                    "start": start_dt.isoformat(),
                    "end": end_dt.isoformat(),
                    "qty": total_qty,
                }
                if kind == "CONV":
                    seg.update({
                        "from_batch": "",
                        "to_batch": task.batch_id,
                        "from_task": "",
                        "to_task": f"{task.plan_prod_key}/{task.oper_id}",
                    })
                segments.append(seg)
                h = end_h

    return segments


def _session_response(session: dict) -> dict:
    problem: ProblemInstance = session["problem"]
    state: SimState = session["state"]
    sim: Simulator = session["sim"]
    snapshots: list[SimState] = session["snapshots"]

    valid_moves = [
        {
            "model": mv.model,
            "from_index": mv.from_index,
            "to_index": mv.to_index,
            "from_task": f"{problem.tasks[mv.from_index].plan_prod_key}/{problem.tasks[mv.from_index].oper_id}",
            "to_task": f"{problem.tasks[mv.to_index].plan_prod_key}/{problem.tasks[mv.to_index].oper_id}",
        }
        for mv in sim.valid_moves(state)
    ]

    wip_list = [
        {
            "task_index": i,
            "task": f"{t.plan_prod_key}/{t.oper_id}",
            "plan_prod_key": t.plan_prod_key,
            "oper_id": t.oper_id,
            "wip": state.wip.get(i, 0),
            "produced": state.produced.get(i, 0),
            "plan": t.plan_qty,
            "rate": round(min(state.produced.get(i, 0) / t.plan_qty, 1.0), 4) if t.plan_qty else 1.0,
        }
        for i, t in enumerate(problem.tasks)
    ]

    assign_list = [
        {
            "model": model,
            "task_index": ti,
            "task": f"{problem.tasks[ti].plan_prod_key}/{problem.tasks[ti].oper_id}",
            "count": cnt,
            "switching": state.switching.get((model, ti), 0),
        }
        for (model, ti), cnt in sorted(state.assign.items())
        if cnt > 0
    ]

    return {
        "hour": state.hour,
        "total_hours": problem.horizon_hours,
        "is_done": sim.is_done(state),
        "gantt": _build_gantt(problem, snapshots + [state]),
        "wip": wip_list,
        "assign": assign_list,
        "valid_moves": valid_moves,
    }


@router.post("/start")
def sim_start(req: StartRequest):
    from src.api.service import list_dataset_paths
    paths = list_dataset_paths()
    if req.dataset not in paths:
        raise HTTPException(status_code=404, detail=f"dataset not found: {req.dataset}")

    problem = load_problem(paths[req.dataset])
    sim = Simulator(problem)
    state = sim.reset()

    sid = str(uuid.uuid4())
    _sessions[sid] = {
        "problem": problem,
        "sim": sim,
        "state": state,
        "snapshots": [copy.deepcopy(state)],
    }

    resp = _session_response(_sessions[sid])
    resp["session_id"] = sid
    return resp


@router.get("/{sid}")
def sim_get(sid: str):
    session = _sessions.get(sid)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")
    return _session_response(session)


@router.post("/{sid}/advance")
def sim_advance(sid: str):
    session = _sessions.get(sid)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")

    sim: Simulator = session["sim"]
    state: SimState = session["state"]
    if sim.is_done(state):
        raise HTTPException(status_code=400, detail="simulation already done")

    sim.advance_hour(state)
    session["snapshots"].append(copy.deepcopy(state))
    return _session_response(session)


@router.post("/{sid}/move")
def sim_move(sid: str, req: MoveRequest):
    session = _sessions.get(sid)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")

    problem: ProblemInstance = session["problem"]
    sim: Simulator = session["sim"]
    state: SimState = session["state"]

    n = len(problem.tasks)
    if req.from_index >= n or req.to_index >= n:
        raise HTTPException(status_code=400, detail="invalid task index")

    mv = Move(req.model, req.from_index, req.to_index)
    if mv not in set(sim.valid_moves(state)):
        raise HTTPException(status_code=400, detail="invalid move")

    sim.apply_move(state, mv)
    return _session_response(session)


@router.post("/{sid}/reset")
def sim_reset(sid: str):
    session = _sessions.get(sid)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")

    sim: Simulator = session["sim"]
    state = sim.reset()
    session["state"] = state
    session["snapshots"] = [copy.deepcopy(state)]
    return _session_response(session)


@router.delete("/{sid}")
def sim_delete(sid: str):
    _sessions.pop(sid, None)
    return {"ok": True}
