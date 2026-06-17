"""RTS 스케줄링 분석 API + 정적 UI 서빙.

실행:
  uvicorn src.api.main:app --host 0.0.0.0 --port 8000

UI(web/dist 빌드본)가 있으면 루트(/)에서 함께 서빙한다.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import config
from src.api import ops, service
from src.api.schemas import ExportRequest, InferRequest, TrainRequest

app = FastAPI(title="RTS 스케줄링 분석 API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    """헬스체크 — 운영(export/infer/train) API 지원 여부 포함."""
    return {"status": "ok", "ops": True, "version": app.version}


@app.get("/api/datasets")
def datasets():
    """분석 가능한 데이터셋 목록 (벤치마크 + 추론 입력)."""
    return service.list_datasets()


@app.get("/api/datasets/{name}")
def dataset_detail(name: str, env_type: str = "dispatch"):
    """데이터셋 1건 분석 결과 — 간트/전환/move/달성률/가이드.
    env_type: dispatch(기본) | alloc
    """
    try:
        return service.analyze(name, env_type=env_type)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"dataset not found: {name}")


@app.get("/api/training/metrics")
def training_metrics(stage: str = "dispatch"):
    """학습 수렴 로그 (dispatch | alloc)."""
    if stage not in ("dispatch", "alloc"):
        raise HTTPException(status_code=400, detail="stage must be dispatch or alloc")
    return {"stage": stage, "points": service.training_metrics(stage)}


@app.get("/api/summary")
def summary(env_type: str = "dispatch"):
    """전체 데이터셋 비교 요약."""
    return service.summary(env_type=env_type)


@app.get("/api/ops/status")
def ops_status():
    """운영 대시보드 상태 — 기본값, 모델/JSON 존재, 실행 중 작업."""
    return ops.get_status()


@app.get("/api/ops/jobs")
def ops_jobs(limit: int = 20):
    """최근 백그라운드 작업 목록."""
    return {"jobs": ops.list_jobs(limit=min(max(limit, 1), 100))}


@app.get("/api/ops/jobs/{job_id}")
def ops_job_detail(job_id: str):
    job = ops.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"job not found: {job_id}")
    return job


@app.get("/api/ops/logs")
def ops_logs(limit: int = 200):
    """ops.jsonl 최근 이벤트."""
    return {"logs": ops.read_ops_logs(limit=min(max(limit, 1), 1000))}


def _submit_or_conflict(fn):
    try:
        return fn()
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/ops/export")
def ops_export(req: ExportRequest):
    """DB → JSON export (단건 또는 학습 범위)."""
    return _submit_or_conflict(lambda: ops.start_export(req))


@app.post("/api/ops/infer")
def ops_infer(req: InferRequest):
    """추론 파이프라인 실행."""
    return _submit_or_conflict(lambda: ops.start_infer(req))


@app.post("/api/ops/train")
def ops_train(req: TrainRequest):
    """학습 파이프라인 실행 (선택: DB 범위 export 후 학습)."""
    return _submit_or_conflict(lambda: ops.start_train(req))


_DIST = Path(config.ROOT) / "web" / "dist"
if _DIST.is_dir():
    app.mount("/", StaticFiles(directory=_DIST, html=True), name="ui")
