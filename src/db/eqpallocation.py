"""RTS_EQPALLOCATION_INF/HIS 행 변환 헬퍼."""
from __future__ import annotations

import config
from src.simulation.domain.problem import ProblemInstance

_DASH = "-"
_LOG_MAX_LEN = 4000


def guide_source_to_mode_typ(guide_source: str) -> str:
    """가이드 산출 방식 → MODE_TYP (AI=RL, 그 외=Heuristic)."""
    return "RL" if guide_source == "ALLOC_RL" else "Heuristic"


def allocation_metrics(
    problem: ProblemInstance,
    task_index: int,
    model: str,
    target_eqp_cnt: int,
) -> tuple[int, int, float, str]:
    """PLAN_QTY / CAPA_QTY / ACHIVE_RATE / LOG_INF_VAL (공정×모델 단위)."""
    task = problem.tasks[task_index]
    plan_qty = int(task.plan_qty)
    horizon = int(problem.horizon_hours)
    uph = problem.uph_of(model, task_index)
    target_cnt = int(target_eqp_cnt)

    if uph is None:
        capa_qty = 0
        capa_expr = "CAPA_QTY=0 (EQUIP_UPH 없음)"
    elif target_cnt <= 0:
        capa_qty = 0
        capa_expr = (
            f"CAPA_QTY=TARGET_EQP_CNT({target_cnt})*EQUIP_UPH({float(uph):g})"
            f"*HORIZON_H({horizon})=0"
        )
    else:
        capa_qty = int(target_cnt * float(uph) * float(horizon))
        capa_expr = (
            f"CAPA_QTY=TARGET_EQP_CNT({target_cnt})*EQUIP_UPH({float(uph):g})"
            f"*HORIZON_H({horizon})={capa_qty}"
        )

    if plan_qty <= 0:
        achive_rate = 1.0
        rate_expr = "ACHIVE_RATE=1.0000 (PLAN_QTY=0)"
    else:
        achive_rate = round(min(capa_qty / plan_qty, 1.0), 4)
        rate_expr = f"ACHIVE_RATE=min(CAPA_QTY/PLAN_QTY,1)={achive_rate:.4f}"

    log_val = (
        f"PLAN_QTY=EXEC_D0_PLAN({plan_qty}); "
        f"{capa_expr}; "
        f"{rate_expr}; "
        f"TASK={task.plan_prod_key}/{task.oper_id}; "
        f"EQP_MODEL={model}"
    )
    if len(log_val) > _LOG_MAX_LEN:
        log_val = log_val[: _LOG_MAX_LEN - 3] + "..."
    return plan_qty, capa_qty, achive_rate, log_val


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
        target_cnt = int(target)
        plan_qty, capa_qty, achive_rate, log_val = allocation_metrics(
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
            "LOG_INF_VAL": log_val,
            "CRT_USER_ID": sys_id,
        })
    return rows
