"""학습 파이프라인."""
from __future__ import annotations

from pathlib import Path

import config
from src.training.dispatch import train_model
from src.utils.json_io import load_problem


def run_train(problems=None, ppo_steps: int | None = None, use_db: bool = False,
              train_dir: Path | None = None) -> Path:
    if problems is None:
        directory = train_dir or config.TRAIN_DATA_DIR
        problems = [load_problem(p) for p in sorted(Path(directory).glob("*.json"))]
    if not problems:
        raise SystemExit("학습 문제 없음.")
    steps = ppo_steps or config.DEFAULT_PPO_STEPS
    train_model(problems, ppo_steps=steps)
    return config.MODEL_PATH
