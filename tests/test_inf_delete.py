"""INF 저장 시 RULE_TIMEKEY 삭제 동작 테스트."""
from unittest.mock import MagicMock, patch

import config
from src.db.adapter import (
    write_assign_results,
    write_eqpallocation_results,
    write_eqpconvplan_results,
)


def _mock_connect():
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value = cur
    return conn, cur


@patch("src.db.adapter._connect")
def test_write_assign_deletes_inf_even_when_rows_empty(mock_connect):
    conn, cur = _mock_connect()
    mock_connect.return_value = conn

    write_assign_results("2026052922500000", [])

    cur.execute.assert_called_once()
    sql = cur.execute.call_args[0][0]
    assert "DELETE FROM" in sql
    assert config.ASSIGN_TABLE in sql
    cur.executemany.assert_not_called()


@patch("src.db.adapter._connect")
def test_write_eqpallocation_deletes_inf_even_when_rows_empty(mock_connect):
    conn, cur = _mock_connect()
    mock_connect.return_value = conn

    write_eqpallocation_results("2026052922500000", [])

    cur.execute.assert_called_once()
    assert config.EQPALLOCATION_TABLE in cur.execute.call_args[0][0]
    cur.executemany.assert_not_called()


@patch("src.db.adapter._connect")
def test_write_eqpconvplan_deletes_inf_even_when_rows_empty(mock_connect):
    conn, cur = _mock_connect()
    mock_connect.return_value = conn

    write_eqpconvplan_results("2026052922500000", [])

    cur.execute.assert_called_once()
    assert config.EQPCONVPLAN_TABLE in cur.execute.call_args[0][0]
    cur.executemany.assert_not_called()
