"""평가 실행·캐시 + API 응답 view-model 빌더.

평가(evaluate_benchmark)는 CPU 바운드이므로 (경로, mtime) 키로 캐시한다.
다중 요청은 FastAPI 스레드풀에서 처리되고, 같은 데이터셋 동시 요청은
락으로 1회만 평가한다. 수평 확장은 uvicorn --workers N.
"""
from __future__ import annotations

import threading
from datetime import datetime, timedelta
from pathlib import Path

import config
from eqp_units import track_units
from report_output import avg_utilization, event_tm_for_hour, merge_assign_rows
from simulator import ProblemInstance, load_problem


_cache: dict[tuple[str, float], dict] = {}
_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()
_model_cache: dict = {}


def _parse_tm(s: str) -> datetime:
    return datetime.strptime(str(s)[:14].ljust(14, "0"), "%Y%m%d%H%M%S")


def _iso(s: str) -> str:
    return _parse_tm(s).isoformat()


def list_dataset_paths() -> dict[str, Path]:
    """이름 -> JSON 경로. 벤치마크 + 추론 입력(_result 제외)."""
    out: dict[str, Path] = {}
    for d in (config.TEST_DATA_DIR, config.INFERENCE_DATA_DIR):
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.json")):
            if p.stem.endswith("_result"):
                continue
            out.setdefault(p.stem, p)
    return out


def _load_rl_model():
    """ppo_dispatch.zip — 1회 로드 캐시. 미설치/없으면 None."""
    key = str(config.MODEL_PATH)
    if key in _model_cache:
        return _model_cache[key]
    model = None
    if Path(config.MODEL_PATH).exists():
        try:
            from sb3_contrib import MaskablePPO
            model = MaskablePPO.load(config.MODEL_PATH)
        except Exception:
            model = None
    _model_cache[key] = model
    return model


def _task_label(t) -> str:
    return f"{t.plan_prod_key}/{t.oper_id}"


def _gantt_rows(problem: ProblemInstance, assign_rows: list[dict], trace: list) -> list[dict]:
    """간트 세그먼트: RUN(병합 배치 구간) + CONV(전환중 구간)."""
    task_by_key = {(t.plan_prod_key, t.oper_id): t for t in problem.tasks}
    segments: list[dict] = []
    for r in merge_assign_rows(assign_rows):
        t = task_by_key.get((r["PLAN_PROD_KEY"], r.get("OPER_ID", "")))
        segments.append({
            "kind": "RUN",
            "eqp_id": r["EQP_ID"],
            "model": r["EQP_MODEL_CD"],
            "plan_prod_key": r["PLAN_PROD_KEY"],
            "oper_id": r.get("OPER_ID", ""),
            "batch_id": t.batch_id if t else "",
            "task": f"{r['PLAN_PROD_KEY']}/{r.get('OPER_ID', '')}",
            "start": _iso(r["START_TIME"]),
            "end": _iso(r["END_TIME"]),
            "qty": r["PRODUCE_QTY"],
        })
    _, conversions = track_units(problem, trace)
    for c in conversions:
        start_tm = event_tm_for_hour(problem.rule_timekey, c["hour"])
        end = _parse_tm(start_tm) + timedelta(hours=problem.switch_time_hours)
        from_t = problem.tasks[c["from_index"]]
        to_t = problem.tasks[c["to_index"]]
        segments.append({
            "kind": "CONV",
            "eqp_id": c["eqp_id"],
            "model": c["model"],
            "plan_prod_key": to_t.plan_prod_key,
            "oper_id": to_t.oper_id,
            "batch_id": to_t.batch_id,
            "task": f"{from_t.batch_id}→{to_t.batch_id}",
            "from_batch": from_t.batch_id,
            "to_batch": to_t.batch_id,
            "from_task": _task_label(from_t),
            "to_task": _task_label(to_t),
            "start": _iso(start_tm),
            "end": end.isoformat(),
            "qty": 0,
        })
    return segments


def _conversion_rows(conv_rows: list[dict]) -> list[dict]:
    """전환 예정 장비 정보 — RTS_EQPCONVPLAN 행을 UI용으로 축약."""
    out = []
    for r in conv_rows:
        out.append({
            "job_id": r["JOB_ID"],
            "eqp_id": r["EQP_ID"],
            "model": r["TESTER_EQP_MODEL_CD"],
            "conv_start": r["CONV_START_TM"],
            "conv_end": r["CONV_END_TM"],
            "conv_time": r["CONV_TIME"],
            "from_batch": f"{r['LOT_CD']}/{r['TEMPER_VAL']}" if r["TEMPER_VAL"] != "-" else r["LOT_CD"],
            "to_batch": f"{r['TO_LOT_CD']}/{r['TO_TEMPER_VAL']}" if r["TO_TEMPER_VAL"] != "-" else r["TO_LOT_CD"],
            "from_ppk": r["PLAN_PROD_ATTR_VAL"],
            "to_ppk": r["TO_PLAN_PROD_ATTR_VAL"],
            "status": r["PRCS_STAT_CD"],
        })
    return out


def _hourly_view(problem: ProblemInstance, hourly_stats: list[dict]) -> list[dict]:
    out = []
    for stat in hourly_stats:
        tm = event_tm_for_hour(problem.rule_timekey, stat["hour"])
        out.append({
            "hour": stat["hour"],
            "time": _iso(tm),
            "produce": sum(stat["hourly_produce"].values()),
            "cumulative": sum(stat["cumulative_produced"].values()),
            "util_rate": stat["util_rate"],
        })
    return out


def _algo_view(problem: ProblemInstance, result: dict, prefix: str = "") -> dict | None:
    def g(key: str, default=None):
        return result.get(f"{prefix}{key}" if prefix else key, default)

    achievement = result.get("rl") if prefix else result.get("heuristic")
    if achievement is None:
        return None
    hourly_stats = g("hourly_stats", []) or []
    per_task = result.get("rl_per_task" if prefix else "heuristic_per_task", {}) or {}
    assign_rows = g("assign_rows", []) or []
    conv_rows = g("conv_rows", []) or []
    trace = g("trace", []) or []
    util = g("avg_utilization")
    if util is None:
        util = avg_utilization(hourly_stats)
    total_move = (
        sum(hourly_stats[-1]["cumulative_produced"].values()) if hourly_stats else 0
    )
    return {
        "kpis": {
            "plan_achievement": float(achievement),
            "avg_utilization": float(util or 0.0),
            "total_move": int(total_move),
            "conversion_count": len(conv_rows),
            # 전환 호기 수 — _analyze_uncached에서 tracker 기준으로 갱신
            "converting_eqp_count": len({r["EQP_ID"] for r in conv_rows} - {"-"}),
        },
        "per_task": [
            {"task": k, "plan": v["plan"], "produced": v["produced"], "rate": v["rate"]}
            for k, v in per_task.items()
        ],
        "hourly": _hourly_view(problem, hourly_stats),
        "gantt": _gantt_rows(problem, assign_rows, trace),
        "conversions": _conversion_rows(conv_rows),
    }


def analyze(name: str, env_type: str = "dispatch") -> dict:
    """데이터셋 1건 평가 → UI payload (캐시)."""
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
    import test as report

    problem = load_problem(path)
    result = report.evaluate_benchmark(problem, model=_load_rl_model())

    heuristic_view = _algo_view(problem, result)
    rl_view = _algo_view(problem, result, prefix="rl_") if result.get("rl") is not None else None

    # 전환 예정 장비 수 KPI 보정 (가상 호기 포함, tracker 기준)
    for view, trace_key in ((heuristic_view, "trace"), (rl_view, "rl_trace")):
        if view is None:
            continue
        _, convs = track_units(problem, result.get(trace_key, []) or [])
        view["kpis"]["converting_eqp_count"] = len({c["eqp_id"] for c in convs})

    guide_rows = []
    from report_output import guide_allocation_rows
    for r in guide_allocation_rows(problem, result.get("guide_allocation", {})):
        guide_rows.append(r)

    return {
        "name": name,
        "meta": {
            "rule_timekey": problem.rule_timekey,
            "facid": problem.facid,
            "horizon_hours": problem.horizon_hours,
            "switch_time_hours": problem.switch_time_hours,
            "task_count": len(problem.tasks),
            "model_count": len(problem.models()),
            "total_eqp": sum(problem.eqp_qty.values()),
            "has_real_equipments": bool(problem.equipments),
            "note": problem.ground_truth.get("note", ""),
        },
        "tasks": [
            {
                "plan_prod_key": t.plan_prod_key,
                "oper_id": t.oper_id,
                "oper_seq": t.oper_seq,
                "batch_id": t.batch_id,
                "plan_qty": t.plan_qty,
                "init_wip": t.init_wip,
            }
            for t in problem.tasks
        ],
        "equipments": [
            {
                "eqp_id": e.eqp_id,
                "eqp_model": e.eqp_model,
                "batch_id": e.batch_id,
                "plan_prod_key": e.plan_prod_key,
                "oper_id": e.oper_id,
            }
            for e in problem.equipments
        ],
        "optimal": problem.ground_truth.get("plan_achievement"),
        "guide": guide_rows,
        "algorithms": {"heuristic": heuristic_view, "rl": rl_view},
    }


def list_datasets() -> list[dict]:
    out = []
    for name, path in list_dataset_paths().items():
        kind = "benchmark" if path.parent == config.TEST_DATA_DIR else "inference"
        out.append({"name": name, "kind": kind})
    return out


def summary(env_type: str = "dispatch") -> dict:
    """전체 데이터셋 비교."""
    rows = []
    for name in list_dataset_paths():
        a = analyze(name, env_type)
        h = a["algorithms"]["heuristic"]
        rl = a["algorithms"]["rl"]
        best = rl or h
        optimal = a["optimal"]
        rows.append({
            "name": name,
            "heuristic": h["kpis"]["plan_achievement"] if h else None,
            "rl": rl["kpis"]["plan_achievement"] if rl else None,
            "optimal": optimal,
            "gap": (best["kpis"]["plan_achievement"] - optimal)
            if (best and optimal is not None) else None,
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
