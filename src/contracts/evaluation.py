"""벤치마크 평가 결과 계약."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.contracts.simulation import SimulationRun
from src.simulation.domain.allocation import GuideAllocation


@dataclass(frozen=True)
class PolicyRunResult:
    """단일 정책 실행 + 산출 테이블."""
    run: SimulationRun
    avg_utilization: float
    output_tables: dict[str, list[dict]] = field(default_factory=dict)
    assign_rows: list[dict] = field(default_factory=list)
    conv_rows: list[dict] = field(default_factory=list)

    def to_legacy_dict(self, prefix: str = "") -> dict[str, Any]:
        p = prefix
        out: dict[str, Any] = {
            f"{p}trace" if p else "trace": self.run.legacy_trace,
            f"{p}hourly_stats" if p else "hourly_stats": self.run.legacy_hourly_stats,
            f"{p}avg_utilization" if p else "avg_utilization": self.avg_utilization,
            f"{p}output_tables" if p else "output_tables": self.output_tables,
            f"{p}assign_rows" if p else "assign_rows": self.assign_rows,
            f"{p}eqpconvplan_rows" if p else "eqpconvplan_rows": self.conv_rows,
            f"{p}conv_rows" if p else "conv_rows": self.conv_rows,
            f"{p}allocation_rows" if p else "allocation_rows": self.assign_rows,
        }
        if p:
            out["rl"] = self.run.plan_achievement
            out["rl_per_task"] = self.run.per_task
        else:
            out["heuristic"] = self.run.plan_achievement
            out["heuristic_per_task"] = self.run.per_task
        return out


@dataclass(frozen=True)
class EvaluationResult:
    """벤치마크 1건 평가 결과."""
    heuristic: PolicyRunResult
    guide: GuideAllocation
    optimal: float | None = None
    rl: PolicyRunResult | None = None

    def to_legacy_dict(self) -> dict[str, Any]:
        out = self.heuristic.to_legacy_dict()
        out["guide_allocation"] = self.guide.as_dict()
        out["optimal"] = self.optimal
        out["heuristic_final_wip"] = dict(self.heuristic.run.final_state.wip)
        out["heuristic_sim_hours"] = self.heuristic.run.final_state.hour
        if self.rl is not None:
            out.update(self.rl.to_legacy_dict(prefix="rl_"))
            out["rl"] = self.rl.run.plan_achievement
            out["rl_per_task"] = self.rl.run.per_task
            out["rl_final_wip"] = dict(self.rl.run.final_state.wip)
            out["rl_sim_hours"] = self.rl.run.final_state.hour
        return out
