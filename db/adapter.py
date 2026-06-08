"""Oracle 어댑터 (oracledb 선택적). RTS_LINEDSDB_INF → ProblemInstance, 결과 테이블 기록.

oracledb 미설치/미접속이어도 rows_to_problem(순수 변환)은 동작한다.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import config
from simulator import Task, ProblemInstance


def filter_rows_by_fac_id(rows, fac_id: str | None) -> list[tuple]:
    """FAC_ID 조건으로 long-format 행 필터."""
    if not fac_id:
        return list(rows)
    filtered = [r for r in rows if r[1] == fac_id]
    if not filtered:
        raise ValueError(f"FAC_ID={fac_id} 에 해당하는 행 없음")
    return filtered


def rows_to_problem(rows, horizon_hours: int,
                    switch_time_hours: int = config.DEFAULT_SWITCH_TIME_HOURS,
                    rule_timekey: str | None = None,
                    fac_id: str | None = None) -> ProblemInstance:
    """GBN_CD가 long-format인 행들을 ProblemInstance로 피벗.

    row = (rule_timekey, fac_id, batch_id, plan_prod_key, oper_id, oper_seq, eqp_model, gbn_cd, attr_val)
    """
    rows = filter_rows_by_fac_id(rows, fac_id)
    task_meta: dict[tuple[str, str], dict] = {}
    uph_raw: dict[tuple[str, str, str], float] = {}
    assign_raw: dict[tuple[str, str, str], int] = {}
    tool_raw: dict[tuple[str, str], int] = {}
    target_raw: dict[tuple[str, str], int] = {}
    wip_raw: dict[tuple[str, str], int] = {}
    eqp_models: set[str] = set()
    rk = rule_timekey

    for r in rows:
        rk = rk or r[0]
        _, _fac, batch_id, ppk, oper_id, oper_seq, eqp_model, gbn, val = r
        key = (ppk, oper_id)
        task_meta.setdefault(key, {"batch_id": batch_id, "oper_seq": int(oper_seq)})
        if eqp_model:
            eqp_models.add(eqp_model)
        if gbn == "UPH" and float(val) > 0:
            uph_raw[(ppk, oper_id, eqp_model)] = float(val)
        elif gbn == "ASSIGN_EQUIP_CNT":
            assign_raw[(ppk, oper_id, eqp_model)] = int(float(val))
        elif gbn == "TOOL_QTY":
            tool_raw[(batch_id, eqp_model)] = int(float(val))
        elif gbn == "D0_TARGET_QTY":
            target_raw[key] = int(float(val))
        elif gbn == "WIP_QTY":
            wip_raw[key] = int(float(val))

    keys = list(task_meta)
    index = {k: i for i, k in enumerate(keys)}
    tasks = [
        Task(ppk, oper, task_meta[(ppk, oper)]["oper_seq"], task_meta[(ppk, oper)]["batch_id"],
             target_raw.get((ppk, oper), 0), wip_raw.get((ppk, oper), 0))
        for (ppk, oper) in keys
    ]
    uph = {(m, index[(ppk, o)]): v for (ppk, o, m), v in uph_raw.items()}
    init_assign = {(m, index[(ppk, o)]): c for (ppk, o, m), c in assign_raw.items() if c > 0}
    eqp_qty: dict[str, int] = defaultdict(int)
    for (m, _ti), c in init_assign.items():
        eqp_qty[m] += c
    for m in eqp_models:
        eqp_qty.setdefault(m, 0)
    resolved_fac = fac_id
    if resolved_fac is None and rows:
        facs = {r[1] for r in rows}
        if len(facs) == 1:
            resolved_fac = next(iter(facs))
    return ProblemInstance(
        rule_timekey=rk, horizon_hours=horizon_hours, switch_time_hours=switch_time_hours,
        tasks=tasks, _uph=uph, eqp_qty=dict(eqp_qty), init_assign=init_assign,
        tool_qty=tool_raw, conv_groups=config.load_conv_groups(), fac_id=resolved_fac,
        ground_truth={},
    )


def _connect():
    import oracledb  # 지연 import
    cfg = config.load_config()
    return oracledb.connect(user=cfg["user"], password=cfg["password"], dsn=cfg["dsn"])


def parse_timekey(rule_timekey: str) -> datetime:
    s = str(rule_timekey).ljust(16, "0")[:16]
    return datetime.strptime(s[:14], "%Y%m%d%H%M%S")


def format_timekey(dt: datetime, suffix: str = "0000") -> str:
    return dt.strftime("%Y%m%d%H%M%S") + suffix[:4].ljust(4, "0")


def fetch_max_timekey(table: str = config.INPUT_TABLE) -> str:
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT MAX(RULE_TIMEKEY) FROM {table}")
        row = cur.fetchone()
        if not row or row[0] is None:
            raise RuntimeError(f"{table}에 RULE_TIMEKEY 없음")
        return str(row[0])
    finally:
        conn.close()


def resolve_timekey(rule_timekey: str | None = None) -> str:
    """미지정 시 MAX(RULE_TIMEKEY)."""
    return rule_timekey if rule_timekey else fetch_max_timekey()


def list_timekeys_in_range(
    from_timekey: str | None = None,
    to_timekey: str | None = None,
    lookback_days: int | None = None,
    table: str = config.INPUT_TABLE,
) -> list[str]:
    """학습용 스냅샷 RULE_TIMEKEY 목록. from/to 미지정 시 최근 lookback_days(기본 30일)."""
    lookback = lookback_days if lookback_days is not None else config.DEFAULT_TRAIN_LOOKBACK_DAYS
    conn = _connect()
    try:
        cur = conn.cursor()
        if from_timekey is None and to_timekey is None:
            cur.execute(f"SELECT MAX(RULE_TIMEKEY) FROM {table}")
            row = cur.fetchone()
            if not row or row[0] is None:
                return []
            max_tk = str(row[0])
            to_dt = parse_timekey(max_tk)
            from_dt = to_dt - timedelta(days=lookback)
            suffix = max_tk[14:] if len(max_tk) >= 16 else "0000"
            from_timekey = format_timekey(from_dt, suffix)
            to_timekey = max_tk
        elif from_timekey is None or to_timekey is None:
            raise ValueError("from_timekey와 to_timekey는 함께 지정하거나 둘 다 생략해야 합니다.")
        cur.execute(
            f"SELECT DISTINCT RULE_TIMEKEY FROM {table} "
            "WHERE RULE_TIMEKEY >= :f AND RULE_TIMEKEY <= :t ORDER BY RULE_TIMEKEY",
            f=from_timekey, t=to_timekey,
        )
        return [str(r[0]) for r in cur.fetchall()]
    finally:
        conn.close()


def fetch_rows(
    rule_timekey: str,
    fac_id: str | None = None,
    table: str = config.INPUT_TABLE,
) -> list[tuple]:
    conn = _connect()
    try:
        cur = conn.cursor()
        sql = (
            "SELECT RULE_TIMEKEY, FAC_ID, BATCH_ID, PLAN_PROD_KEY, OPER_ID, OPER_SEQ, "
            "EQP_MODEL_CD, GBN_CD, ATTR_VAL FROM "
            f"{table} WHERE RULE_TIMEKEY = :rk"
        )
        params: dict = {"rk": rule_timekey}
        if fac_id:
            sql += " AND FAC_ID = :fac_id"
            params["fac_id"] = fac_id
        cur.execute(sql, **params)
        return cur.fetchall()
    finally:
        conn.close()


def fetch_problem(
    rule_timekey: str | None = None,
    horizon_hours: int = 12,
    fac_id: str | None = None,
) -> ProblemInstance:
    """RTS_LINEDSDB_INF에서 스냅샷을 읽어 ProblemInstance로 변환."""
    rk = resolve_timekey(rule_timekey)
    fac = config.resolve_fac_id(fac_id)
    rows = fetch_rows(rk, fac_id=fac)
    if fac and not rows:
        raise ValueError(f"RULE_TIMEKEY={rk}, FAC_ID={fac} 에 해당하는 행 없음")
    return rows_to_problem(rows, horizon_hours, rule_timekey=rk, fac_id=fac)


def write_assign_results(rule_timekey: str, assign_rows: list[dict]) -> None:
    """RTS_ASSIGN_INF/HIS 삭제 후 insert."""
    _write_table_pair(config.ASSIGN_TABLE, config.ASSIGN_HIS_TABLE, rule_timekey, assign_rows, _ASSIGN_INSERT_SQL)


def write_plan_achv_results(rule_timekey: str, plan_rows: list[dict]) -> None:
    """RTS_PLAN_ACHV_INF/HIS 삭제 후 insert."""
    _write_table_pair(
        config.PLAN_ACHV_TABLE, config.PLAN_ACHV_HIS_TABLE, rule_timekey, plan_rows, _PLAN_ACHV_INSERT_SQL)


def write_conv_results(rule_timekey: str, conv_rows: list[dict]) -> None:
    """RTS_CONV_INF/HIS 삭제 후 insert."""
    _write_table_pair(config.CONV_TABLE, config.CONV_HIS_TABLE, rule_timekey, conv_rows, _CONV_INSERT_SQL)


def write_guide_results(rule_timekey: str, guide_rows: list[dict]) -> None:
    """RTS_GUIDE_INF/HIS 삭제 후 insert."""
    _write_table_pair(config.GUIDE_TABLE, config.GUIDE_HIS_TABLE, rule_timekey, guide_rows, _GUIDE_INSERT_SQL)


def write_inference_result(rule_timekey: str, result_doc: dict) -> None:
    """추론 결과 JSON document → Oracle (가이드 + 동적 3종)."""
    write_guide_results(rule_timekey, result_doc.get("guide", {}).get("rows", []))
    dynamic = result_doc.get("dynamic", {})
    write_plan_achv_results(rule_timekey, dynamic.get("plan_achv_rows", []))
    write_assign_results(rule_timekey, dynamic.get("assign_rows", []))
    write_conv_results(rule_timekey, dynamic.get("conv_rows", []))


_ASSIGN_INSERT_SQL = (
    "INSERT INTO {table} (RULE_TIMEKEY, EQP_ID, EQP_MODEL_CD, SEQ_NO, "
    "START_TIME, END_TIME, PLAN_PROD_KEY, OPER_ID, PRODUCE_QTY, CRT_TM, CRT_USER_ID) "
    "VALUES (:RULE_TIMEKEY, :EQP_ID, :EQP_MODEL_CD, :SEQ_NO, :START_TIME, "
    ":END_TIME, :PLAN_PROD_KEY, :OPER_ID, :PRODUCE_QTY, SYSTIMESTAMP, :CRT_USER_ID)"
)

_PLAN_ACHV_INSERT_SQL = (
    "INSERT INTO {table} (RULE_TIMEKEY, EVENT_TM, BATCH_ID, PLAN_PROD_KEY, OPER_ID, "
    "PLAN_QTY, REMAIN_QTY, PRODUCE_QTY, ACHIEVE_RATE, EQP_UTIL_RATE, CRT_TM, CRT_USER_ID) "
    "VALUES (:RULE_TIMEKEY, :EVENT_TM, :BATCH_ID, :PLAN_PROD_KEY, :OPER_ID, "
    ":PLAN_QTY, :REMAIN_QTY, :PRODUCE_QTY, :ACHIEVE_RATE, :EQP_UTIL_RATE, "
    "SYSTIMESTAMP, :CRT_USER_ID)"
)

_CONV_INSERT_SQL = (
    "INSERT INTO {table} (RULE_TIMEKEY, EVENT_TM, EQP_ID, EQP_MODEL_CD, SEQ_NO, "
    "START_TIME, END_TIME, FROM_BATCH_ID, TO_BATCH_ID, "
    "FROM_PLAN_PROD_KEY, TO_PLAN_PROD_KEY, FROM_OPER_ID, TO_OPER_ID, CRT_TM, CRT_USER_ID) "
    "VALUES (:RULE_TIMEKEY, :EVENT_TM, :EQP_ID, :EQP_MODEL_CD, :SEQ_NO, "
    ":START_TIME, :END_TIME, :FROM_BATCH_ID, :TO_BATCH_ID, "
    ":FROM_PLAN_PROD_KEY, :TO_PLAN_PROD_KEY, :FROM_OPER_ID, :TO_OPER_ID, "
    "SYSTIMESTAMP, :CRT_USER_ID)"
)

_GUIDE_INSERT_SQL = (
    "INSERT INTO {table} (RULE_TIMEKEY, PLAN_PROD_KEY, OPER_ID, EQP_MODEL_CD, "
    "TARGET_EQP_CNT, GUIDE_SOURCE, CRT_TM, CRT_USER_ID) "
    "VALUES (:RULE_TIMEKEY, :PLAN_PROD_KEY, :OPER_ID, :EQP_MODEL_CD, "
    ":TARGET_EQP_CNT, :GUIDE_SOURCE, SYSTIMESTAMP, :CRT_USER_ID)"
)


def _write_table_pair(inf_table: str, his_table: str, rule_timekey: str,
                      rows: list[dict], insert_sql_template: str) -> None:
    if not rows:
        return
    conn = _connect()
    try:
        cur = conn.cursor()
        sql = insert_sql_template.format(table="{table}")
        for table in (inf_table, his_table):
            cur.execute(f"DELETE FROM {table} WHERE RULE_TIMEKEY = :rk", rk=rule_timekey)
            cur.executemany(sql.format(table=table), rows)
        conn.commit()
    finally:
        conn.close()


def write_results(rule_timekey: str, allocation_rows: list[dict]) -> None:
    """하위호환: RTS_ASSIGN_INF/HIS insert (allocation_rows = assign_rows)."""
    write_assign_results(rule_timekey, allocation_rows)
