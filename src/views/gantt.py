"""간트차트 projection."""
from __future__ import annotations

from datetime import datetime, timedelta

from src.utils.eqp_units import initial_positions, track_units, virtual_roster
from src.utils.rows import event_tm_for_hour, merge_assign_rows, _split_hourly_produce
from src.simulation.domain.problem import ProblemInstance


def _parse_tm(s: str) -> datetime:
    return datetime.strptime(str(s)[:14].ljust(14, "0"), "%Y%m%d%H%M%S")


def _iso(s: str) -> str:
    return _parse_tm(s).isoformat()


def _task_label(t) -> str:
    return f"{t.plan_prod_key}/{t.oper_id}"


def _conv_eqp_hours(problem: ProblemInstance, conversions: list[dict]) -> set[tuple[str, int]]:
    """전환 중인 (eqp_id, hour) — switch_time_hours 구간."""
    blocked: set[tuple[str, int]] = set()
    switch_h = max(1, problem.switch_time_hours)
    for c in conversions:
        for h in range(c["hour"], c["hour"] + switch_h):
            blocked.add((c["eqp_id"], h))
    return blocked


def _hourly_unit_positions(
    problem: ProblemInstance,
    hourly_stats: list[dict],
    trace: list,
) -> list[dict[tuple[str, int], list[str]]]:
    hourly_positions = None
    if trace:
        hourly_positions, _ = track_units(problem, trace)
    out: list[dict[tuple[str, int], list[str]]] = []
    for k, stat in enumerate(hourly_stats):
        if hourly_positions is not None and k < len(hourly_positions):
            out.append(hourly_positions[k])
            continue
        snapshot = stat["assign_snapshot"]
        positions: dict[tuple[str, int], list[str]] = {}
        model_unit_offset: dict[str, int] = {}
        for model in problem.models():
            for ti in range(len(problem.tasks)):
                active = snapshot.get((model, ti), 0)
                if active <= 0:
                    continue
                offset = model_unit_offset.get(model, 0)
                positions[(model, ti)] = [
                    f"{model}-{offset + u + 1:03d}" for u in range(active)
                ]
                model_unit_offset[model] = offset + active
        out.append(positions)
    return out


def _idle_segments(
    problem: ProblemInstance,
    hourly_stats: list[dict],
    trace: list,
) -> list[dict]:
    """할당됐으나 생산 없음(재공=0 등) · 미할당 구간."""
    if not hourly_stats:
        return []
    _, conversions = track_units(problem, trace) if trace else ([], [])
    conv_hours = _conv_eqp_hours(problem, conversions)
    positions_by_hour = _hourly_unit_positions(problem, hourly_stats, trace)
    roster = problem.equipments or virtual_roster(problem)
    roster_by_model: dict[str, list[str]] = {}
    for e in roster:
        roster_by_model.setdefault(e.eqp_model, []).append(e.eqp_id)
    for model in roster_by_model:
        roster_by_model[model].sort()

    segments: list[dict] = []
    for k, stat in enumerate(hourly_stats):
        hour = stat["hour"]
        wip = stat.get("wip_snapshot", {})
        start_tm = event_tm_for_hour(problem.rule_timekey, hour)
        end_tm = event_tm_for_hour(problem.rule_timekey, hour + 1)
        positions = positions_by_hour[k] if k < len(positions_by_hour) else {}
        assigned_eqps: set[str] = set()

        for (model, ti), unit_ids in sorted(positions.items()):
            task = problem.tasks[ti]
            active = len(unit_ids)
            model_total = _split_hourly_produce(problem, stat, ti).get(model, 0)
            per_unit = model_total // active if active else 0
            remainder = model_total % active if active else 0
            for u, eqp_id in enumerate(sorted(unit_ids)):
                assigned_eqps.add(eqp_id)
                qty = per_unit + (1 if u < remainder else 0)
                if qty > 0 or (eqp_id, hour) in conv_hours:
                    continue
                wip_qty = int(wip.get(ti, 0))
                reason = "WIP_ZERO" if wip_qty == 0 else "NO_OUTPUT"
                segments.append({
                    "kind": "IDLE",
                    "eqp_id": eqp_id,
                    "model": model,
                    "plan_prod_key": task.plan_prod_key,
                    "oper_id": task.oper_id,
                    "batch_id": task.batch_id,
                    "task": _task_label(task),
                    "start": _iso(start_tm),
                    "end": _iso(end_tm),
                    "qty": 0,
                    "allocated": True,
                    "wip": wip_qty,
                    "idle_reason": reason,
                })

        for model, eqp_ids in roster_by_model.items():
            for eqp_id in eqp_ids:
                if eqp_id in assigned_eqps or (eqp_id, hour) in conv_hours:
                    continue
                segments.append({
                    "kind": "UNALLOC",
                    "eqp_id": eqp_id,
                    "model": model,
                    "plan_prod_key": "",
                    "oper_id": "",
                    "batch_id": "",
                    "task": "미할당",
                    "start": _iso(start_tm),
                    "end": _iso(end_tm),
                    "qty": 0,
                    "allocated": False,
                    "wip": 0,
                    "idle_reason": "UNALLOCATED",
                })
    return segments


def gantt_rows(
    problem: ProblemInstance,
    assign_rows: list[dict],
    trace: list,
    hourly_stats: list[dict] | None = None,
) -> list[dict]:
    task_by_key = {(t.plan_prod_key, t.oper_id): t for t in problem.tasks}
    segments: list[dict] = []
    for r in merge_assign_rows(assign_rows):
        t = task_by_key.get((r["PLAN_PROD_KEY"], r.get("OPER_ID", "")))
        segments.append({
            "kind": "RUN",
            "eqp_id": r["EQP_ID"],
            "model": r["EQP_MODEL_CD"],
            "plan_prod_key": r["PLAN_PROD_KEY"],
            "oper_id": r.get("OPER_ID", ""),
            "batch_id": t.batch_id if t else "",
            "task": f"{r['PLAN_PROD_KEY']}/{r.get('OPER_ID', '')}",
            "start": _iso(r["START_TIME"]),
            "end": _iso(r["END_TIME"]),
            "qty": r["PRODUCE_QTY"],
            "allocated": True,
        })
    _, conversions = track_units(problem, trace) if trace else ([], [])
    for c in conversions:
        start_tm = event_tm_for_hour(problem.rule_timekey, c["hour"])
        end = _parse_tm(start_tm) + timedelta(hours=problem.switch_time_hours)
        from_t = problem.tasks[c["from_index"]]
        to_t = problem.tasks[c["to_index"]]
        segments.append({
            "kind": "CONV",
            "eqp_id": c["eqp_id"],
            "model": c["model"],
            "plan_prod_key": to_t.plan_prod_key,
            "oper_id": to_t.oper_id,
            "batch_id": to_t.batch_id,
            "task": f"{from_t.batch_id}→{to_t.batch_id}",
            "from_batch": from_t.batch_id,
            "to_batch": to_t.batch_id,
            "from_task": _task_label(from_t),
            "to_task": _task_label(to_t),
            "start": _iso(start_tm),
            "end": end.isoformat(),
            "qty": 0,
            "allocated": True,
        })
    if hourly_stats:
        segments.extend(_idle_segments(problem, hourly_stats, trace))
    return segments


def gantt_wip_summary(problem: ProblemInstance) -> list[dict]:
    """공정별 초기 재공·계획 요약."""
    return [
        {
            "task": _task_label(t),
            "batch_id": t.batch_id,
            "plan_prod_key": t.plan_prod_key,
            "oper_id": t.oper_id,
            "init_wip": int(t.init_wip),
            "plan_qty": int(t.plan_qty),
        }
        for t in problem.tasks
    ]


def gantt_allocation_summary(problem: ProblemInstance) -> list[dict]:
    """초기 장비 할당(호기·공정) 요약."""
    init_pos = initial_positions(problem)
    rows: list[dict] = []
    for (model, ti), eqp_ids in sorted(init_pos.items(), key=lambda x: (x[0][1], x[0][0])):
        t = problem.tasks[ti]
        for eqp_id in sorted(eqp_ids):
            rows.append({
                "eqp_id": eqp_id,
                "model": model,
                "task": _task_label(t),
                "batch_id": t.batch_id,
                "allocated": True,
            })
    roster = problem.equipments or virtual_roster(problem)
    assigned = {r["eqp_id"] for r in rows}
    for e in sorted(roster, key=lambda x: x.eqp_id):
        if e.eqp_id in assigned:
            continue
        rows.append({
            "eqp_id": e.eqp_id,
            "model": e.eqp_model,
            "task": "",
            "batch_id": e.batch_id,
            "allocated": False,
        })
    return rows
