"""실행 SQL 콘솔/ops 로그."""
from __future__ import annotations

import re

from src.utils.ops_log import log_ops


def render_sql(sql: str, binds: dict | None = None) -> str:
    """바인드값을 치환한 SQL 문자열 (로그용, 실제 실행문 아님)."""
    if not binds:
        return sql.strip()

    lookup = {k.lower(): v for k, v in binds.items()}

    def _replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key.lower() not in lookup:
            return match.group(0)
        val = lookup[key.lower()]
        if val is None:
            return "NULL"
        if isinstance(val, bool):
            return "1" if val else "0"
        if isinstance(val, (int, float)):
            return str(val)
        text = str(val).replace("'", "''")
        return f"'{text}'"

    return re.sub(r":(\w+)", _replace, sql.strip())


def log_sql(
    name: str,
    sql: str,
    binds: dict | None = None,
    *,
    row_count: int | None = None,
) -> None:
    """실행 SQL을 콘솔에 출력하고 ops.jsonl에 기록."""
    rendered = render_sql(sql, binds)
    print(f"[sql] {name}", flush=True)
    print(rendered, flush=True)
    if row_count is not None:
        print(f"[sql] {name} rows={row_count}", flush=True)
    log_ops(
        "sql.execute",
        name=name,
        sql=rendered,
        row_count=row_count if row_count is not None else "-",
    )
