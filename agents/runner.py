"""시뮬레이션 러너 — policy_fn을 매 시간 적용."""
from __future__ import annotations

from src.contracts.simulation import SimulationRun
from src.simulation.kernel.simulator import Simulator, active_eqp_count
from agents.protocol import PolicyFn


def run_policy(sim: Simulator, policy_fn: PolicyFn, policy_name: str = "heuristic") -> SimulationRun:
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
        wip_snapshot = dict(s.wip)
        before = dict(s.produced)
        util_rate = round(active_eqp_count(p, s) / total_eqp, 4)
        sim.advance_hour(s)
        hourly_produce = {ti: s.produced[ti] - before.get(ti, 0) for ti in range(n_tasks)}
        stat = {
            "hour": hour,
            "hourly_produce": hourly_produce,
            "cumulative_produced": dict(s.produced),
            "util_rate": util_rate,
            "assign_snapshot": snapshot,
            "wip_snapshot": wip_snapshot,
        }
        hourly_stats.append(stat)
        trace.append((hour, applied, snapshot))
    metrics = sim.metrics(s)
    return SimulationRun.from_legacy(s, trace, hourly_stats, metrics, policy_name=policy_name)


def evaluate(problem, policy_name: str = "heuristic") -> dict:
    """휴리스틱 단일 정책 평가 (레거시 dict 반환)."""
    from agents.registry import get_dispatch

    sim = Simulator(problem)
    run = run_policy(sim, get_dispatch(policy_name), policy_name=policy_name)
    return {
        "heuristic": run.plan_achievement,
        "optimal": problem.ground_truth.get("plan_achievement"),
        "per_task": run.per_task,
        "trace": run.legacy_trace,
        "hourly_stats": run.legacy_hourly_stats,
    }
