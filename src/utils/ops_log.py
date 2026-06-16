"""운영 실행 로그 — 콘솔 + artifacts/inference/ops.jsonl."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import config

OPS_LOG_PATH = config.ARTIFACTS_DIR / "inference" / "ops.jsonl"


def _serialize(value) -> str:
    if value is None:
        return "-"
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)


def log_ops(event: str, **params) -> None:
    """파라미터 포함 로그. stdout 출력 + ops.jsonl append."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    record = {"ts": ts, "event": event, **{k: _serialize(v) for k, v in params.items()}}
    line = " ".join([f"[{event}]", ts] + [f"{k}={record[k]}" for k in params])
    print(line, flush=True)
    OPS_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OPS_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
