"""ML 파이프라인 API — 설정, 모델 레지스트리, 평가/비교."""
from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import config
from agents.model_store import clear_model_cache, dispatch_model_matches, load_dispatch_model
from src import evaluate as eval_pipeline
from src.utils.json_io import load_problem
from src.views.viewmodel import algo_view, plan_achievement_for_env

REGISTRY_PATH = config.MODELS_DIR / "registry.json"
RUNTIME_CONFIG_PATH = config.MODELS_DIR / "runtime_config.json"

# .env 전용 — runtime_config.json / UI PATCH 로 덮어쓰지 않음 (git 충돌 방지)
ENV_LOCKED_KEYS = frozenset({"max_tasks", "max_models", "metric_digits"})

SPLIT_DIRS: dict[str, Path] = {
    "validation": config.TRAIN_DATA_DIR,
    "train": config.TRAIN_DATA_DIR,
    "test": config.TEST_DATA_DIR,
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ensure_models_dir() -> None:
    config.MODELS_DIR.mkdir(parents=True, exist_ok=True)
    config.CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True)
    config.BEST_MODEL_DIR.mkdir(parents=True, exist_ok=True)


def _load_json(path: Path, default: dict) -> dict:
    if not path.is_file():
        return dict(default)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return dict(default)


def _save_json(path: Path, data: dict) -> None:
    _ensure_models_dir()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _default_registry() -> dict:
    return {"active_model_id": None, "models": {}}


def _registry() -> dict:
    reg = _load_json(REGISTRY_PATH, _default_registry())
    reg.setdefault("active_model_id", None)
    reg.setdefault("models", {})
    return reg


def _runtime_overrides() -> dict:
    return _load_json(RUNTIME_CONFIG_PATH, {})


def default_ml_config() -> dict[str, Any]:
    return {
        "ppo_steps": config.DEFAULT_PPO_STEPS,
        "bc_epochs": config.BC_EPOCHS,
        "bc_lr": config.BC_LR,
        "bc_loss_target": config.BC_LOSS_TARGET,
        "max_tasks": config.MAX_TASKS,
        "max_models": config.MAX_MODELS,
        "dwell_lambda": config.DWELL_LAMBDA,
        "alloc_lambda": config.ALLOC_LAMBDA,
        "dwell_obs": config.DWELL_OBS,
        "use_alloc_model": config.USE_ALLOC_MODEL,
        "guide_util_threshold": config.GUIDE_UTIL_THRESHOLD,
        "guide_band_pct": config.GUIDE_BAND_PCT,
        "horizon_hours": 12,
        "lookback_days": config.DEFAULT_TRAIN_LOOKBACK_DAYS,
        "metric_digits": config.UI_METRIC_DIGITS,
        "conv_groups": config.load_conv_groups(),
    }


def _patchable_keys() -> set[str]:
    return set(default_ml_config().keys()) - ENV_LOCKED_KEYS


def get_ml_config() -> dict[str, Any]:
    base = default_ml_config()
    overrides = {
        k: v for k, v in _runtime_overrides().items() if k in _patchable_keys()
    }
    base.update(overrides)
    base["env_locked"] = sorted(ENV_LOCKED_KEYS)
    base["paths"] = {
        "checkpoints": str(config.CHECKPOINTS_DIR),
        "best": str(config.BEST_MODEL_DIR),
        "active_dispatch": str(config.MODEL_PATH),
        "train_data": str(config.TRAIN_DATA_DIR),
        "test_data": str(config.TEST_DATA_DIR),
    }
    return base


def update_ml_config(updates: dict[str, Any]) -> dict[str, Any]:
    allowed = _patchable_keys()
    clean = {k: v for k, v in updates.items() if k in allowed}
    if "conv_groups" in clean and clean["conv_groups"] is not None:
        cg = clean["conv_groups"]
        if not isinstance(cg, dict):
            raise ValueError("conv_groups는 JSON 객체여야 합니다.")
        clean["conv_groups"] = {str(k): [str(x) for x in v] for k, v in cg.items()}
    if not clean:
        raise ValueError("변경 가능한 파라미터가 없습니다.")
    current = {k: v for k, v in _runtime_overrides().items() if k in allowed}
    current.update(clean)
    _save_json(RUNTIME_CONFIG_PATH, current)
    return get_ml_config()


def _model_meta(path: Path, model_id: str, *, registered: bool = False, name: str | None = None) -> dict:
    stat = path.stat()
    reg = _registry()
    is_active = str(path.resolve()) == Path(config.MODEL_PATH).resolve()
    active_id = reg.get("active_model_id")
    if active_id and active_id in reg["models"]:
        is_active = reg["models"][active_id].get("path") == str(path)
    return {
        "id": model_id,
        "name": name or path.stem,
        "path": str(path),
        "filename": path.name,
        "size_bytes": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "registered": registered,
        "is_active": is_active,
        "exists": path.is_file(),
    }


def list_models() -> list[dict]:
    _ensure_models_dir()
    out: dict[str, dict] = {}
    reg = _registry()

    for mid, row in reg.get("models", {}).items():
        p = Path(row.get("path", ""))
        if p.is_file():
            out[mid] = {
                **_model_meta(p, mid, registered=True, name=row.get("name")),
                "registered_at": row.get("registered_at"),
                "notes": row.get("notes", ""),
                "source_path": row.get("source_path"),
                "final_training_reward": row.get("final_training_reward"),
            }

    for directory in (config.CHECKPOINTS_DIR, config.BEST_MODEL_DIR):
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.zip")):
            mid = f"file:{path.name}"
            if mid not in out:
                out[mid] = _model_meta(path, mid, registered=False)

    if config.MODEL_PATH.is_file():
        mid = "active:checkpoint"
        if mid not in out and str(config.MODEL_PATH) not in {m["path"] for m in out.values()}:
            out[mid] = _model_meta(config.MODEL_PATH, mid, registered=False, name="현재 활성 모델")

    return sorted(out.values(), key=lambda m: m.get("modified_at", ""), reverse=True)


def _final_training_reward() -> float | None:
    from src.training.log_io import read_training_metrics

    points = read_training_metrics("dispatch")
    ppo = [p for p in points if p.get("phase") == "ppo" and p.get("mean_reward") is not None]
    if not ppo:
        bc = [p for p in points if p.get("mean_reward") is not None]
        return float(bc[-1]["mean_reward"]) if bc else None
    return float(ppo[-1]["mean_reward"])


def register_model(
    *,
    source_path: str | None = None,
    name: str | None = None,
    notes: str = "",
    model_id: str | None = None,
) -> dict:
    _ensure_models_dir()
    src = Path(source_path) if source_path else config.MODEL_PATH
    if not src.is_file():
        raise ValueError(f"모델 파일 없음: {src}")

    mid = model_id or uuid.uuid4().hex[:10]
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest_name = f"ppo_dispatch_{stamp}.zip"
    dest = config.BEST_MODEL_DIR / dest_name
    shutil.copy2(src, dest)

    reg = _registry()
    reg["models"][mid] = {
        "id": mid,
        "name": name or f"등록 모델 {stamp}",
        "path": str(dest),
        "source_path": str(src),
        "registered_at": _utc_now(),
        "notes": notes,
        "final_training_reward": _final_training_reward(),
    }
    reg["active_model_id"] = mid
    _save_json(REGISTRY_PATH, reg)

    shutil.copy2(dest, config.MODEL_PATH)
    clear_model_cache()
    return {"model": reg["models"][mid], "activated": True}


def activate_model(model_id: str) -> dict:
    reg = _registry()
    row = reg.get("models", {}).get(model_id)
    if row is None:
        for m in list_models():
            if m["id"] == model_id:
                path = Path(m["path"])
                if not path.is_file():
                    raise ValueError(f"모델 파일 없음: {path}")
                shutil.copy2(path, config.MODEL_PATH)
                clear_model_cache()
                reg["active_model_id"] = model_id
                _save_json(REGISTRY_PATH, reg)
                return {"model_id": model_id, "path": str(config.MODEL_PATH), "activated": True}
        raise ValueError(f"모델 없음: {model_id}")

    path = Path(row["path"])
    if not path.is_file():
        raise ValueError(f"모델 파일 없음: {path}")
    shutil.copy2(path, config.MODEL_PATH)
    reg["active_model_id"] = model_id
    _save_json(REGISTRY_PATH, reg)
    clear_model_cache()
    return {"model_id": model_id, "path": str(config.MODEL_PATH), "activated": True}


def dataset_paths_for_split(split: str) -> dict[str, Path]:
    if split not in SPLIT_DIRS:
        raise ValueError(f"split must be one of: {', '.join(SPLIT_DIRS)}")
    directory = SPLIT_DIRS[split]
    if not directory.is_dir():
        return {}
    return {p.stem: p for p in sorted(directory.glob("*.json"))}


def _episode_reward(problem, model) -> float | None:
    if model is None or not dispatch_model_matches(model, problem):
        return None
    from envs.dispatch_env import DispatchEnv
    from src.stages.allocation.use_case import allocate
    from src.utils.rows import guide_allocation_rows

    guide = allocate(problem)
    target_alloc: dict[tuple[str, int], float] = {}
    for row in guide_allocation_rows(problem, guide):
        task_idx = next(
            (i for i, t in enumerate(problem.tasks) if f"{t.plan_prod_key}/{t.oper_id}" == row["task"]),
            None,
        )
        if task_idx is not None:
            target_alloc[(row["model"], task_idx)] = float(row["target_count"])

    env = DispatchEnv(
        problem,
        max_tasks=config.MAX_TASKS,
        max_models=config.MAX_MODELS,
        dwell_lambda=config.DWELL_LAMBDA,
        alloc_lambda=config.ALLOC_LAMBDA,
        target_allocation=target_alloc,
        dwell_obs=config.DWELL_OBS,
        guide_util_threshold=config.GUIDE_UTIL_THRESHOLD,
        guide_band_pct=config.GUIDE_BAND_PCT,
    )
    obs, _ = env.reset()
    total = 0.0
    terminated = False
    while not terminated:
        action, _ = model.predict(obs, action_masks=env.action_masks())
        obs, reward, terminated, _, _ = env.step(int(action))
        total += float(reward)
    return round(total, 6)


def _kpi_from_view(view: dict | None, env_type: str) -> dict | None:
    if view is None:
        return None
    return {
        "plan_achievement": plan_achievement_for_env(view, env_type),
        "avg_utilization": float(view["kpis"]["avg_utilization"]),
        "conversion_count": int(view["kpis"]["conversion_count"]),
    }


def _eval_row(name: str, problem, model, env_type: str = "dispatch") -> dict:
    result = eval_pipeline.evaluate_benchmark(problem, model=model)
    h_view = algo_view(problem, result)
    rl_view = algo_view(problem, result, prefix="rl_") if result.get("rl") is not None else None
    rl_reward = _episode_reward(problem, model) if rl_view else None

    return {
        "dataset": name,
        "optimal": result.get("optimal"),
        "heuristic": _kpi_from_view(h_view, env_type),
        "rl": _kpi_from_view(rl_view, env_type),
        "rl_episode_reward": rl_reward,
        "rl_available": rl_view is not None,
    }


def _aggregate(rows: list[dict], key: str, subkey: str) -> float | None:
    vals = []
    for row in rows:
        block = row.get(key)
        if block and block.get(subkey) is not None:
            vals.append(float(block[subkey]))
    return round(sum(vals) / len(vals), 4) if vals else None


def _aggregate_reward(rows: list[dict]) -> float | None:
    vals = [float(r["rl_episode_reward"]) for r in rows if r.get("rl_episode_reward") is not None]
    return round(sum(vals) / len(vals), 4) if vals else None


def evaluate_split(
    split: str,
    *,
    model_path: str | None = None,
    env_type: str = "dispatch",
) -> dict:
    paths = dataset_paths_for_split(split)
    if not paths:
        return {"split": split, "count": 0, "rows": [], "averages": {}}

    path = Path(model_path) if model_path else config.MODEL_PATH
    model = load_dispatch_model(path) if path.is_file() else None

    rows = []
    for name, json_path in paths.items():
        problem = load_problem(json_path)
        rows.append(_eval_row(name, problem, model, env_type=env_type))

    averages = {
        "heuristic_plan_achievement": _aggregate(rows, "heuristic", "plan_achievement"),
        "rl_plan_achievement": _aggregate(rows, "rl", "plan_achievement"),
        "heuristic_utilization": _aggregate(rows, "heuristic", "avg_utilization"),
        "rl_utilization": _aggregate(rows, "rl", "avg_utilization"),
        "rl_episode_reward": _aggregate_reward(rows),
        "optimal": round(
            sum(float(r["optimal"]) for r in rows if r.get("optimal") is not None)
            / max(1, sum(1 for r in rows if r.get("optimal") is not None)),
            4,
        )
        if any(r.get("optimal") is not None for r in rows)
        else None,
    }

    return {
        "split": split,
        "model_path": str(path) if path.is_file() else None,
        "model_loaded": model is not None,
        "count": len(rows),
        "rows": rows,
        "averages": averages,
    }


def compare_models(model_ids: list[str], split: str = "test", env_type: str = "dispatch") -> dict:
    catalog = {m["id"]: m for m in list_models()}
    comparisons = []
    for mid in model_ids:
        meta = catalog.get(mid)
        if meta is None:
            comparisons.append({"model_id": mid, "error": "모델 없음"})
            continue
        path = meta["path"]
        ev = evaluate_split(split, model_path=path, env_type=env_type)
        comparisons.append({
            "model_id": mid,
            "name": meta.get("name"),
            "path": path,
            "registered": meta.get("registered", False),
            "is_active": meta.get("is_active", False),
            "averages": ev["averages"],
            "count": ev["count"],
        })

    return {"split": split, "env_type": env_type, "models": comparisons}


def pipeline_status() -> dict:
    cfg = get_ml_config()
    models = list_models()
    reg = _registry()
    train_eval = evaluate_split("train", env_type="dispatch")
    test_eval = evaluate_split("test", env_type="dispatch")
    from src.training.log_io import read_training_metrics

    metrics = read_training_metrics("dispatch")
    return {
        "config": cfg,
        "models_count": len(models),
        "active_model_id": reg.get("active_model_id"),
        "active_model_exists": config.MODEL_PATH.is_file(),
        "train_json_count": len(dataset_paths_for_split("train")),
        "test_json_count": len(dataset_paths_for_split("test")),
        "training_points": len(metrics),
        "validation": train_eval.get("averages"),
        "test": test_eval.get("averages"),
    }
