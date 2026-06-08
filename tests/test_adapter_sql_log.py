from unittest.mock import MagicMock

from db import adapter


def test_fetch_rows_logs_sql(monkeypatch, capsys):
    rows = [("tk", "ICPRB", "B1", "P1", "OP10", 1, "M1", "EQUIP_UPH", "100")]
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value = cur
    cur.fetchall.return_value = rows
    monkeypatch.setattr(adapter, "_connect", lambda: conn)

    out = adapter.fetch_rows("2026052922500000", "ICPRB", "B1")
    assert out == rows

    text = capsys.readouterr().out
    assert "[sql] fetch_rows" in text
    assert "RULE_TIMEKEY = '2026052922500000'" in text
    assert "FAC_ID = 'ICPRB'" in text
    assert "BATCH_ID LIKE '%B1%'" in text
    cur.execute.assert_called_once()
