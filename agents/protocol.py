"""정책 프로토콜."""
from __future__ import annotations

from typing import Callable, Protocol

from src.simulation.domain.problem import Move, ProblemInstance
from src.simulation.domain.state import SimState
from src.simulation.kernel.simulator import Simulator

PolicyFn = Callable[[Simulator, SimState], list[Move]]


class AllocationPolicyPort(Protocol):
    def allocate(self, problem: ProblemInstance) -> dict[tuple[str, int], int]: ...
