"""Oracle 어댑터 (oracledb 선택적). RTS_LINEDSDB_INF → ProblemInstance, 결과 테이블 기록.

oracledb 미설치/미접속이어도 rows_to_problem(순수 변환)은 동작한다.
"""
from __future__ import annotations
from collections import defaultdict
import config
from simulator import Task, ProblemInstance


def rows_to_problem(rows, horizon_hours: int, conv_groups: dict[str, list[str]],
                    switch_time_hours: int = config.DEFAULT_SWITCH_TIME_HOURS,
                    rule_timekey: str | None = None) -> ProblemInstance:
    """GBN_CD가 long-format인 행들을 ProblemInstance로 피벗.

    row = (rule_timekey, fac_id, batch_id, plan_prod_key, oper_id, oper_seq, eqp_model, gbn_cd, attr_val)
    """
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
    return ProblemInstance(
        rule_timekey=rk, horizon_hours=horizon_hours, switch_time_hours=switch_time_hours,
        tasks=tasks, _uph=uph, eqp_qty=dict(eqp_qty), init_assign=init_assign,
        tool_qty=tool_raw, conv_groups=conv_groups, ground_truth={},
    )


# --- 아래는 실제 Oracle 접속이 있을 때만 사용 (oracledb 필요) ---

def _connect():
    import oracledb  # 지연 import
    cfg = config.load_config()
    return oracledb.connect(user=cfg["user"], password=cfg["password"], dsn=cfg["dsn"])


def fetch_problem(rule_timekey: str | None = None, horizon_hours: int = 12,
                  conv_groups: dict | None = None) -> ProblemInstance:
    """RTS_LINEDSDB_INF에서 스냅샷을 읽어 ProblemInstance로 변환."""
    conn = _connect()
    try:
        cur = conn.cursor()
        if rule_timekey is None:
            cur.execute("SELECT MAX(RULE_TIMEKEY) FROM RTS_LINEDSDB_INF")
            rule_timekey = cur.fetchone()[0]
        cur.execute(
            "SELECT RULE_TIMEKEY, FAC_ID, BATCH_ID, PLAN_PROD_KEY, OPER_ID, OPER_SEQ, "
            "EQP_MODEL_CD, GBN_CD, ATTR_VAL FROM RTS_LINEDSDB_INF WHERE RULE_TIMEKEY = :rk",
            rk=rule_timekey)
        rows = cur.fetchall()
        return rows_to_problem(rows, horizon_hours, conv_groups or {}, rule_timekey=rule_timekey)
    finally:
        conn.close()


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


_ASSIGN_INSERT_SQL = (
    "INSERT INTO {table} (RULE_TIMEKEY, EQP_ID, EQP_MODEL_CD, SEQ_NO, "
    "START_TIME, END_TIME, PLAN_PROD_KEY, PRODUCE_QTY, CRT_TM, CRT_USER_ID) "
    "VALUES (:RULE_TIMEKEY, :EQP_ID, :EQP_MODEL_CD, :SEQ_NO, :START_TIME, "
    ":END_TIME, :PLAN_PROD_KEY, :PRODUCE_QTY, SYSTIMESTAMP, :CRT_USER_ID)"
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
