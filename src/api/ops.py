"""운영 작업(export / infer / train) 백그라운드 실행."""
from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import config
from src.api.schemas import ExportRequest, InferRequest, TrainRequest
from src.utils.ops_log import OPS_LOG_PATH

_jobs: dict[str, dict[str, Any]] = {}
_jobs_order: list[str] = []
_lock = threading.Lock()
_MAX_JOBS = 50


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _serialize_value(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {k: _serialize_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize_value(v) for v in value]
    return value


def _running_job() -> dict[str, Any] | None:
    for jid in reversed(_jobs_order):
        job = _jobs.get(jid)
        if job and job["status"] == "running":
            return job
    return None


def is_busy() -> bool:
    with _lock:
        return _running_job() is not None


def list_jobs(limit: int = 20) -> list[dict[str, Any]]:
    with _lock:
        ids = _jobs_order[-limit:]
        return [_public_job(_jobs[jid]) for jid in reversed(ids) if jid in _jobs]


def get_job(job_id: str) -> dict[str, Any] | None:
    with _lock:
        job = _jobs.get(job_id)
        return _public_job(job) if job else None


def _public_job(job: dict[str, Any] | None) -> dict[str, Any]:
    if job is None:
        return {}
    return {
        "id": job["id"],
        "kind": job["kind"],
        "status": job["status"],
        "params": job["params"],
        "created_at": job["created_at"],
        "started_at": job["started_at"],
        "finished_at": job["finished_at"],
        "result": job["result"],
        "error": job["error"],
    }


def submit_job(kind: str, params: dict[str, Any], fn: Callable[[], Any]) -> dict[str, Any]:
    with _lock:
        if _running_job() is not None:
            raise RuntimeError("다른 작업이 실행 중입니다. 완료 후 다시 시도하세요.")
        job_id = uuid.uuid4().hex[:12]
        record: dict[str, Any] = {
            "id": job_id,
            "kind": kind,
            "status": "queued",
            "params": params,
            "created_at": _utc_now(),
            "started_at": None,
            "finished_at": None,
            "result": None,
            "error": None,
        }
        _jobs[job_id] = record
        _jobs_order.append(job_id)
        while len(_jobs_order) > _MAX_JOBS:
            old = _jobs_order.pop(0)
            _jobs.pop(old, None)

    def runner() -> None:
        with _lock:
            _jobs[job_id]["status"] = "running"
            _jobs[job_id]["started_at"] = _utc_now()
        try:
            result = _serialize_value(fn())
            with _lock:
                _jobs[job_id]["status"] = "done"
                _jobs[job_id]["result"] = result
                _jobs[job_id]["finished_at"] = _utc_now()
        except Exception as exc:
            with _lock:
                _jobs[job_id]["status"] = "failed"
                _jobs[job_id]["error"] = str(exc)
                _jobs[job_id]["finished_at"] = _utc_now()

    threading.Thread(target=runner, daemon=True, name=f"ops-{kind}-{job_id}").start()
    return {"job_id": job_id, "status": "queued"}


def read_ops_logs(limit: int = 200) -> list[dict[str, Any]]:
    path = OPS_LOG_PATH
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    out: list[dict[str, Any]] = []
    for line in lines[-limit:]:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def get_status() -> dict[str, Any]:
    train_count = len(list(config.TRAIN_DATA_DIR.glob("*.json")))
    infer_count = len(list(config.INFERENCE_INPUT_DIR.glob("*.json")))
    result_count = len(list(config.INFERENCE_RESULT_DIR.glob("*_result.json")))
    with _lock:
        running = _running_job()
    return {
        "defaults": {
            "facid": config.DEFAULT_FACID,
            "batchid": config.DEFAULT_BATCHID,
            "lookback_days": config.DEFAULT_TRAIN_LOOKBACK_DAYS,
            "default_ppo_steps": config.DEFAULT_PPO_STEPS,
            "horizon_hours": 12,
        },
        "artifacts": {
            "dispatch_model": str(config.MODEL_PATH),
            "dispatch_model_exists": config.MODEL_PATH.is_file(),
            "alloc_model": str(config.SAVED_MODELS_DIR / "ppo_alloc.zip"),
            "alloc_model_exists": (config.SAVED_MODELS_DIR / "ppo_alloc.zip").is_file(),
            "train_json_count": train_count,
            "inference_input_count": infer_count,
            "inference_result_count": result_count,
            "ops_log": str(OPS_LOG_PATH),
        },
        "busy": running is not None,
        "running_job": _public_job(running) if running else None,
    }


def _execute_export(req: ExportRequest) -> dict[str, Any]:
    from src.db.export import export_from_db, export_from_sample_rows, export_train_range

    if req.sample:
        path = export_from_sample_rows()
        return {"mode": "sample", "paths": [str(path)], "count": 1}

    if req.mode == "train_range":
        paths = export_train_range(
            req.from_timekey,
            req.to_timekey,
            req.lookback_days,
            req.horizon_hours,
            facid=req.facid,
            batchid=req.batchid,
        )
        return {
            "mode": "train_range",
            "paths": [str(p) for p in paths],
            "count": len(paths),
            "output_dir": str(config.TRAIN_DATA_DIR),
        }

    from src.db.adapter import resolve_timekey
    from src.utils.ops_log import log_ops

    fac = config.require_facid(req.facid)
    bid = config.require_batchid(req.batchid)
    rk = req.timekey or resolve_timekey(None, facid=fac)
    log_ops(
        "export.start",
        rule_timekey=rk,
        facid=fac,
        batchid=bid,
        batchid_like=f"%{bid}%",
        horizon_hours=req.horizon_hours,
        output="-",
        ops_log=OPS_LOG_PATH,
    )
    path = export_from_db(
        rk,
        horizon_hours=req.horizon_hours,
        facid=fac,
        batchid=bid,
    )
    log_ops("export.done", rule_timekey=rk, facid=fac, batchid=bid, output=path)
    return {"mode": "single", "rule_timekey": rk, "paths": [str(path)], "count": 1}


def _execute_infer(req: InferRequest) -> dict[str, Any]:
    from src.inference import run_infer

    out = run_infer(
        rule_timekey=req.timekey,
        facid=req.facid,
        batchid=req.batchid,
        horizon_hours=req.horizon_hours,
        skip_input_export=req.skip_input_export,
        write_db=req.write_db,
    )
    doc = out.pop("result_doc", None)
    serialized = _serialize_value(out)
    if isinstance(doc, dict):
        serialized["policy"] = doc.get("policy")
        serialized["guide_source"] = doc.get("guide", {}).get("source")
    return serialized


def _execute_train(req: TrainRequest) -> dict[str, Any]:
    from src.db.export import export_train_range
    from src.db.pipeline import load_train_problems_from_export
    from src.train import run_train

    export_count = 0
    if req.mode == "db_range":
        paths = export_train_range(
            req.from_timekey,
            req.to_timekey,
            req.lookback_days,
            req.horizon_hours,
            facid=req.facid,
            batchid=req.batchid,
        )
        export_count = len(paths)

    problems = load_train_problems_from_export()
    if not problems:
        raise ValueError(
            "학습 JSON 없음. DB 범위 export를 선택하거나 data/raw/train/ 에 JSON을 준비하세요."
        )

    model_path = run_train(problems=problems, ppo_steps=req.steps)
    return {
        "mode": req.mode,
        "export_count": export_count,
        "problem_count": len(problems),
        "steps": req.steps,
        "model_path": str(model_path),
    }


def start_export(req: ExportRequest) -> dict[str, Any]:
    return submit_job("export", req.model_dump(), lambda: _execute_export(req))


def start_infer(req: InferRequest) -> dict[str, Any]:
    return submit_job("infer", req.model_dump(), lambda: _execute_infer(req))


def start_train(req: TrainRequest) -> dict[str, Any]:
    return submit_job("train", req.model_dump(), lambda: _execute_train(req))
