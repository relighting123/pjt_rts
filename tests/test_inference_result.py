from simulator import load_problem
from config import TEST_DATA_DIR
import test as report
from report_output import (
    build_eqpallocation_rows,
    build_inference_result_document,
    save_inference_result_document,
    load_inference_result_document,
    EQPALLOCATION_KEYS,
)


def test_build_eqpallocation_rows_uses_integer_counts():
    p = load_problem(TEST_DATA_DIR / "benchmark_09.json")
    res = report.evaluate_benchmark(p, model=None)
    rows = build_eqpallocation_rows(p, res["guide_allocation"], "ANALYTIC")
    assert len(rows) == len(p.tasks) * len(p.models())
    assert all(k in rows[0] for k in EQPALLOCATION_KEYS)
    assert all(isinstance(r["TARGET_EQP_CNT"], int) for r in rows)
    assert all(isinstance(r["CUR_EQP_CNT"], int) for r in rows)


def test_inference_result_document_roundtrip(tmp_path):
    p = load_problem(TEST_DATA_DIR / "benchmark_01.json")
    res = report.evaluate_benchmark(p, model=None)
    doc = build_inference_result_document(p, res, policy="HEURISTIC")
    assert doc["schema_version"] == 1
    assert doc["guide"]["rows"]
    assert doc["dynamic"]["plan_achv_rows"]
    assert "eqpallocation_rows" in doc["guide"]
    assert doc["guide"]["eqpallocation_rows"] == doc["guide"]["rows"]
    path = save_inference_result_document(doc, tmp_path / "r.json")
    loaded = load_inference_result_document(path)
    assert loaded["rule_timekey"] == p.rule_timekey
    assert len(loaded["guide"]["rows"]) == len(doc["guide"]["rows"])
