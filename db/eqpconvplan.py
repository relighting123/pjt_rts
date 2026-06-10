"""RTS_EQPCONVPLAN_INF/HIS 행 변환 헬퍼."""
from __future__ import annotations

from datetime import datetime, timedelta

from simulator import Move, ProblemInstance

_DASH = "-"
_RTS_USER = "RTS"
_REASON_CD = "RTS-001"
_REASON_CTN = "테스트 데이터"


def split_batch_lot_temper(batch_id: str) -> tuple[str, str]:
    """BATCH_ID → LOT_CD(앞) / TEMPER_VAL(뒤). 슬래시 없으면 뒤는 '-'."""
    text = str(batch_id or "").strip()
    if "/" in text:
        lot, temper = text.split("/", 1)
        return lot or _DASH, temper or _DASH
    return text or _DASH, _DASH


def conv_start_end_tm(event_tm_16: str) -> tuple[str, str]:
    """16자 EVENT_TM → CONV_START_TM/END_TM (yyyyMMddHHmm, +1h)."""
    s = str(event_tm_16).ljust(16, "0")[:16]
    dt = datetime.strptime(s[:14], "%Y%m%d%H%M%S")
    start = dt.strftime("%Y%m%d%H%M")
    end = (dt + timedelta(hours=1)).strftime("%Y%m%d%H%M")
    return start, end


def build_eqpconvplan_rows(
    problem: ProblemInstance,
    trace: list,
    *,
    facid: str | None = None,
) -> list[dict]:
    """batch 전환 이동 → RTS_EQPCONVPLAN_INF/HIS 행.

    problem.equipments(실제 호기 명단)가 있으면 전환 호기 EQP_ID·모델을 채운다.
    """
    from eqp_units import track_units

    rk = problem.rule_timekey
    fac = facid or problem.facid or _DASH
    rows: list[dict] = []
    seq = 0
    has_real_eqp = bool(problem.equipments)
    # track_units conversions는 아래 루프와 동일 순서(batch 전환 이동만)로 생성됨
    _, conversions = track_units(problem, trace)

    for hour, applied_moves, _snapshot in trace:
        event_tm = _event_tm_for_hour(rk, hour)
        conv_start, conv_end = conv_start_end_tm(event_tm)
        for mv in applied_moves:
            if not isinstance(mv, Move):
                continue
            from_batch = problem.batch_of(mv.from_index)
            to_batch = problem.batch_of(mv.to_index)
            if from_batch == to_batch:
                continue
            from_task = problem.tasks[mv.from_index]
            to_task = problem.tasks[mv.to_index]
            from_lot, from_temper = split_batch_lot_temper(from_batch)
            to_lot, to_temper = split_batch_lot_temper(to_batch)
            conv = conversions[seq] if seq < len(conversions) else None
            eqp_id = conv["eqp_id"] if (has_real_eqp and conv) else _DASH
            eqp_model = mv.model if has_real_eqp else _DASH
            seq += 1
            rows.append({
                "FAC_ID": fac,
                "RULE_TIMEKEY": rk,
                "PRCS_STAT_CD": "WAIT",
                "JOB_ID": f"CONV_{seq:03d}_{rk}",
                "RTS_GBN_CD": "RTS",
                "EQP_ID": eqp_id,
                "EQP_MODEL_CD": eqp_model,
                "TESTER_EQP_MODEL_CD": mv.model,
                "CONV_START_TM": conv_start,
                "CONV_END_TM": conv_end,
                "CONV_TIME": 1,
                "LOT_CD": from_lot,
                "PRB_CARD_NO": _DASH,
                "TEMPER_VAL": from_temper,
                "PLAN_PROD_ATTR_VAL": from_task.plan_prod_key,
                "TO_LOT_CD": to_lot,
                "TO_PRB_CARD_NO": _DASH,
                "PRB_CARD_NO_LVAL": _DASH,
                "TO_TEMPER_VAL": to_temper,
                "TO_PLAN_PROD_ATTR_VAL": to_task.plan_prod_key,
                "REASON_CD": _REASON_CD,
                "REASON_CTN": _REASON_CTN,
                "TRANSMIT_YN": "N",
                "TRANSMIT_TM": None,
                "CRT_USER_ID": _RTS_USER,
                "CHG_USER_ID": _RTS_USER,
            })
    return rows


def _event_tm_for_hour(rule_timekey: str, hours: int) -> str:
    s = rule_timekey.ljust(16, "0")[:16]
    suffix = s[14:]
    dt = datetime.strptime(s[:14], "%Y%m%d%H%M%S") + timedelta(hours=hours)
    return dt.strftime("%Y%m%d%H%M%S") + suffix
