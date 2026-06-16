"""RL 모델 로드·shape 검증·캐시."""
from __future__ import annotations

from pathlib import Path

import config
from src.simulation.domain.problem import ProblemInstance

_DISPATCH_CACHE: dict = {}
_ALLOC_CACHE: dict = {}


def load_dispatch_model(path: Path | None = None):
    path = Path(path) if path else config.MODEL_PATH
    key = str(path)
    if key in _DISPATCH_CACHE:
        return _DISPATCH_CACHE[key]
    model = None
    if path.exists():
        try:
            from sb3_contrib import MaskablePPO
            model = MaskablePPO.load(path)
        except Exception:
            model = None
    _DISPATCH_CACHE[key] = model
    return model


def load_alloc_model(path: Path):
    key = (str(path), path.stat().st_mtime)
    if key in _ALLOC_CACHE:
        return _ALLOC_CACHE[key]
    model = None
    try:
        import stable_baselines3 as sb3
        model = sb3.PPO.load(path)
    except Exception:
        model = None
    _ALLOC_CACHE[key] = model
    return model


def dispatch_model_matches(model, problem: ProblemInstance) -> bool:
    from envs.dispatch_env import DispatchEnv
    env = DispatchEnv(problem, max_tasks=config.MAX_TASKS,
                      max_models=config.MAX_MODELS, dwell_obs=config.DWELL_OBS)
    try:
        obs_ok = tuple(model.observation_space.shape) == tuple(env.observation_space.shape)
        act_ok = int(model.action_space.n) == int(env.action_space.n)
        return obs_ok and act_ok
    except Exception:
        return False


def rl_status(problem: ProblemInstance, result_has_rl: bool) -> dict:
    model_path_exists = Path(config.MODEL_PATH).exists()
    model = load_dispatch_model()
    if model is None:
        return {
            "available": False,
            "reason": "model_missing" if not model_path_exists else "model_load_failed",
        }
    if not result_has_rl:
        return {"available": False, "reason": "shape_mismatch"}
    return {"available": True, "reason": "ready"}
