"""db/sql/ 외부 SQL 파일 로더 테스트."""
from db.sql_loader import load_sql, sql_file


def test_sql_files_exist():
    expected = [
        ("select", "fetch_rows"),
        ("select", "fetch_rows_by_fac"),
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


def test_fetch_rows_sql_formats_table():
    sql = load_sql("select", "fetch_rows", table="RTS_LINEDSDB_INF")
    assert "FROM RTS_LINEDSDB_INF" in sql
    assert ":rk" in sql
    assert "FAC_ID" in sql


def test_fetch_rows_by_fac_sql_has_fac_param():
    sql = load_sql("select", "fetch_rows_by_fac", table="RTS_LINEDSDB_INF")
    assert ":fac_id" in sql


def test_insert_assign_sql_formats_table():
    sql = load_sql("write", "insert_assign", table="RTS_ASSIGN_INF")
    assert "INSERT INTO RTS_ASSIGN_INF" in sql
    assert ":RULE_TIMEKEY" in sql
