"""RTS 스케줄링 분석 API + 정적 UI 서빙.

실행:
  uvicorn server.main:app --host 0.0.0.0 --port 8000           # 개발
  uvicorn server.main:app --workers 4 --port 8000              # 다중 요청 처리

UI(web/dist 빌드본)가 있으면 루트(/)에서 함께 서빙한다.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import config
from server import service

app = FastAPI(title="RTS 스케줄링 분석 API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok"}


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


@app.get("/api/summary")
def summary(env_type: str = "dispatch"):
    """전체 데이터셋 비교 요약."""
    return service.summary(env_type=env_type)


_DIST = Path(config.ROOT) / "web" / "dist"
if _DIST.is_dir():
    app.mount("/", StaticFiles(directory=_DIST, html=True), name="ui")
