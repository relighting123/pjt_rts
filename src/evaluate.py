"""벤치마크 평가 파이프라인."""
from __future__ import annotations

import agents.heuristic as _heuristic_reg  # noqa: F401 — register
from agents.model_store import dispatch_model_matches, load_dispatch_model
from agents.rl_dispatch import rl_dispatch_factory
from src.contracts.evaluation import EvaluationResult, PolicyRunResult
from src.utils.rows import enrich_eval_result
from src.simulation.domain.problem import ProblemInstance
from src.stages.allocation.use_case import allocate
from src.stages.dispatch.use_case import run_dispatch


def _policy_run(problem: ProblemInstance, run, extra: dict) -> PolicyRunResult:
    return PolicyRunResult(
        run=run,
        avg_utilization=float(extra.get("avg_utilization", 0.0)),
        output_tables=extra.get("output_tables", {}),
        assign_rows=extra.get("assign_rows", []),
        conv_rows=extra.get("conv_rows", extra.get("eqpconvplan_rows", [])),
    )


def evaluate_benchmark(problem: ProblemInstance, model=None) -> dict:
    """벤치마크 1건 평가 — 레거시 dict 반환 (API 호환)."""
    return evaluate(problem, model=model).to_legacy_dict()


def evaluate(problem: ProblemInstance, model=None) -> EvaluationResult:
    guide = allocate(problem)
    h_run = run_dispatch(problem, guide, policy="heuristic")
    h_extra = enrich_eval_result(problem, h_run.legacy_trace, h_run.legacy_hourly_stats)
    heuristic = _policy_run(problem, h_run, h_extra)

    rl_result = None
    if model is not None and dispatch_model_matches(model, problem):
        rl_fn = rl_dispatch_factory(model, problem)
        rl_run = run_dispatch(problem, guide, policy=rl_fn, policy_name="rl")
        rl_extra = enrich_eval_result(problem, rl_run.legacy_trace, rl_run.legacy_hourly_stats)
        rl_result = _policy_run(problem, rl_run, rl_extra)

    return EvaluationResult(
        heuristic=heuristic,
        guide=guide,
        optimal=problem.ground_truth.get("plan_achievement"),
        rl=rl_result,
    )
