"""장비 전환 스케줄링 도메인 모델 + 1시간 step 시뮬레이터.

gym/sb3/DB에 의존하지 않는 순수 코어.
"""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple


class Move(NamedTuple):
    model: str
    from_index: int
    to_index: int


@dataclass(frozen=True)
class Task:
    plan_prod_key: str
    oper_id: str
    oper_seq: int
    batch_id: str
    plan_qty: int
    init_wip: int


@dataclass
class ProblemInstance:
    rule_timekey: str
    horizon_hours: int
    switch_time_hours: int
    tasks: list[Task]
    _uph: dict[tuple[str, int], float]          # (model, task_index) -> uph
    eqp_qty: dict[str, int]                      # model -> total units
    init_assign: dict[tuple[str, int], int]      # (model, task_index) -> count
    tool_qty: dict[tuple[str, str], int]         # (batch_id, model) -> tools
    conv_groups: dict[str, list[str]]            # group_id -> [batch_id, ...]
    ground_truth: dict = field(default_factory=dict)

    def uph_of(self, model: str, task_index: int) -> float | None:
        return self._uph.get((model, task_index))

    def batch_of(self, task_index: int) -> str:
        return self.tasks[task_index].batch_id

    def conv_group_of(self, batch_id: str) -> str | None:
        for gid, batches in self.conv_groups.items():
            if batch_id in batches:
                return gid
        return None

    def can_convert(self, from_batch: str, to_batch: str) -> bool:
        """conversion 그룹이 같아야 batch 전환 가능."""
        g = self.conv_group_of(from_batch)
        return g is not None and g == self.conv_group_of(to_batch)

    def next_task_index(self, task_index: int) -> int | None:
        """같은 plan_prod_key의 oper_seq+1 태스크 인덱스(없으면 None)."""
        t = self.tasks[task_index]
        for i, o in enumerate(self.tasks):
            if o.plan_prod_key == t.plan_prod_key and o.oper_seq == t.oper_seq + 1:
                return i
        return None

    def models(self) -> list[str]:
        return sorted(self.eqp_qty)


@dataclass
class SimState:
    hour: int
    produced: dict[int, int]                  # task_index -> 누적 생산
    wip: dict[int, int]                        # task_index -> 현재 가용 유입재공
    assign: dict[tuple[str, int], int]         # (model, task_index) -> 배치 대수
    idle: dict[tuple[str, int], int]           # (model, task_index) -> 전환 Idle 잔여대수
    tool_used: dict[tuple[str, str], int]      # (batch_id, model) -> 사용중 tool


class Simulator:
    """1시간 단위로 전이하는 결정론적 시뮬레이터."""

    def __init__(self, problem: ProblemInstance):
        self.p = problem

    def reset(self) -> SimState:
        p = self.p
        wip = {i: t.init_wip for i, t in enumerate(p.tasks)}
        produced = {i: 0 for i in range(len(p.tasks))}
        assign = dict(p.init_assign)
        idle: dict[tuple[str, int], int] = {}
        tool_used: dict[tuple[str, str], int] = {}
        for (model, ti), cnt in assign.items():
            key = (p.batch_of(ti), model)
            tool_used[key] = tool_used.get(key, 0) + cnt
        return SimState(0, produced, wip, assign, idle, tool_used)

    def advance_hour(self, s: SimState) -> None:
        """배치된(Idle 아닌) 장비로 1시간 생산 후 WIP를 다음 공정으로 흘린다."""
        p = self.p
        inflow: dict[int, int] = {}
        for ti in range(len(p.tasks)):
            capacity = 0.0
            for model in p.models():
                active = s.assign.get((model, ti), 0) - s.idle.get((model, ti), 0)
                if active <= 0:
                    continue
                uph = p.uph_of(model, ti)
                if uph:
                    capacity += active * uph
            q = int(min(capacity, s.wip[ti]))
            if q <= 0:
                continue
            s.produced[ti] += q
            s.wip[ti] -= q
            nxt = p.next_task_index(ti)
            if nxt is not None:
                inflow[nxt] = inflow.get(nxt, 0) + q
        # 생산분은 다음 시간에 가용 (지금 더해두면 다음 advance에서 읽힘)
        for ti, v in inflow.items():
            s.wip[ti] += v
        # 전환 Idle 1시간 차감
        for key in list(s.idle):
            s.idle[key] = max(0, s.idle[key] - 1)
            if s.idle[key] == 0:
                del s.idle[key]
        s.hour += 1

    def is_done(self, s: SimState) -> bool:
        return s.hour >= self.p.horizon_hours

    def metrics(self, s: SimState) -> dict:
        p = self.p
        rates = []
        per_task = {}
        for i, t in enumerate(p.tasks):
            rate = min(s.produced[i] / t.plan_qty, 1.0) if t.plan_qty > 0 else 1.0
            rates.append(rate)
            per_task[f"{t.plan_prod_key}/{t.oper_id}"] = {
                "produced": s.produced[i], "plan": t.plan_qty, "rate": round(rate, 4)
            }
        return {
            "plan_achievement": round(sum(rates) / len(rates), 4) if rates else 0.0,
            "per_task": per_task,
        }

    def valid_moves(self, s: SimState) -> list[Move]:
        """현재 상태에서 둘 수 있는 (model, from, to) 이동 목록."""
        p = self.p
        out: list[Move] = []
        n = len(p.tasks)
        for model in p.models():
            for fi in range(n):
                # 옮길 수 있는 (Idle 아닌) 대수가 있어야 함
                movable = s.assign.get((model, fi), 0) - s.idle.get((model, fi), 0)
                if movable <= 0:
                    continue
                for ti in range(n):
                    if ti == fi:
                        continue
                    if p.uph_of(model, ti) is None:        # 적격(UPH 존재)해야
                        continue
                    fb, tb = p.batch_of(fi), p.batch_of(ti)
                    if fb != tb:
                        if not p.can_convert(fb, tb):       # 그룹 외 전환 불가
                            continue
                        used = s.tool_used.get((tb, model), 0)
                        cap = p.tool_qty.get((tb, model), 0)
                        if used >= cap:                     # tool 부족
                            continue
                    out.append(Move(model, fi, ti))
        return out

    def apply_move(self, s: SimState, mv: Move) -> None:
        """장비 1대를 from→to로 이동. batch 변경이면 Idle + tool 교체."""
        p = self.p
        model, fi, ti = mv
        fb, tb = p.batch_of(fi), p.batch_of(ti)
        s.assign[(model, fi)] = s.assign.get((model, fi), 0) - 1
        if s.assign[(model, fi)] == 0:
            del s.assign[(model, fi)]
        s.assign[(model, ti)] = s.assign.get((model, ti), 0) + 1
        if fb != tb:
            s.idle[(model, ti)] = s.idle.get((model, ti), 0) + p.switch_time_hours
            s.tool_used[(fb, model)] = s.tool_used.get((fb, model), 0) - 1
            s.tool_used[(tb, model)] = s.tool_used.get((tb, model), 0) + 1


def load_problem(path: str | Path) -> ProblemInstance:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    tasks = [
        Task(t["plan_prod_key"], t["oper_id"], int(t["oper_seq"]),
             t["batch_id"], int(t["plan_qty"]), int(t.get("init_wip", 0)))
        for t in data["tasks"]
    ]

    def task_index(ppk: str, oper: str) -> int:
        for i, t in enumerate(tasks):
            if t.plan_prod_key == ppk and t.oper_id == oper:
                return i
        raise KeyError(f"task not found: {ppk}/{oper}")

    uph = {
        (u["eqp_model"], task_index(u["plan_prod_key"], u["oper_id"])): float(u["uph"])
        for u in data["uph"] if float(u["uph"]) > 0
    }
    init_assign = {
        (a["eqp_model"], task_index(a["plan_prod_key"], a["oper_id"])): int(a["count"])
        for a in data["init_assign"]
    }
    tool_qty = {(t["batch_id"], t["eqp_model"]): int(t["tool_qty"]) for t in data["tool_qty"]}
    return ProblemInstance(
        rule_timekey=data["rule_timekey"],
        horizon_hours=int(data["horizon_hours"]),
        switch_time_hours=int(data.get("switch_time_hours", 1)),
        tasks=tasks,
        _uph=uph,
        eqp_qty={k: int(v) for k, v in data["eqp_qty"].items()},
        init_assign=init_assign,
        tool_qty=tool_qty,
        conv_groups={k: list(v) for k, v in data["conv_groups"].items()},
        ground_truth=data.get("ground_truth", {}),
    )
