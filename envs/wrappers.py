"""Gym env wrappers — ActionMasker, make_env."""
from __future__ import annotations

import random

from sb3_contrib.common.wrappers import ActionMasker

import config
from agents.heuristic import heuristic_actions
from agents.model_store import load_alloc_model
from envs.allocation_env import AllocationEnv
from envs.dispatch_env import DispatchEnv
from src.simulation.domain.problem import ProblemInstance
from src.stages.allocation.use_case import allocate


def mask_fn(env) -> list:
    return env.action_masks()


def get_target_allocation(problem: ProblemInstance) -> dict:
    if config.USE_ALLOC_MODEL and config.ALLOC_LAMBDA > 0.0:
        alloc_model_path = config.CHECKPOINTS_DIR / "ppo_alloc.zip"
        if alloc_model_path.exists():
            alloc_model = load_alloc_model(alloc_model_path)
            if alloc_model is not None:
                alloc_env = AllocationEnv(
                    problem, max_tasks=config.MAX_TASKS, max_models=config.MAX_MODELS,
                )
                obs, _ = alloc_env.reset()
                action, _ = alloc_model.predict(obs, deterministic=True)
                alloc_env.step(action)
                return problem.complete_guide_allocation(alloc_env.get_allocation())
    return allocate(problem).as_dict()


def make_dispatch_env(problem: ProblemInstance) -> ActionMasker:
    target = get_target_allocation(problem) if config.ALLOC_LAMBDA > 0.0 else {}
    env = DispatchEnv(
        problem,
        max_tasks=config.MAX_TASKS,
        max_models=config.MAX_MODELS,
        dwell_lambda=config.DWELL_LAMBDA,
        alloc_lambda=config.ALLOC_LAMBDA,
        target_allocation=target,
        dwell_obs=config.DWELL_OBS,
        guide_util_threshold=config.GUIDE_UTIL_THRESHOLD,
        guide_band_pct=config.GUIDE_BAND_PCT,
    )
    return ActionMasker(env, mask_fn)


def make_training_env(problems: list[ProblemInstance]):
    """PPO 학습용 env factory."""
    def _factory():
        return make_dispatch_env(random.choice(problems))
    return _factory
