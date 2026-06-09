"""db/sql/select·write SQL 파일 로더 테스트."""
from pathlib import Path

import pytest

from db.sql_loader import filter_rows_for_sql, load_sql, sql_bind_names, sql_file
import config

_REFERENCE_SQL = Path(__file__).resolve().parent.parent / "db" / "sql" / "reference"


def test_reference_sql_files_exist():
    for name in (
        "01_create_tables",
        "02_sample_input_data",
        "03_sample_output_data",
        "04_verify_queries",
    ):
        assert (_REFERENCE_SQL / f"{name}.sql").is_file()


def test_sql_files_exist():
    expected = [
        ("select", "fetch_rows"),
        ("select", "max_timekey"),
        ("select", "list_timekeys_in_range"),
        ("write", "delete_by_timekey"),
        ("write", "insert_assign"),
        ("write", "insert_plan_achv"),
        ("write", "insert_eqpconvplan"),
        ("write", "insert_eqpconvplan_his"),
        ("write", "insert_eqpallocation"),
        ("write", "insert_eqpallocation_his"),
    ]
    for category, name in expected:
        assert sql_file(category, name).is_file()
    assert not sql_file("select", "fetch_rows_batch").is_file()


def test_fetch_rows_sql_requires_facid_and_batch_like():
    sql = load_sql("select", "fetch_rows", table="RTS_LINEDSDB_INF")
    assert "FROM RTS_LINEDSDB_INF" in sql
    assert ":rk" in sql
    assert ":facid" in sql
    assert ":batch_like" in sql
    assert "BATCH_ID LIKE :batch_like" in sql
    assert "AS rule_timekey" in sql
    assert "EQP_MODEL_CD AS eqp_model" in sql


def test_max_timekey_sql_requires_facid():
    sql = load_sql("select", "max_timekey", table="RTS_LINEDSDB_INF")
    assert ":facid" in sql
    assert "FAC_ID = :facid" in sql


def test_list_timekeys_sql_requires_facid():
    sql = load_sql("select", "list_timekeys_in_range", table="RTS_LINEDSDB_INF")
    assert ":facid" in sql


def test_filter_rows_for_sql_drops_extra_assign_keys():
    sql = load_sql("write", "insert_assign", table="RTS_ASSIGN_INF")
    assert "EVENT_TM" not in sql_bind_names(sql)
    row = {
        "RULE_TIMEKEY": "2026052922500000",
        "EVENT_TM": "2026052922500000",
        "EQP_ID": "M1-001",
        "EQP_MODEL_CD": "M1",
        "SEQ_NO": 1,
        "START_TIME": "2026052922500000",
        "END_TIME": "2026052923010000",
        "PLAN_PROD_KEY": "P1",
        "OPER_ID": "OP10",
        "PRODUCE_QTY": 100,
        "CRT_USER_ID": "RL_AGENT",
    }
    filtered = filter_rows_for_sql(sql, [row])[0]
    assert "EVENT_TM" not in filtered
    assert filtered["OPER_ID"] == "OP10"
    assert set(filtered) == sql_bind_names(sql)


def test_insert_assign_sql_formats_table():
    sql = load_sql("write", "insert_assign", table="RTS_ASSIGN_INF")
    assert "INSERT INTO RTS_ASSIGN_INF" in sql
    assert ":RULE_TIMEKEY" in sql


def test_require_facid_raises_without_default(monkeypatch):
    monkeypatch.setattr(config, "DEFAULT_FACID", None)
    with pytest.raises(ValueError, match="facid 필수"):
        config.require_facid(None)


def test_require_facid_uses_default(monkeypatch):
    monkeypatch.setattr(config, "DEFAULT_FACID", "ICPRB")
    assert config.require_facid(None) == "ICPRB"


def test_require_batchid_raises_without_default(monkeypatch):
    monkeypatch.setattr(config, "DEFAULT_BATCHID", None)
    with pytest.raises(ValueError, match="batchid 필수"):
        config.require_batchid(None)


def test_require_batchid_uses_default(monkeypatch):
    monkeypatch.setattr(config, "DEFAULT_BATCHID", "B1")
    assert config.require_batchid(None) == "B1"
