"""Stage 1 — 장비 배분 단일 진입점."""
from __future__ import annotations

import warnings

import config
from src.simulation.domain.allocation import GuideAllocation
from src.simulation.domain.problem import ProblemInstance


def allocate(problem: ProblemInstance, policy: str = "auto") -> GuideAllocation:
    """공정×모델 목표 장비 대수 산출.

    policy: auto | analytic | rl
    """
    if policy == "auto":
        policy = "rl" if config.USE_ALLOC_MODEL else "analytic"
    if policy == "rl":
        raw = _allocate_rl(problem)
        if raw is not None:
            return GuideAllocation.from_raw(problem, raw)
    return GuideAllocation.from_raw(problem, problem.plan_target_allocation_int())


def _allocate_rl(problem: ProblemInstance) -> dict[tuple[str, int], int] | None:
    from agents.model_store import load_alloc_model

    path = config.SAVED_MODELS_DIR / "ppo_alloc.zip"
    if not path.exists():
        return None
    model = load_alloc_model(path)
    if model is None:
        return None
    try:
        from envs.allocation_env import AllocationEnv
        env = AllocationEnv(problem, max_tasks=config.MAX_TASKS, max_models=config.MAX_MODELS)
        obs, _ = env.reset()
        action, _ = model.predict(obs, deterministic=True)
        env.step(action)
        return env.get_allocation()
    except Exception as e:
        warnings.warn(f"AllocationEnv 추론 실패 ({e!r}); 해석식 가이드로 폴백.")
        return None
