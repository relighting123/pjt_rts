"""Stage 2 — 디스패치 실행."""
from __future__ import annotations

from src.contracts.simulation import SimulationRun
from src.simulation.domain.allocation import GuideAllocation
from src.simulation.domain.problem import ProblemInstance
from src.simulation.kernel.simulator import Simulator
from agents.protocol import PolicyFn
from agents.registry import get_dispatch
from agents.runner import run_policy


def run_dispatch(
    problem: ProblemInstance,
    guide: GuideAllocation | None = None,
    policy: str | PolicyFn = "heuristic",
    policy_name: str | None = None,
) -> SimulationRun:
    """가이드(선택)를 참고하며 horizon까지 시뮬레이션."""
    sim = Simulator(problem)
    if callable(policy):
        policy_fn = policy
        name = policy_name or "custom"
    else:
        policy_fn = get_dispatch(policy)
        name = policy
    return run_policy(sim, policy_fn, policy_name=name)
