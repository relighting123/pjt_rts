"""RL 디스패치 정책 팩토리."""
from __future__ import annotations

from src.simulation.domain.problem import ProblemInstance
from src.simulation.domain.state import SimState
from src.simulation.kernel.simulator import Simulator
from agents.protocol import PolicyFn
from agents.registry import register_dispatch
from src.stages.dispatch.bridge import DispatchBridge


def rl_dispatch_factory(model, problem: ProblemInstance) -> PolicyFn:
    bridge = DispatchBridge(problem)

    def policy_fn(sim: Simulator, s: SimState) -> list:
        return bridge.plan_moves(sim, s, model)

    return policy_fn


def register_rl_dispatch(model, problem: ProblemInstance) -> PolicyFn:
    """모델 인스턴스별 동적 정책 — registry 대신 팩토리 반환."""
    return rl_dispatch_factory(model, problem)
