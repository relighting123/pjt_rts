from simulator import load_problem
from config import TEST_DATA_DIR
import test as report
from report_output import (
    build_guide_rows,
    build_inference_result_document,
    save_inference_result_document,
    load_inference_result_document,
    GUIDE_KEYS,
)


def test_build_guide_rows_includes_zero():
    p = load_problem(TEST_DATA_DIR / "benchmark_09.json")
    res = report.evaluate_benchmark(p, model=None)
    rows = build_guide_rows(p, res["guide_allocation"], "ANALYTIC")
    assert len(rows) == len(p.tasks) * len(p.models())
    assert all(k in rows[0] for k in GUIDE_KEYS)
    op30 = next(r for r in rows if r["OPER_ID"] == "OP30")
    assert op30["TARGET_EQP_CNT"] == 0.0


def test_inference_result_document_roundtrip(tmp_path):
    p = load_problem(TEST_DATA_DIR / "benchmark_01.json")
    res = report.evaluate_benchmark(p, model=None)
    doc = build_inference_result_document(p, res, policy="HEURISTIC")
    assert doc["schema_version"] == 1
    assert doc["guide"]["rows"]
    assert doc["dynamic"]["plan_achv_rows"]
    path = save_inference_result_document(doc, tmp_path / "r.json")
    loaded = load_inference_result_document(path)
    assert loaded["rule_timekey"] == p.rule_timekey
    assert len(loaded["guide"]["rows"]) == len(doc["guide"]["rows"])
