"""RTS_EQPALLOCATION_INF/HIS 행 변환 헬퍼."""
from __future__ import annotations

import config
from simulator import ProblemInstance

_DASH = "-"


def guide_source_to_mode_typ(guide_source: str) -> str:
    """가이드 산출 방식 → MODE_TYP (AI=RL, 그 외=Heuristic)."""
    return "RL" if guide_source == "ALLOC_RL" else "Heuristic"


def build_eqpallocation_rows(
    problem: ProblemInstance,
    guide_allocation: dict,
    guide_source: str = "ANALYTIC",
    sys_id: str | None = None,
    *,
    facid: str | None = None,
) -> list[dict]:
    """공정×모델 가이드 배분 → RTS_EQPALLOCATION_INF/HIS 행 (0 포함)."""
    sys_id = sys_id or config.SYS_ID
    fac = facid or problem.facid or _DASH
    mode_typ = guide_source_to_mode_typ(guide_source)
    complete = problem.complete_guide_allocation(guide_allocation)
    rows: list[dict] = []
    for (model, ti), target in sorted(complete.items(), key=lambda x: (x[0][1], x[0][0])):
        task = problem.tasks[ti]
        rows.append({
            "FAC_ID": fac,
            "RULE_TIMEKEY": problem.rule_timekey,
            "BATCH_ID": task.batch_id,
            "PLAN_PROD_KEY": task.plan_prod_key,
            "OPER_ID": task.oper_id,
            "EQP_MODEL_CD": model,
            "TARGET_EQP_CNT": int(target),
            "CUR_EQP_CNT": int(problem.init_assign.get((model, ti), 0)),
            "MODE_TYP": mode_typ,
            "CRT_USER_ID": sys_id,
        })
    return rows
