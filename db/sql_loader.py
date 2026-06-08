"""db/sql/select·write 런타임 SQL 로더 (reference/ 는 수동 참조용)."""
from __future__ import annotations

from pathlib import Path

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
