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
            s.tool_used[(fb, model)] = max(0, s.tool_used.get((fb, model), 0) - 1)
            s.tool_used[(tb, model)] = s.tool_used.get((tb, model), 0) + 1


def _remaining(p: ProblemInstance, s: SimState, ti: int) -> int:
    return max(0, p.tasks[ti].plan_qty - s.produced[ti])


def heuristic_actions(sim: "Simulator", s: SimState) -> list[Move]:
    """이번 1시간에 둘 이동들을 그리디로 결정.

    원칙:
    1) 잔여계획이 0인 task에서 잔여계획이 큰 task로 장비를 옮긴다.
    2) batch 전환은 from-task가 더 이상 기여 못할 때만(잔여=0 또는 WIP=0).
    3) 한 시간의 남은 잔여계획을 가장 많이 줄이는 이동을 우선.
    """
    p = sim.p
    moves: list[Move] = []
    # 반복적으로 최선 이동 1개씩 선택 (substep)
    for _ in range(sum(p.eqp_qty.values()) + 1):
        candidates = sim.valid_moves(s)
        best, best_gain = None, 0.0
        for mv in candidates:
            from_rem = _remaining(p, s, mv.from_index)
            from_wip = s.wip[mv.from_index]
            to_rem = _remaining(p, s, mv.to_index)
            uph_to = p.uph_of(mv.model, mv.to_index) or 0.0
            uph_from = p.uph_of(mv.model, mv.from_index) or 0.0
            same_batch = p.batch_of(mv.from_index) == p.batch_of(mv.to_index)
            to_has_eqp = any(s.assign.get((m, mv.to_index), 0) > 0 for m in p.models())
            # from이 여전히 유효 생산 중이면 기본 유지하되, 무비용(같은 batch) 이동만 예외 허용:
            # (a) to의 UPH가 더 높아 총 생산이 늘거나
            # (b) to가 잔여>0인데 장비가 없어 무비용 충원이 가능할 때
            #     (단, UPH 저하 이동은 제외 — 고UPH 장비가 저UPH 태스크로 역배치되는 thrashing 방지)
            if from_rem > 0 and from_wip > 0:
                better_here = same_batch and uph_to > uph_from
                fill_empty_free = same_batch and to_rem > 0 and not to_has_eqp and uph_to >= uph_from
                if not (better_here or fill_empty_free):
                    continue
            hours_left = p.horizon_hours - s.hour - (0 if same_batch else p.switch_time_hours)
            gain = min(to_rem, s.wip[mv.to_index], uph_to * max(0, hours_left))
            if gain > best_gain:
                best, best_gain = mv, gain
        if best is None:
            break
        sim.apply_move(s, best)
        moves.append(best)
    return moves


def _active_eqp_count(p: ProblemInstance, s: SimState) -> int:
    """Idle 제외, 처리할 WIP가 남아 실제로 생산에 기여 중인 장비 대수 합."""
    return sum(
        max(0, s.assign.get((m, ti), 0) - s.idle.get((m, ti), 0))
        for m in p.models()
        for ti in range(len(p.tasks))
        if s.wip[ti] > 0 and p.uph_of(m, ti)
    )


def run_policy(sim: "Simulator", policy_fn) -> tuple[SimState, list, list[dict]]:
    """policy_fn(sim, state)->list[Move]를 매 시간 적용하며 horizon까지 시뮬레이션.

    반환 trace 항목: (hour, applied_moves, assign_snapshot)
    hourly_stats 항목: hour, hourly_produce, cumulative_produced, util_rate, assign_snapshot
    """
    p = sim.p
    s = sim.reset()
    trace: list = []
    hourly_stats: list[dict] = []
    total_eqp = sum(p.eqp_qty.values()) or 1
    n_tasks = len(p.tasks)
    while not sim.is_done(s):
        hour = s.hour
        applied = policy_fn(sim, s)
        snapshot = {(m, ti): c for (m, ti), c in s.assign.items()}
        before = dict(s.produced)
        util_rate = round(_active_eqp_count(p, s) / total_eqp, 4)
        sim.advance_hour(s)
        hourly_produce = {ti: s.produced[ti] - before.get(ti, 0) for ti in range(n_tasks)}
        stat = {
            "hour": hour,
            "hourly_produce": hourly_produce,
            "cumulative_produced": dict(s.produced),
            "util_rate": util_rate,
            "assign_snapshot": snapshot,
        }
        hourly_stats.append(stat)
        trace.append((hour, applied, snapshot))
    return s, trace, hourly_stats


def evaluate(problem: ProblemInstance) -> dict:
    """휴리스틱 vs ground_truth 비교."""
    sim = Simulator(problem)
    final, trace, hourly_stats = run_policy(sim, heuristic_actions)
    m = sim.metrics(final)
    return {
        "heuristic": m["plan_achievement"],
        "optimal": problem.ground_truth.get("plan_achievement"),
        "per_task": m["per_task"],
        "trace": trace,
        "hourly_stats": hourly_stats,
    }


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
