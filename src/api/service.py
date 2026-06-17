"""평가 실행·캐시 + API 응답 view-model 빌더."""
from __future__ import annotations

import threading
from pathlib import Path

import config
from src import evaluate as eval_pipeline
from src.utils.json_io import load_problem
from src.simulation.domain.problem import ProblemInstance
from src.views.viewmodel import build_detail_payload, plan_achievement_for_env
from agents.model_store import load_dispatch_model, rl_status

_cache: dict[tuple[str, float], dict] = {}
_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def list_dataset_paths() -> dict[str, Path]:
    out: dict[str, Path] = {}
    for d in (config.TEST_DATA_DIR, config.INFERENCE_DATA_DIR):
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.json")):
            if p.stem.endswith("_result"):
                continue
            out.setdefault(p.stem, p)
    return out


def analyze(name: str, env_type: str = "dispatch") -> dict:
    paths = list_dataset_paths()
    if name not in paths:
        raise KeyError(name)
    path = paths[name]
    key = (str(path), path.stat().st_mtime, env_type)
    if key in _cache:
        return _cache[key]
    with _locks_guard:
        lock = _locks.setdefault(str(path) + env_type, threading.Lock())
    with lock:
        if key in _cache:
            return _cache[key]
        payload = _analyze_uncached(name, path, env_type)
        _cache[key] = payload
    return payload


def _analyze_uncached(name: str, path: Path, env_type: str = "dispatch") -> dict:
    problem = load_problem(path)
    result = eval_pipeline.evaluate_benchmark(problem, model=load_dispatch_model())
    status = rl_status(problem, result.get("rl") is not None)
    return build_detail_payload(name, problem, result, status, env_type=env_type)


def list_datasets() -> list[dict]:
    out = []
    for name, path in list_dataset_paths().items():
        kind = "benchmark" if path.parent == config.TEST_DATA_DIR else "inference"
        out.append({"name": name, "kind": kind})
    return out


def training_metrics(stage: str = "dispatch") -> list[dict]:
    from src.training.log_io import read_training_metrics
    return read_training_metrics(stage)


def summary(env_type: str = "dispatch") -> dict:
    rows = []
    for name in list_dataset_paths():
        a = analyze(name, env_type)
        h = a["algorithms"]["heuristic"]
        rl = a["algorithms"]["rl"]
        best = rl or h
        optimal = a["optimal"]
        rows.append({
            "name": name,
            "heuristic": plan_achievement_for_env(h, env_type),
            "rl": plan_achievement_for_env(rl, env_type) if rl else None,
            "optimal": optimal,
            "gap": (plan_achievement_for_env(best, env_type) - optimal)
            if (best and optimal is not None) else None,
            "heuristic_utilization": h["kpis"]["avg_utilization"] if h else None,
            "rl_utilization": rl["kpis"]["avg_utilization"] if rl else None,
            "heuristic_conversion_count": h["kpis"]["conversion_count"] if h else 0,
            "rl_conversion_count": rl["kpis"]["conversion_count"] if rl else 0,
            "avg_utilization": best["kpis"]["avg_utilization"] if best else None,
            "total_move": best["kpis"]["total_move"] if best else 0,
            "conversion_count": best["kpis"]["conversion_count"] if best else 0,
            "horizon_hours": a["meta"]["horizon_hours"],
            "task_count": a["meta"]["task_count"],
            "total_eqp": a["meta"]["total_eqp"],
            "has_real_equipments": a["meta"]["has_real_equipments"],
        })

    def _avg(key: str):
        vals = [r[key] for r in rows if r[key] is not None]
        return round(sum(vals) / len(vals), 4) if vals else None

    return {
        "rows": rows,
        "averages": {
            "heuristic": _avg("heuristic"),
            "rl": _avg("rl"),
            "optimal": _avg("optimal"),
            "gap": _avg("gap"),
            "avg_utilization": _avg("avg_utilization"),
            "avg_conversion_count": _avg("conversion_count"),
        },
    }
