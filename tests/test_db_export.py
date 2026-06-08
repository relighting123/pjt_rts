from pathlib import Path

from db.export import export_from_rows, export_from_sample_rows
from db.pipeline import input_json_path, snapshot_key
from simulator import load_problem, save_problem, problem_to_dict
import config


def test_export_from_sample_rows_creates_inference_json(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "INFERENCE_DATA_DIR", tmp_path)
    out = export_from_sample_rows()
    assert out == tmp_path / "2026052922500000.json"
    assert out.is_file()
    p = load_problem(out)
    assert p.rule_timekey == "2026052922500000"
    assert p.tasks[0].plan_qty == 300
    assert "ground_truth" not in problem_to_dict(p, include_ground_truth=False)


def test_export_from_rows_matches_load_problem(tmp_path):
    rows = [
        ("20260529", "ICPRB", "B1", "P1", "OP10", 1, "M1", "UPH", "100"),
        ("20260529", "ICPRB", "B1", "P1", "OP10", 1, "M1", "ASSIGN_EQUIP_CNT", "1"),
        ("20260529", "ICPRB", "B1", "P1", "OP10", 1, "M1", "D0_TARGET_QTY", "300"),
        ("20260529", "ICPRB", "B1", "P1", "OP10", 1, "M1", "WIP_QTY", "1000"),
        ("20260529", "ICPRB", "B1", "P1", "OP10", 1, "M1", "TOOL_QTY", "1"),
    ]
    out = tmp_path / "exported.json"
    export_from_rows(rows, out, horizon_hours=3, rule_timekey="20260529")
    p = load_problem(out)
    assert len(p.tasks) == 1
    assert p.uph_of("M1", 0) == 100.0


def test_save_problem_roundtrip(tmp_path):
    src = config.TEST_DATA_DIR / "benchmark_01.json"
    p = load_problem(src)
    out = tmp_path / "roundtrip.json"
    save_problem(p, out, include_ground_truth=True)
    p2 = load_problem(out)
    assert p2.rule_timekey == p.rule_timekey
    assert len(p2.tasks) == len(p.tasks)
    assert p2.ground_truth == p.ground_truth


def test_export_from_rows_with_fac_id(tmp_path):
    rows = [
        ("20260529", "ICPRB", "B1", "P1", "OP10", 1, "M1", "UPH", "100"),
        ("20260529", "ICPRB", "B1", "P1", "OP10", 1, "M1", "D0_TARGET_QTY", "300"),
        ("20260529", "OTHER", "B2", "P2", "OP20", 1, "M2", "UPH", "200"),
    ]
    out = tmp_path / "fac.json"
    export_from_rows(rows, out, horizon_hours=3, rule_timekey="20260529", fac_id="ICPRB")
    p = load_problem(out)
    assert p.fac_id == "ICPRB"
    assert len(p.tasks) == 1


def test_snapshot_key_includes_fac_id():
    assert snapshot_key("2026052922500000") == "2026052922500000"
    assert snapshot_key("2026052922500000", "ICPRB") == "2026052922500000_ICPRB"
    assert input_json_path("2026052922500000", "ICPRB").name == "2026052922500000_ICPRB.json"


def test_save_problem_replaces_existing(tmp_path):
    src = config.TEST_DATA_DIR / "benchmark_01.json"
    p = load_problem(src)
    out = tmp_path / "roundtrip.json"
    save_problem(p, out, include_ground_truth=True)
    save_problem(p, out, include_ground_truth=False)
    p2 = load_problem(out)
    assert "ground_truth" not in problem_to_dict(p2, include_ground_truth=False)
