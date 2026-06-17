"""학습 수렴 JSONL 읽기/쓰기 (stable_baselines3 불필요)."""
from __future__ import annotations

import json
from pathlib import Path

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
