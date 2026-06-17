"""학습 수렴 로그 — PPO callback."""
from __future__ import annotations

import numpy as np
from stable_baselines3.common.callbacks import BaseCallback

from src.training.log_io import append_training_point


class ConvergenceLogger(BaseCallback):
    """PPO rollout 종료마다 평균 에피소드 보상을 기록."""

    def __init__(self, stage: str, log_every_rollouts: int = 1):
        super().__init__()
        self.stage = stage
        self.log_every_rollouts = max(1, log_every_rollouts)
        self._rollouts = 0

    def _on_step(self) -> bool:
        return True

    def _on_rollout_end(self) -> None:
        self._rollouts += 1
        if self._rollouts % self.log_every_rollouts != 0:
            return
        buffer = getattr(self.model, "ep_info_buffer", None)
        if not buffer:
            return
        rewards = [float(info["r"]) for info in buffer if "r" in info]
        if not rewards:
            return
        append_training_point(self.stage, {
            "phase": "ppo",
            "timesteps": int(self.num_timesteps),
            "mean_reward": round(float(np.mean(rewards)), 6),
            "episodes": len(rewards),
        })
