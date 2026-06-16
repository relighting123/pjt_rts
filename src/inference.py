"""추론 파이프라인 — db/pipeline 래핑."""
from __future__ import annotations

from pathlib import Path

from src.db.pipeline import run_inference as _run_inference


def run_infer(**kwargs):
    return _run_inference(**kwargs)
