"""RTS_EQPALLOCATION_INF/HIS 행 변환 헬퍼."""
from __future__ import annotations

import config
from src.simulation.domain.problem import ProblemInstance

_DASH = "-"


def guide_source_to_mode_typ(guide_source: str) -> str:
    """가이드 산출 방식 → MODE_TYP (AI=RL, 그 외=Heuristic)."""
    return "RL" if guide_source == "ALLOC_RL" else "Heuristic"


def allocation_his_metrics(
    problem: ProblemInstance,
    task_index: int,
    model: str,
    target_eqp_cnt: int,
) -> tuple[int, int, float]:
    """HIS 전용 PLAN_QTY / CAPA_QTY / ACHIVE_RATE (공정×모델 단위)."""
    plan_qty = int(problem.tasks[task_index].plan_qty)
    uph = problem.uph_of(model, task_index)
    if uph is None or target_eqp_cnt <= 0:
        capa_qty = 0
    else:
        capa_qty = int(target_eqp_cnt * float(uph) * float(problem.horizon_hours))
    if plan_qty <= 0:
        achive_rate = 1.0
    else:
        achive_rate = round(min(capa_qty / plan_qty, 1.0), 4)
    return plan_qty, capa_qty, achive_rate


def build_eqpallocation_rows(
    problem: ProblemInstance,
    guide_allocation: dict,
    guide_source: str = "ANALYTIC",
    sys_id: str | None = None,
    *,
    facid: str | None = None,
) -> list[dict]:
    """공정×모델 가이드 배분 → RTS_EQPALLOCATION_INF/HIS 행 (0 포함).

    HIS 전용 PLAN_QTY/CAPA_QTY/ACHIVE_RATE는 row dict에 포함되며
    insert_eqpallocation(INF) SQL 바인드에서 자동 제외된다.
    """
    sys_id = sys_id or config.SYS_ID
    fac = facid or problem.facid or _DASH
    mode_typ = guide_source_to_mode_typ(guide_source)
    complete = problem.complete_guide_allocation(guide_allocation)
    rows: list[dict] = []
    for (model, ti), target in sorted(complete.items(), key=lambda x: (x[0][1], x[0][0])):
        task = problem.tasks[ti]
        target_cnt = int(target)
        plan_qty, capa_qty, achive_rate = allocation_his_metrics(
            problem, ti, model, target_cnt,
        )
        rows.append({
            "FAC_ID": fac,
            "RULE_TIMEKEY": problem.rule_timekey,
            "BATCH_ID": task.allocation_batch_id(),
            "PLAN_PROD_KEY": task.plan_prod_key,
            "OPER_ID": task.oper_id,
            "EQP_MODEL_CD": model,
            "TARGET_EQP_CNT": target_cnt,
            "CUR_EQP_CNT": int(problem.init_assign.get((model, ti), 0)),
            "MODE_TYP": mode_typ,
            "PLAN_QTY": plan_qty,
            "CAPA_QTY": capa_qty,
            "ACHIVE_RATE": achive_rate,
            "CRT_USER_ID": sys_id,
        })
    return rows
