import pytest
from fastapi.testclient import TestClient

from src.api.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_runtime_config(tmp_path, monkeypatch):
    from src.api import ml

    cfg_file = tmp_path / "runtime_config.json"
    reg_file = tmp_path / "registry.json"
    monkeypatch.setattr(ml, "RUNTIME_CONFIG_PATH", cfg_file)
    monkeypatch.setattr(ml, "REGISTRY_PATH", reg_file)
    yield


def test_ml_config(client):
    r = client.get("/api/ml/config")
    assert r.status_code == 200
    body = r.json()
    assert body["ppo_steps"] == 50_000
    assert "paths" in body


def test_ml_config_patch(client):
    r = client.patch("/api/ml/config", json={"ppo_steps": 12000, "dwell_lambda": 0.25})
    assert r.status_code == 200
    assert r.json()["ppo_steps"] == 12000
    assert r.json()["dwell_lambda"] == 0.25


def test_ml_models_list(client):
    r = client.get("/api/ml/models")
    assert r.status_code == 200
    assert "models" in r.json()


def test_ml_evaluate_test_split(client):
    r = client.get("/api/ml/evaluate?split=test")
    assert r.status_code == 200
    body = r.json()
    assert body["split"] == "test"
    assert body["count"] >= 1
    assert "averages" in body


def test_ml_evaluate_validation_split(client):
    r = client.get("/api/ml/evaluate?split=validation")
    assert r.status_code == 200
    assert r.json()["split"] == "validation"


def test_ml_pipeline_status(client):
    r = client.get("/api/ml/pipeline")
    assert r.status_code == 200
    body = r.json()
    assert "test_json_count" in body
    assert "validation" in body or "test" in body


def test_ml_compare_requires_models(client):
    r = client.post("/api/ml/compare", json={"model_ids": ["missing-id"], "split": "test"})
    assert r.status_code == 200
    assert r.json()["models"][0]["error"] == "모델 없음"
