"""시뮬레이션 엔진 — 정책 없음, 상태 전이만."""
from __future__ import annotations

from src.simulation.domain.problem import Move, ProblemInstance
from src.simulation.domain.state import SimState


def active_eqp_count(p: ProblemInstance, s: SimState) -> int:
    """Idle 제외, WIP가 남아 생산에 기여 중인 장비 대수 합."""
    return sum(
        max(0, s.assign.get((m, ti), 0) - s.switching.get((m, ti), 0))
        for m in p.models()
        for ti in range(len(p.tasks))
        if s.wip[ti] > 0 and p.uph_of(m, ti)
    )


class Simulator:
    """1시간 단위로 전이하는 결정론적 시뮬레이터."""

    def __init__(self, problem: ProblemInstance):
        self.p = problem

    def reset(self) -> SimState:
        p = self.p
        wip = {i: t.init_wip for i, t in enumerate(p.tasks)}
        produced = {i: 0 for i in range(len(p.tasks))}
        assign = dict(p.init_assign)
        switching: dict[tuple[str, int], int] = {}
        tool_used: dict[tuple[str, str], int] = {}
        for (model, ti), cnt in assign.items():
            key = (p.batch_of(ti), model)
            tool_used[key] = tool_used.get(key, 0) + cnt
        return SimState(0, produced, wip, assign, switching, tool_used)

    def advance_hour(self, s: SimState) -> None:
        p = self.p
        inflow: dict[int, int] = {}
        for ti in range(len(p.tasks)):
            capacity = self.task_capacity(s, ti)
            q = int(min(capacity, s.wip[ti]))
            if q <= 0:
                continue
            s.produced[ti] += q
            s.wip[ti] -= q
            nxt = p.next_task_index(ti)
            if nxt is not None:
                inflow[nxt] = inflow.get(nxt, 0) + q
        for ti, v in inflow.items():
            s.wip[ti] += v
        for key in list(s.switching):
            model, ti = key
            machines_here = s.assign.get((model, ti), 0)
            s.switching[key] = max(0, s.switching[key] - machines_here)
            if s.switching[key] == 0:
                del s.switching[key]
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
        p = self.p
        out: list[Move] = []
        n = len(p.tasks)
        for model in p.models():
            for fi in range(n):
                movable = s.assign.get((model, fi), 0) - s.switching.get((model, fi), 0)
                if movable <= 0:
                    continue
                for ti in range(n):
                    if ti == fi:
                        continue
                    if p.uph_of(model, ti) is None:
                        continue
                    fb, tb = p.batch_of(fi), p.batch_of(ti)
                    if fb != tb:
                        if not p.can_convert(fb, tb):
                            continue
                        used = s.tool_used.get((tb, model), 0)
                        cap = p.tool_qty.get((tb, model), 0)
                        if used >= cap:
                            continue
                    out.append(Move(model, fi, ti))
        return out

    def apply_move(self, s: SimState, mv: Move) -> None:
        p = self.p
        model, fi, ti = mv
        fb, tb = p.batch_of(fi), p.batch_of(ti)
        s.assign[(model, fi)] = s.assign.get((model, fi), 0) - 1
        if s.assign[(model, fi)] == 0:
            del s.assign[(model, fi)]
        s.assign[(model, ti)] = s.assign.get((model, ti), 0) + 1
        if fb != tb:
            s.switching[(model, ti)] = s.switching.get((model, ti), 0) + p.switch_time_hours
            s.tool_used[(fb, model)] = max(0, s.tool_used.get((fb, model), 0) - 1)
            s.tool_used[(tb, model)] = s.tool_used.get((tb, model), 0) + 1

    def task_capacity(self, s: SimState, task_index: int) -> float:
        cap = 0.0
        for model in self.p.models():
            active = s.assign.get((model, task_index), 0) - s.switching.get((model, task_index), 0)
            if active > 0 and (uph := self.p.uph_of(model, task_index)):
                cap += active * uph
        return cap

    def wip_dwell_time(self, s: SimState, task_index: int) -> float | None:
        p = self.p
        wip = s.wip[task_index]
        H = float(p.horizon_hours)
        if wip == 0:
            return 0.0
        cap_cur = self.task_capacity(s, task_index)
        if cap_cur <= 0:
            return None
        prev_ti = p.prev_task_index(task_index)
        if prev_ti is None:
            return min(wip / cap_cur, H)
        cap_prev = self.task_capacity(s, prev_ti)
        denom = min(cap_cur, float(wip)) - min(cap_prev, float(wip))
        if denom <= 0:
            return None
        return min(wip / denom, H)
