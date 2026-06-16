"""db/sql/select·write 런타임 SQL 로더 (reference/ 는 수동 참조용)."""
from __future__ import annotations

import re
from pathlib import Path

_BIND_NAME_RE = re.compile(r":([A-Za-z_][A-Za-z0-9_]*)")

_SQL_ROOT = Path(__file__).resolve().parent / "sql"


def sql_file(category: str, name: str) -> Path:
    return _SQL_ROOT / category / f"{name}.sql"


def load_sql(category: str, name: str, **fmt: str) -> str:
    """category/name.sql 읽기. {table} 등 placeholder는 fmt로 치환."""
    path = sql_file(category, name)
    if not path.is_file():
        raise FileNotFoundError(f"SQL 파일 없음: {path}")
    sql = path.read_text(encoding="utf-8").strip()
    return sql.format(**fmt) if fmt else sql


def sql_bind_names(sql: str) -> frozenset[str]:
    """SQL 내 :BIND_NAME placeholder 목록 (대소문자 유지)."""
    return frozenset(_BIND_NAME_RE.findall(sql))


def filter_rows_for_sql(sql: str, rows: list[dict]) -> list[dict]:
    """executemany용 — SQL에 없는 dict 키 제거 (no bind placeholder 방지)."""
    names = sql_bind_names(sql)
    return [{k: v for k, v in row.items() if k in names} for row in rows]
