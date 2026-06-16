"""RTS_LINEDSDB_INF 행 — 컬럼명 기반 매핑 (순서 무관)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

# fetch_rows.sql SELECT 컬럼 ↔ Python 필드 (소문자 키로 정규화)
INPUT_ROW_FIELDS: tuple[str, ...] = (
    "rule_timekey",
    "fac_id",
    "batch_id",
    "plan_prod_key",
    "oper_id",
    "oper_seq",
    "eqp_model",
    "gbn_cd",
    "attr_val",
)

# DB/JSON 컬럼명 변형 → InputRow 필드명
_FIELD_ALIASES: dict[str, str] = {
    "rule_timekey": "rule_timekey",
    "fac_id": "fac_id",
    "facid": "fac_id",
    "batch_id": "batch_id",
    "batchid": "batch_id",
    "plan_prod_key": "plan_prod_key",
    "oper_id": "oper_id",
    "oper_seq": "oper_seq",
    "eqp_model_cd": "eqp_model",
    "eqp_model": "eqp_model",
    "gbn_cd": "gbn_cd",
    "gbncd": "gbn_cd",
    "attr_val": "attr_val",
    "attrval": "attr_val",
}


@dataclass(frozen=True, slots=True)
class InputRow:
    rule_timekey: str
    fac_id: str
    batch_id: str
    plan_prod_key: str
    oper_id: str
    oper_seq: int
    eqp_model: str
    gbn_cd: str
    attr_val: str


def _normalize_key(key: str) -> str:
    return str(key).strip().lower()


def _field_name(key: str) -> str | None:
    return _FIELD_ALIASES.get(_normalize_key(key))


def row_from_mapping(data: Mapping[str, Any] | InputRow) -> InputRow:
    """dict/Row 객체 → InputRow. 컬럼명이 필드와 같거나 alias면 매핑."""
    if isinstance(data, InputRow):
        return data
    values: dict[str, Any] = {}
    for key, val in data.items():
        field = _field_name(key)
        if field is None:
            continue
        values[field] = val
    missing = [f for f in INPUT_ROW_FIELDS if f not in values]
    if missing:
        raise ValueError(f"입력 행 필드 부족: {missing} (keys={list(data.keys())})")
    return InputRow(
        rule_timekey=str(values["rule_timekey"]),
        fac_id=str(values["fac_id"]),
        batch_id=str(values["batch_id"]),
        plan_prod_key=str(values["plan_prod_key"]),
        oper_id=str(values["oper_id"]),
        oper_seq=int(values["oper_seq"]),
        eqp_model=str(values["eqp_model"] or ""),
        gbn_cd=str(values["gbn_cd"]),
        attr_val=str(values["attr_val"]),
    )


def row_from_sequence(seq: Sequence[Any]) -> InputRow:
    """레거시 tuple/list → InputRow (고정 컬럼 순서)."""
    if len(seq) != len(INPUT_ROW_FIELDS):
        raise ValueError(
            f"입력 행 길이 불일치: {len(seq)} != {len(INPUT_ROW_FIELDS)}"
        )
    return row_from_mapping(dict(zip(INPUT_ROW_FIELDS, seq)))


def coerce_input_row(row: Mapping[str, Any] | InputRow | Sequence[Any]) -> InputRow:
    """tuple·dict·InputRow 모두 수용."""
    if isinstance(row, InputRow):
        return row
    if isinstance(row, Mapping):
        return row_from_mapping(row)
    return row_from_sequence(row)


def coerce_input_rows(rows) -> list[InputRow]:
    return [coerce_input_row(r) for r in rows]


def rows_from_cursor(cursor) -> list[InputRow]:
    """oracledb cursor → 컬럼명 기반 InputRow 목록."""
    if cursor.description is None:
        return []
    columns = [d[0] for d in cursor.description]
    return [row_from_mapping(dict(zip(columns, record))) for record in cursor.fetchall()]
