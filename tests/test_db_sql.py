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


def test_fetch_rows_sql_requires_fac_id():
    sql = load_sql("select", "fetch_rows", table="RTS_LINEDSDB_INF")
    assert "FROM RTS_LINEDSDB_INF" in sql
    assert ":rk" in sql
    assert ":fac_id" in sql
    assert "AND FAC_ID = :fac_id" in sql


def test_insert_assign_sql_formats_table():
    sql = load_sql("write", "insert_assign", table="RTS_ASSIGN_INF")
    assert "INSERT INTO RTS_ASSIGN_INF" in sql
    assert ":RULE_TIMEKEY" in sql


def test_require_fac_id_raises_without_default(monkeypatch):
    monkeypatch.setattr(config, "DEFAULT_FAC_ID", None)
    with pytest.raises(ValueError, match="FAC_ID 필수"):
        config.require_fac_id(None)


def test_require_fac_id_uses_default(monkeypatch):
    monkeypatch.setattr(config, "DEFAULT_FAC_ID", "ICPRB")
    assert config.require_fac_id(None) == "ICPRB"
