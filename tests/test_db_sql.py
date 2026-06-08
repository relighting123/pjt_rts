"""db/sql/ 외부 SQL 파일 로더 테스트."""
import pytest

from db.sql_loader import load_sql, sql_file
import config


def test_sql_files_exist():
    expected = [
        ("select", "fetch_rows"),
        ("select", "max_timekey"),
        ("select", "list_timekeys_in_range"),
        ("write", "delete_by_timekey"),
        ("write", "insert_assign"),
        ("write", "insert_plan_achv"),
        ("write", "insert_conv"),
        ("write", "insert_guide"),
    ]
    for category, name in expected:
        assert sql_file(category, name).is_file()


def test_fetch_rows_sql_requires_facid():
    sql = load_sql("select", "fetch_rows", table="RTS_LINEDSDB_INF")
    assert "FROM RTS_LINEDSDB_INF" in sql
    assert ":rk" in sql
    assert ":facid" in sql
    assert "AND FAC_ID = :facid" in sql
    assert ":fac_id" not in sql


def test_max_timekey_sql_requires_facid():
    sql = load_sql("select", "max_timekey", table="RTS_LINEDSDB_INF")
    assert ":facid" in sql
    assert "FAC_ID = :facid" in sql


def test_list_timekeys_sql_requires_facid():
    sql = load_sql("select", "list_timekeys_in_range", table="RTS_LINEDSDB_INF")
    assert ":facid" in sql


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
