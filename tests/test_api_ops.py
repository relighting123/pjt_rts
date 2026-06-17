import json
import time

import pytest
from fastapi.testclient import TestClient

from src.api import ops
from src.api.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_jobs():
    ops._jobs.clear()
    ops._jobs_order.clear()
    yield
    ops._jobs.clear()
    ops._jobs_order.clear()


def test_ops_status(client):
    r = client.get("/api/ops/status")
    assert r.status_code == 200
    body = r.json()
    assert "defaults" in body
    assert "artifacts" in body
    assert body["busy"] is False


def test_ops_logs_empty(client, tmp_path, monkeypatch):
    log_file = tmp_path / "ops.jsonl"
    monkeypatch.setattr("src.api.ops.OPS_LOG_PATH", log_file)
    r = client.get("/api/ops/logs")
    assert r.status_code == 200
    assert r.json()["logs"] == []


def test_ops_logs_reads_jsonl(client, tmp_path, monkeypatch):
    log_file = tmp_path / "ops.jsonl"
    log_file.write_text(
        json.dumps({"ts": "2026-01-01T00:00:00Z", "event": "infer.start", "facid": "ICPRB"})
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("src.api.ops.OPS_LOG_PATH", log_file)
    r = client.get("/api/ops/logs")
    assert r.status_code == 200
    assert r.json()["logs"][0]["event"] == "infer.start"


def test_ops_export_sample_job(client, monkeypatch):
    from src.api.schemas import ExportRequest

    def fake_execute(req: ExportRequest):
        return {"mode": "sample", "paths": ["/tmp/x.json"], "count": 1}

    monkeypatch.setattr(ops, "_execute_export", fake_execute)

    r = client.post("/api/ops/export", json={"sample": True})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    for _ in range(50):
        if ops.get_job(job_id)["status"] in ("done", "failed"):
            break
        time.sleep(0.05)

    job = ops.get_job(job_id)
    assert job["status"] == "done"
    assert job["result"]["count"] == 1


def test_ops_conflict_when_busy(client):
    ops._jobs["busy1"] = {
        "id": "busy1",
        "kind": "train",
        "status": "running",
        "params": {},
        "created_at": "2026-01-01T00:00:00Z",
        "started_at": "2026-01-01T00:00:00Z",
        "finished_at": None,
        "result": None,
        "error": None,
    }
    ops._jobs_order.append("busy1")
    r = client.post("/api/ops/infer", json={"facid": "ICPRB", "batchid": "B1"})
    assert r.status_code == 409


def test_ops_job_not_found(client):
    r = client.get("/api/ops/jobs/missing-id")
    assert r.status_code == 404
