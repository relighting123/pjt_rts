"""재공(WIP) 요약 — 제품별 집계."""
from __future__ import annotations

from src.simulation.domain.problem import ProblemInstance


def wip_product_summary(
    problem: ProblemInstance,
    final_wip: dict[int, int] | None = None,
) -> list[dict]:
    """제품(plan_prod_key)별 가용·잔여 재공."""
    products: dict[str, dict] = {}
    for i, t in enumerate(problem.tasks):
        pk = t.plan_prod_key
        if pk not in products:
            products[pk] = {
                "plan_prod_key": pk,
                "init_wip": 0,
                "remaining_wip": 0,
                "plan_qty": 0,
            }
        products[pk]["init_wip"] += int(t.init_wip)
        products[pk]["plan_qty"] += int(t.plan_qty)
        if final_wip is not None:
            products[pk]["remaining_wip"] += int(final_wip.get(i, 0))
        else:
            products[pk]["remaining_wip"] += int(t.init_wip)
    out = []
    for row in products.values():
        row["consumed_wip"] = max(0, row["init_wip"] - row["remaining_wip"])
        out.append(row)
    return sorted(out, key=lambda r: r["plan_prod_key"])
