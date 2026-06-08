"""Oracle 어댑터 (oracledb 선택적). RTS_LINEDSDB_INF → ProblemInstance, 결과 테이블 기록.

oracledb 미설치/미접속이어도 rows_to_problem(순수 변환)은 동작한다.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timedelta
import config
from db.sql_loader import load_sql
from db.sql_log import log_sql
from simulator import Task, ProblemInstance


def filter_rows_by_facid(rows, facid: str | None) -> list[tuple]:
    """facid 조건으로 long-format 행 필터."""
    if not facid:
        return list(rows)
    filtered = [r for r in rows if r[1] == facid]
    if not filtered:
        raise ValueError(f"facid={facid} 에 해당하는 행 없음")
    return filtered


def filter_rows_by_batchid(rows, batchid: str) -> list[tuple]:
    """batch_id 부분 일치(LIKE %batchid%) 필터."""
    needle = batchid.lower()
    filtered = [r for r in rows if needle in str(r[2]).lower()]
    if not filtered:
        raise ValueError(f"batchid LIKE %{batchid}% 에 해당하는 행 없음")
    return filtered


def batch_like_pattern(batchid: str) -> str:
    """Oracle BATCH_ID LIKE 바인드값 (%좌우%)."""
    return f"%{batchid}%"


def rows_to_problem(rows, horizon_hours: int,
                    switch_time_hours: int = config.DEFAULT_SWITCH_TIME_HOURS,
                    rule_timekey: str | None = None,
                    facid: str | None = None,
                    batchid: str | None = None) -> ProblemInstance:
    """GBN_CD가 long-format인 행들을 ProblemInstance로 피벗.

    row = (rule_timekey, fac_id, batch_id, plan_prod_key, oper_id, oper_seq, eqp_model, gbn_cd, attr_val)
    """
    rows = filter_rows_by_facid(rows, facid)
    if batchid:
        rows = filter_rows_by_batchid(rows, batchid)
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
        if gbn == "EQUIP_UPH" and float(val) > 0:
            uph_raw[(ppk, oper_id, eqp_model)] = float(val)
        elif gbn == "ASSIGN_EQUIP_CNT":
            assign_raw[(ppk, oper_id, eqp_model)] = int(float(val))
        elif gbn == "TOOL_QTY":
            tool_raw[(batch_id, eqp_model)] = int(float(val))
        elif gbn == "D0_TARGET_QTY":
            target_raw[key] = int(float(val))
        elif gbn == "AVAIL_WIP_QTY":
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
    resolved_fac = facid
    if resolved_fac is None and rows:
        facs = {r[1] for r in rows}
        if len(facs) == 1:
            resolved_fac = next(iter(facs))
    return ProblemInstance(
        rule_timekey=rk, horizon_hours=horizon_hours, switch_time_hours=switch_time_hours,
        tasks=tasks, _uph=uph, eqp_qty=dict(eqp_qty), init_assign=init_assign,
        tool_qty=tool_raw, conv_groups=config.load_conv_groups(), facid=resolved_fac,
        ground_truth={},
    )


def _connect():
    import oracledb  # 지연 import
    cfg = config.load_config()
    return oracledb.connect(user=cfg["user"], password=cfg["password"], dsn=cfg["dsn"])


def _execute_logged(
    cur,
    name: str,
    category: str,
    sql_name: str,
    *,
    table: str | None = None,
    **binds,
) -> None:
    fmt = {"table": table} if table is not None else {}
    sql = load_sql(category, sql_name, **fmt)
    log_sql(name, sql, binds)
    cur.execute(sql, binds)


def _executemany_logged(
    cur,
    name: str,
    category: str,
    sql_name: str,
    rows: list[dict],
    *,
    table: str,
) -> None:
    sql = load_sql(category, sql_name, table=table)
    sample = rows[0] if rows else {}
    log_sql(name, sql, sample, row_count=len(rows))
    cur.executemany(sql, rows)


def parse_timekey(rule_timekey: str) -> datetime:
    s = str(rule_timekey).ljust(16, "0")[:16]
    return datetime.strptime(s[:14], "%Y%m%d%H%M%S")


def format_timekey(dt: datetime, suffix: str = "0000") -> str:
    return dt.strftime("%Y%m%d%H%M%S") + suffix[:4].ljust(4, "0")


def fetch_max_timekey(facid: str, table: str = config.INPUT_TABLE) -> str:
    """facid별 최신 RULE_TIMEKEY."""
    conn = _connect()
    try:
        cur = conn.cursor()
        _execute_logged(cur, "max_timekey", "select", "max_timekey", table=table, facid=facid)
        row = cur.fetchone()
        if not row or row[0] is None:
            raise RuntimeError(f"{table}에 facid={facid} RULE_TIMEKEY 없음")
        return str(row[0])
    finally:
        conn.close()


def resolve_timekey(rule_timekey: str | None = None, facid: str | None = None) -> str:
    """미지정 시 facid별 MAX(RULE_TIMEKEY)."""
    if rule_timekey:
        return rule_timekey
    return fetch_max_timekey(config.require_facid(facid))


def list_timekeys_in_range(
    from_timekey: str | None = None,
    to_timekey: str | None = None,
    lookback_days: int | None = None,
    facid: str | None = None,
    table: str = config.INPUT_TABLE,
) -> list[str]:
    """학습용 스냅샷 RULE_TIMEKEY 목록. from/to 미지정 시 최근 lookback_days(기본 30일)."""
    fac = config.require_facid(facid)
    lookback = lookback_days if lookback_days is not None else config.DEFAULT_TRAIN_LOOKBACK_DAYS
    conn = _connect()
    try:
        cur = conn.cursor()
        if from_timekey is None and to_timekey is None:
            _execute_logged(cur, "max_timekey", "select", "max_timekey", table=table, facid=fac)
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
        _execute_logged(
            cur, "list_timekeys_in_range", "select", "list_timekeys_in_range",
            table=table, f=from_timekey, t=to_timekey, facid=fac,
        )
        return [str(r[0]) for r in cur.fetchall()]
    finally:
        conn.close()


def fetch_rows(
    rule_timekey: str,
    facid: str,
    batchid: str,
    table: str = config.INPUT_TABLE,
) -> list[tuple]:
    """RTS_LINEDSDB_INF 조회. facid·batchid(LIKE %값%) 필수."""
    conn = _connect()
    try:
        cur = conn.cursor()
        _execute_logged(
            cur, "fetch_rows", "select", "fetch_rows", table=table,
            rk=rule_timekey, facid=facid, batch_like=batch_like_pattern(batchid),
        )
        return cur.fetchall()
    finally:
        conn.close()


def fetch_problem(
    rule_timekey: str | None = None,
    horizon_hours: int = 12,
    facid: str | None = None,
    batchid: str | None = None,
) -> ProblemInstance:
    """RTS_LINEDSDB_INF에서 스냅샷을 읽어 ProblemInstance로 변환."""
    fac = config.require_facid(facid)
    bid = config.require_batchid(batchid)
    rk = resolve_timekey(rule_timekey, facid=fac)
    rows = fetch_rows(rk, facid=fac, batchid=bid)
    if not rows:
        raise ValueError(
            f"RULE_TIMEKEY={rk}, facid={fac}, batchid LIKE %{bid}% 에 해당하는 행 없음"
        )
    return rows_to_problem(rows, horizon_hours, rule_timekey=rk, facid=fac, batchid=bid)


def write_assign_results(rule_timekey: str, assign_rows: list[dict]) -> None:
    """RTS_ASSIGN_INF/HIS 삭제 후 insert."""
    _write_table_pair(
        config.ASSIGN_TABLE, config.ASSIGN_HIS_TABLE, rule_timekey, assign_rows, "insert_assign",
    )


def write_plan_achv_results(rule_timekey: str, plan_rows: list[dict]) -> None:
    """RTS_PLAN_ACHV_INF/HIS 삭제 후 insert."""
    _write_table_pair(
        config.PLAN_ACHV_TABLE, config.PLAN_ACHV_HIS_TABLE,
        rule_timekey, plan_rows, "insert_plan_achv",
    )


def write_conv_results(rule_timekey: str, conv_rows: list[dict]) -> None:
    """RTS_CONV_INF/HIS 삭제 후 insert."""
    _write_table_pair(
        config.CONV_TABLE, config.CONV_HIS_TABLE, rule_timekey, conv_rows, "insert_conv",
    )


def write_guide_results(rule_timekey: str, guide_rows: list[dict]) -> None:
    """RTS_GUIDE_INF/HIS 삭제 후 insert."""
    _write_table_pair(
        config.GUIDE_TABLE, config.GUIDE_HIS_TABLE, rule_timekey, guide_rows, "insert_guide",
    )


def write_inference_result(rule_timekey: str, result_doc: dict) -> None:
    """추론 결과 JSON document → Oracle (가이드 + 동적 3종)."""
    write_guide_results(rule_timekey, result_doc.get("guide", {}).get("rows", []))
    dynamic = result_doc.get("dynamic", {})
    write_plan_achv_results(rule_timekey, dynamic.get("plan_achv_rows", []))
    write_assign_results(rule_timekey, dynamic.get("assign_rows", []))
    write_conv_results(rule_timekey, dynamic.get("conv_rows", []))


def _write_table_pair(
    inf_table: str,
    his_table: str,
    rule_timekey: str,
    rows: list[dict],
    insert_sql_name: str,
) -> None:
    if not rows:
        return
    conn = _connect()
    try:
        cur = conn.cursor()
        for table in (inf_table, his_table):
            _execute_logged(
                cur, f"delete_by_timekey:{table}", "write", "delete_by_timekey",
                table=table, rk=rule_timekey,
            )
            _executemany_logged(
                cur, f"{insert_sql_name}:{table}", "write", insert_sql_name, rows, table=table,
            )
        conn.commit()
    finally:
        conn.close()


def write_results(rule_timekey: str, allocation_rows: list[dict]) -> None:
    """하위호환: RTS_ASSIGN_INF/HIS insert (allocation_rows = assign_rows)."""
    write_assign_results(rule_timekey, allocation_rows)
