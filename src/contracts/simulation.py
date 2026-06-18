"""시뮬레이션 실행 결과 계약."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.simulation.domain.problem import Move
from src.simulation.domain.state import SimState


@dataclass(frozen=True)
class TraceStep:
    hour: int
    moves: tuple[Move, ...]
    assign_snapshot: dict[tuple[str, int], int]


@dataclass(frozen=True)
class HourlyStat:
    hour: int
    hourly_produce: dict[int, int]
    cumulative_produced: dict[int, int]
    util_rate: float
    assign_snapshot: dict[tuple[str, int], int]
    wip_snapshot: dict[int, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "hour": self.hour,
            "hourly_produce": dict(self.hourly_produce),
            "cumulative_produced": dict(self.cumulative_produced),
            "util_rate": self.util_rate,
            "assign_snapshot": dict(self.assign_snapshot),
            "wip_snapshot": dict(self.wip_snapshot),
        }

    @classmethod
    def from_dict(cls, d: dict) -> HourlyStat:
        return cls(
            hour=d["hour"],
            hourly_produce=dict(d["hourly_produce"]),
            cumulative_produced=dict(d["cumulative_produced"]),
            util_rate=float(d["util_rate"]),
            assign_snapshot=dict(d["assign_snapshot"]),
            wip_snapshot=dict(d.get("wip_snapshot", {})),
        )


@dataclass(frozen=True)
class SimulationRun:
    """Stage 2 dispatch 실행 결과."""
    final_state: SimState
    trace: tuple[TraceStep, ...]
    hourly_stats: tuple[HourlyStat, ...]
    plan_achievement: float
    per_task: dict[str, dict]
    policy_name: str = "heuristic"

    @property
    def legacy_trace(self) -> list:
        """기존 (hour, moves, snapshot) 튜플 리스트 호환."""
        return [(t.hour, list(t.moves), dict(t.assign_snapshot)) for t in self.trace]

    @property
    def legacy_hourly_stats(self) -> list[dict]:
        return [h.to_dict() for h in self.hourly_stats]

    @classmethod
    def from_legacy(
        cls,
        final: SimState,
        trace: list,
        hourly_stats: list[dict],
        metrics: dict,
        policy_name: str = "heuristic",
    ) -> SimulationRun:
        steps = tuple(
            TraceStep(hour=h, moves=tuple(moves), assign_snapshot=dict(snap))
            for h, moves, snap in trace
        )
        stats = tuple(HourlyStat.from_dict(s) for s in hourly_stats)
        return cls(
            final_state=final,
            trace=steps,
            hourly_stats=stats,
            plan_achievement=float(metrics["plan_achievement"]),
            per_task=dict(metrics["per_task"]),
            policy_name=policy_name,
        )
