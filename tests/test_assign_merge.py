"""ASSIGN 행 병합·EQPALLOCATION BATCH_ID 테스트."""
from src.db.adapter import rows_to_problem
from src.db.eqpallocation import build_eqpallocation_rows
from src.utils.json_io import load_problem
from src.utils.rows import build_assign_rows, finalize_assign_rows, merge_assign_rows
from config import TEST_DATA_DIR
import src.evaluate as report


def test_finalize_assign_rows_merges_consecutive_same_task():
    rows = [
        {
            "RULE_TIMEKEY": "RK", "EQP_ID": "M1-001", "EQP_MODEL_CD": "M1",
            "SEQ_NO": 1, "START_TIME": "2026050100000000", "END_TIME": "2026050101000000",
            "BATCH_ID": "B1", "PLAN_PROD_KEY": "P1", "OPER_ID": "OP10",
            "PRODUCE_QTY": 10, "CRT_USER_ID": "X",
        },
        {
            "RULE_TIMEKEY": "RK", "EQP_ID": "M1-001", "EQP_MODEL_CD": "M1",
            "SEQ_NO": 2, "START_TIME": "2026050101000000", "END_TIME": "2026050102000000",
            "BATCH_ID": "B1", "PLAN_PROD_KEY": "P1", "OPER_ID": "OP10",
            "PRODUCE_QTY": 20, "CRT_USER_ID": "X",
        },
        {
            "RULE_TIMEKEY": "RK", "EQP_ID": "M1-001", "EQP_MODEL_CD": "M1",
            "SEQ_NO": 3, "START_TIME": "2026050102000000", "END_TIME": "2026050103000000",
            "BATCH_ID": "B1", "PLAN_PROD_KEY": "P2", "OPER_ID": "OP20",
            "PRODUCE_QTY": 5, "CRT_USER_ID": "X",
        },
    ]
    out = finalize_assign_rows(rows)
    assert len(out) == 2
    assert out[0]["SEQ_NO"] == 1
    assert out[0]["END_TIME"] == "2026050102000000"
    assert out[0]["PRODUCE_QTY"] == 30
    assert out[1]["SEQ_NO"] == 2
    assert out[1]["PLAN_PROD_KEY"] == "P2"


def test_build_assign_rows_returns_merged_segments():
    p = load_problem(TEST_DATA_DIR / "benchmark_01.json")
    res = report.evaluate_benchmark(p, model=None)
    rows = res["assign_rows"]
    assert len(rows) == 1
    assert rows[0]["SEQ_NO"] == 1
    assert rows[0]["BATCH_ID"] == p.tasks[0].allocation_batch_id()


def test_eqpallocation_uses_equip_batch_id():
    rows = [
        ("20260529", "ICPRB", "9C", "P1", "OP10", 1, "", "AVAIL_WIP_QTY", "1000"),
        ("20260529", "ICPRB", "9C", "P1", "OP10", 1, "", "EXEC_D0_PLAN", "300"),
        ("20260529", "ICPRB", "9C/92", "P1", "OP10", 1, "M1", "EQUIP_UPH", "100"),
        ("20260529", "ICPRB", "9C/92", "P1", "OP10", 1, "M1", "ASSIGN_EQUIP_CNT", "1"),
    ]
    p = rows_to_problem(rows, horizon_hours=3)
    assert p.tasks[0].batch_id == "9C"
    assert p.tasks[0].allocation_batch_id() == "9C/92"
    alloc = build_eqpallocation_rows(p, p.plan_target_allocation_int())
    m1 = next(r for r in alloc if r["EQP_MODEL_CD"] == "M1")
    assert m1["BATCH_ID"] == "9C/92"
