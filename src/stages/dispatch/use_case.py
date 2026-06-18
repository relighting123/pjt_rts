"""Stage 2 — 디스패치 실행."""
from __future__ import annotations

import copy

from src.contracts.simulation import SimulationRun
from src.simulation.domain.allocation import GuideAllocation
from src.simulation.domain.problem import ProblemInstance, estimate_wip_simulation_hours
from src.simulation.kernel.simulator import Simulator
from agents.protocol import PolicyFn
from agents.registry import get_dispatch
from agents.runner import run_policy


def run_dispatch(
    problem: ProblemInstance,
    guide: GuideAllocation | None = None,
    policy: str | PolicyFn = "heuristic",
    policy_name: str | None = None,
    until_wip_exhausted: bool = False,
) -> SimulationRun:
    """가이드(선택)를 참고하며 시뮬레이션. until_wip_exhausted 시 재공 소진까지 진행."""
    prob = copy.deepcopy(problem)
    if until_wip_exhausted:
        max_h = estimate_wip_simulation_hours(problem)
        prob.horizon_hours = max_h
        sim = Simulator(prob, until_wip_exhausted=True, max_hours=max_h)
    else:
        sim = Simulator(prob)
    if callable(policy):
        policy_fn = policy
        name = policy_name or "custom"
    else:
        policy_fn = get_dispatch(policy)
        name = policy
    return run_policy(sim, policy_fn, policy_name=name)
