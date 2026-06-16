"""Stage 1 — 가이드 배분 값 객체."""
from __future__ import annotations

from dataclasses import dataclass

from src.simulation.domain.problem import ProblemInstance


@dataclass(frozen=True)
class GuideAllocation:
    """공정×모델 목표 장비 대수 (정수)."""
    counts: dict[tuple[str, int], int]

    @classmethod
    def from_raw(cls, problem: ProblemInstance, raw: dict[tuple[str, int], float | int]) -> GuideAllocation:
        return cls(counts=problem.complete_guide_allocation(raw))

    def as_dict(self) -> dict[tuple[str, int], int]:
        return dict(self.counts)
