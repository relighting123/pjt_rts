import json

from src.utils.ops_log import log_ops, OPS_LOG_PATH
import config


def test_log_ops_writes_jsonl(tmp_path, monkeypatch, capsys):
    log_file = tmp_path / "ops.jsonl"
    monkeypatch.setattr("src.utils.ops_log.OPS_LOG_PATH", log_file)

    log_ops("test.event", facid="ICPRB", batchid="B1", count=3)

    out = capsys.readouterr().out
    assert "[test.event]" in out
    assert "facid=ICPRB" in out
    assert "batchid=B1" in out

    lines = log_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["event"] == "test.event"
    assert record["facid"] == "ICPRB"
    assert record["batchid"] == "B1"
    assert record["count"] == "3"
