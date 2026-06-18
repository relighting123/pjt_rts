import io
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


def test_health_reports_ops(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["ops"] is True


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


def test_ops_train_local_job(client, monkeypatch):
    from src.api.schemas import TrainRequest

    captured: list[TrainRequest] = []

    def fake_execute(req: TrainRequest):
        captured.append(req)
        return {
            "mode": req.mode,
            "export_count": 0,
            "problem_count": 2,
            "steps": req.steps,
            "facid": req.facid,
            "batchid": req.batchid,
            "conv_groups": req.conv_groups,
            "model_path": "/tmp/model.zip",
        }

    monkeypatch.setattr(ops, "_execute_train", fake_execute)

    r = client.post(
        "/api/ops/train",
        json={
            "mode": "local",
            "steps": 100,
            "facid": "ICPRB",
            "batchid": "B2",
            "conv_groups": {"G1": ["B1", "B2"]},
        },
    )
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    for _ in range(50):
        if ops.get_job(job_id)["status"] in ("done", "failed"):
            break
        time.sleep(0.05)

    job = ops.get_job(job_id)
    assert job["status"] == "done"
    assert job["result"]["problem_count"] == 2
    assert captured[0].facid == "ICPRB"
    assert captured[0].batchid == "B2"
    assert captured[0].conv_groups == {"G1": ["B1", "B2"]}


def test_ops_infer_passes_conv_groups(client, monkeypatch):
    from src.api.schemas import InferRequest

    captured: list[InferRequest] = []

    def fake_execute(req: InferRequest):
        captured.append(req)
        return {
            "rule_timekey": "2026010100",
            "facid": req.facid,
            "batchid": req.batchid,
            "conv_groups": req.conv_groups,
            "result_path": "/tmp/result.json",
        }

    monkeypatch.setattr(ops, "_execute_infer", fake_execute)

    r = client.post(
        "/api/ops/infer",
        json={
            "facid": "ICPRB",
            "batchid": "B3",
            "conv_groups": {"G1": ["B1", "B2", "B3"]},
        },
    )
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    for _ in range(50):
        if ops.get_job(job_id)["status"] in ("done", "failed"):
            break
        time.sleep(0.05)

    job = ops.get_job(job_id)
    assert job["status"] == "done"
    assert captured[0].facid == "ICPRB"
    assert captured[0].batchid == "B3"
    assert captured[0].conv_groups == {"G1": ["B1", "B2", "B3"]}


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


def test_is_pipe_error_detects_broken_pipe():
    assert ops._is_pipe_error(BrokenPipeError())
    assert ops._is_pipe_error(OSError(109, "The pipe has been ended"))
    assert not ops._is_pipe_error(ValueError("other"))


def test_run_job_callable_captures_stdout():
    def fn():
        print("hello-train-log")
        return {"ok": True}

    result, captured = ops._run_job_callable("train", fn)
    assert result == {"ok": True}
    assert "hello-train-log" in captured


def test_run_job_callable_train_tees_to_real_stdio(monkeypatch):
  import sys

  lines: list[str] = []

  class FakeStream(io.StringIO):
      def write(self, s):
          lines.append(s)
          return super().write(s)

      def flush(self):
          pass

  fake = FakeStream()
  monkeypatch.setattr(sys, "stdout", fake)
  monkeypatch.setattr(sys, "stderr", fake)

  def fn():
      print("tee-visible", flush=True)
      return {"ok": True}

  result, captured = ops._run_job_callable("train", fn)
  assert result == {"ok": True}
  assert "tee-visible" in captured
  assert any("tee-visible" in line for line in lines)
