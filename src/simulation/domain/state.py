from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SimState:
    hour: int
    produced: dict[int, int]
    wip: dict[int, int]
    assign: dict[tuple[str, int], int]
    switching: dict[tuple[str, int], int]
    tool_used: dict[tuple[str, str], int]
