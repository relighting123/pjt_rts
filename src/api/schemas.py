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


class MlConfigUpdate(BaseModel):
    ppo_steps: int | None = Field(default=None, ge=100, le=5_000_000)
    bc_epochs: int | None = Field(default=None, ge=1, le=10_000)
    bc_lr: float | None = Field(default=None, gt=0, le=1.0)
    bc_loss_target: float | None = Field(default=None, gt=0, le=10.0)
    max_tasks: int | None = Field(default=None, ge=1, le=64)
    max_models: int | None = Field(default=None, ge=1, le=32)
    dwell_lambda: float | None = Field(default=None, ge=0, le=10)
    alloc_lambda: float | None = Field(default=None, ge=0, le=10)
    dwell_obs: bool | None = None
    use_alloc_model: bool | None = None
    guide_util_threshold: float | None = Field(default=None, ge=0, le=1)
    guide_band_pct: float | None = Field(default=None, ge=0, le=1)
    horizon_hours: int | None = Field(default=None, ge=1, le=168)
    lookback_days: int | None = Field(default=None, ge=1, le=365)


class ModelRegisterRequest(BaseModel):
    source_path: str | None = None
    name: str | None = None
    notes: str = ""
    model_id: str | None = None


class ModelCompareRequest(BaseModel):
    model_ids: list[str] = Field(min_length=1, max_length=10)
    split: Literal["train", "validation", "test"] = "test"
    env_type: Literal["dispatch", "alloc"] = "dispatch"
