import json

from src.db.sql_log import log_sql, render_sql
from src.utils.ops_log import OPS_LOG_PATH


def test_render_sql_substitutes_binds():
    sql = """
SELECT *
  FROM T
 WHERE RULE_TIMEKEY = :rk
   AND FAC_ID = :facid
   AND BATCH_ID LIKE :batch_like
"""
    rendered = render_sql(
        sql,
        {"rk": "2026052922500000", "facid": "ICPRB", "batch_like": "%B1%"},
    )
    assert "RULE_TIMEKEY = '2026052922500000'" in rendered
    assert "FAC_ID = 'ICPRB'" in rendered
    assert "BATCH_ID LIKE '%B1%'" in rendered


def test_log_sql_prints_and_writes_jsonl(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("src.utils.ops_log.OPS_LOG_PATH", tmp_path / "ops.jsonl")
    sql = "SELECT 1 FROM DUAL WHERE FAC_ID = :facid"
    log_sql("max_timekey", sql, {"facid": "ICPRB"})

    out = capsys.readouterr().out
    assert "[sql] max_timekey" in out
    assert "FAC_ID = 'ICPRB'" in out
    assert "[sql.execute]" in out

    record = json.loads((tmp_path / "ops.jsonl").read_text(encoding="utf-8").strip())
    assert record["event"] == "sql.execute"
    assert record["name"] == "max_timekey"
    assert "FAC_ID = 'ICPRB'" in record["sql"]
