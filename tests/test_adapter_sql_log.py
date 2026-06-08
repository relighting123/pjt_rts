from unittest.mock import MagicMock

from db import adapter
from db.input_row import INPUT_ROW_FIELDS


def _cursor_description():
    return [(name,) for name in INPUT_ROW_FIELDS]


def test_fetch_rows_logs_sql(monkeypatch, capsys):
    record = ("tk", "ICPRB", "B1", "P1", "OP10", 1, "M1", "EQUIP_UPH", "100")
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value = cur
    cur.description = _cursor_description()
    cur.fetchall.return_value = [record]
    monkeypatch.setattr(adapter, "_connect", lambda: conn)

    out = adapter.fetch_rows("2026052922500000", "ICPRB", "B1")
    assert len(out) == 1
    assert out[0].gbn_cd == "EQUIP_UPH"

    text = capsys.readouterr().out
    assert "[sql] fetch_rows" in text
    assert "RULE_TIMEKEY = '2026052922500000'" in text
    assert "FAC_ID = 'ICPRB'" in text
    assert "BATCH_ID LIKE '%B1%'" in text
    cur.execute.assert_called_once()
