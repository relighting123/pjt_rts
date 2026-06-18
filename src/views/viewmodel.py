"""API/UI view-model projection."""
from __future__ import annotations

from datetime import datetime

from src.utils.eqp_units import track_units
from src.utils.rows import avg_utilization, event_tm_for_hour, guide_allocation_rows
from src.simulation.domain.problem import ProblemInstance
from src.views.gantt import gantt_rows
from src.views.pivot import aggregate_static_rate, allocation_pivot


def _parse_tm(s: str) -> datetime:
    return datetime.strptime(str(s)[:14].ljust(14, "0"), "%Y%m%d%H%M%S")


def _iso(s: str) -> str:
    return _parse_tm(s).isoformat()


def _conversion_rows(conv_rows: list[dict]) -> list[dict]:
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


def algo_view(problem: ProblemInstance, result: dict, prefix: str = "") -> dict | None:
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
            "converting_eqp_count": len({r["EQP_ID"] for r in conv_rows} - {"-"}),
        },
        "per_task": [
            {"task": k, "plan": v["plan"], "produced": v["produced"], "rate": v["rate"]}
            for k, v in per_task.items()
        ],
        "hourly": _hourly_view(problem, hourly_stats),
        "gantt": gantt_rows(problem, assign_rows, trace),
        "conversions": _conversion_rows(conv_rows),
        "allocation_pivot": allocation_pivot(
            problem, result.get("guide_allocation", {}), per_task,
        ),
    }


def _attach_static_kpis(view: dict | None) -> None:
    if view is None:
        return
    pivot = view.get("allocation_pivot") or {}
    view["kpis"]["static_plan_achievement"] = aggregate_static_rate(pivot)


def plan_achievement_for_env(view: dict | None, env_type: str = "dispatch") -> float | None:
    if view is None:
        return None
    if env_type == "alloc":
        return float(view["kpis"].get("static_plan_achievement", 0.0))
    return float(view["kpis"]["plan_achievement"])


def build_detail_payload(name: str, problem: ProblemInstance, result: dict,
                         rl_status: dict, env_type: str = "dispatch") -> dict:
    heuristic_view = algo_view(problem, result)
    rl_view = algo_view(problem, result, prefix="rl_") if result.get("rl") is not None else None

    for view in (heuristic_view, rl_view):
        _attach_static_kpis(view)

    for view, trace_key in ((heuristic_view, "trace"), (rl_view, "rl_trace")):
        if view is None:
            continue
        _, convs = track_units(problem, result.get(trace_key, []) or [])
        view["kpis"]["converting_eqp_count"] = len({c["eqp_id"] for c in convs})

    guide_rows = list(guide_allocation_rows(problem, result.get("guide_allocation", {})))

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
        "init_assign": [
            {
                "eqp_model": model,
                "plan_prod_key": problem.tasks[ti].plan_prod_key,
                "oper_id": problem.tasks[ti].oper_id,
                "count": int(cnt),
            }
            for (model, ti), cnt in sorted(problem.init_assign.items())
            if cnt > 0
        ],
        "optimal": problem.ground_truth.get("plan_achievement"),
        "rl_status": rl_status,
        "guide": guide_rows,
        "env_type": env_type,
        "algorithms": {"heuristic": heuristic_view, "rl": rl_view},
    }
