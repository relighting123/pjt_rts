"""간트차트 projection."""
from __future__ import annotations

from datetime import datetime, timedelta

from src.utils.eqp_units import track_units
from src.utils.rows import event_tm_for_hour, merge_assign_rows
from src.simulation.domain.problem import ProblemInstance


def _parse_tm(s: str) -> datetime:
    return datetime.strptime(str(s)[:14].ljust(14, "0"), "%Y%m%d%H%M%S")


def _iso(s: str) -> str:
    return _parse_tm(s).isoformat()


def _task_label(t) -> str:
    return f"{t.plan_prod_key}/{t.oper_id}"


def gantt_rows(problem: ProblemInstance, assign_rows: list[dict], trace: list) -> list[dict]:
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
