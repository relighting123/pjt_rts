"""Ops API 요청/응답 스키마."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

import config


class ExportRequest(BaseModel):
    mode: Literal["single", "train_range"] = "single"
    timekey: str | None = None
    from_timekey: str | None = None
    to_timekey: str | None = None
    lookback_days: int = Field(default=config.DEFAULT_TRAIN_LOOKBACK_DAYS, ge=1, le=365)
    horizon_hours: int = Field(default=12, ge=1, le=168)
    facid: str | None = None
    batchid: str | None = None
    sample: bool = False


class InferRequest(BaseModel):
    timekey: str | None = None
    facid: str | None = None
    batchid: str | None = None
    horizon_hours: int = Field(default=12, ge=1, le=168)
    skip_input_export: bool = False
    write_db: bool = True


class TrainRequest(BaseModel):
    mode: Literal["local", "db_range"] = "local"
    from_timekey: str | None = None
    to_timekey: str | None = None
    lookback_days: int = Field(default=config.DEFAULT_TRAIN_LOOKBACK_DAYS, ge=1, le=365)
    horizon_hours: int = Field(default=12, ge=1, le=168)
    facid: str | None = None
    batchid: str | None = None
    steps: int = Field(default=config.DEFAULT_PPO_STEPS, ge=100, le=5_000_000)
