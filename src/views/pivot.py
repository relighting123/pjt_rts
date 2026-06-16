"""AllocEnv 피벗 테이블 projection."""
from __future__ import annotations

from src.simulation.domain.problem import ProblemInstance


def static_task_rate(problem: ProblemInstance, guide_allocation: dict, task_index: int) -> tuple[int, float]:
    """정적 달성률.

    - time_cap(댓수×UPD×Horizon) < 계획 → time_cap / 계획  (시간 한계)
    - time_cap ≥ 계획 → instant_cap(댓수×UPD) / 계획  (배분 밀도)
    """
    complete = problem.complete_guide_allocation(guide_allocation)
    t = problem.tasks[task_index]
    time_cap = 0.0
    instant_cap = 0.0
    for model in problem.models():
        uph = problem.uph_of(model, task_index)
        if uph is None:
            continue
        cnt = int(complete.get((model, task_index), 0))
        instant_cap += cnt * float(uph)
        time_cap += cnt * float(uph) * float(problem.horizon_hours)
    plan = float(t.plan_qty)
    if plan <= 0:
        return 0, 1.0
    if time_cap < plan:
        produced = int(time_cap)
        rate = min(time_cap / plan, 1.0)
    else:
        produced = int(min(plan, instant_cap))
        rate = min(instant_cap / plan, 1.0)
    return produced, float(rate)


def aggregate_static_rate(pivot: dict) -> float:
    rows = pivot.get("rows", [])
    if not rows:
        return 0.0
    return sum(float(r["rate"]) for r in rows) / len(rows)


def allocation_pivot(
    problem: ProblemInstance,
    guide_allocation: dict,
    per_task: dict | None = None,
) -> dict:
    complete = problem.complete_guide_allocation(guide_allocation)
    models = sorted(problem.models())
    per_task = per_task or {}
    rows = []
    for ti, t in enumerate(problem.tasks):
        task_key = f"{t.plan_prod_key}/{t.oper_id}"
        counts: dict[str, int | None] = {}
        uphs: dict[str, float | None] = {}
        for model in models:
            uph = problem.uph_of(model, ti)
            if uph is None:
                counts[model] = None
                uphs[model] = None
            else:
                counts[model] = int(complete.get((model, ti), 0))
                uphs[model] = float(uph)
        produced, rate = static_task_rate(problem, guide_allocation, ti)
        dynamic = per_task.get(task_key, {})
        rows.append({
            "task": task_key,
            "plan_prod_key": t.plan_prod_key,
            "oper_id": t.oper_id,
            "counts": counts,
            "uphs": uphs,
            "plan": int(t.plan_qty),
            "produced": produced,
            "rate": rate,
            "dynamic_produced": int(dynamic.get("produced", 0)),
            "dynamic_rate": float(dynamic.get("rate", 0.0)),
        })
    return {"models": models, "rows": rows}
