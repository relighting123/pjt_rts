"""학습 수렴 로그 — JSONL 저장."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from stable_baselines3.common.callbacks import BaseCallback

import config


def training_log_path(stage: str) -> Path:
    return config.LOGS_DIR / "training" / f"{stage}.jsonl"


def append_training_point(stage: str, point: dict) -> None:
    path = training_log_path(stage)
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {"stage": stage, **point}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_training_metrics(stage: str) -> list[dict]:
    path = training_log_path(stage)
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def reset_training_log(stage: str) -> None:
    path = training_log_path(stage)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        path.unlink()


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
