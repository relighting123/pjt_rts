"""RTS_EQPALLOCATION_INF/HIS 행 변환 테스트."""
from config import TEST_DATA_DIR
from src.db.eqpallocation import (
    allocation_metrics,
    build_eqpallocation_rows,
    guide_source_to_mode_typ,
)
from src.utils.json_io import load_problem
import src.evaluate as report


def test_guide_source_to_mode_typ():
    assert guide_source_to_mode_typ("ALLOC_RL") == "RL"
    assert guide_source_to_mode_typ("ANALYTIC") == "Heuristic"


def test_build_eqpallocation_rows_includes_fac_batch_oper():
    p = load_problem(TEST_DATA_DIR / "benchmark_01.json")
    res = report.evaluate_benchmark(p, model=None)
    rows = build_eqpallocation_rows(p, res["guide_allocation"], "ANALYTIC", facid="FAC-01")
    assert len(rows) >= 1
    row = rows[0]
    assert row["FAC_ID"] == "FAC-01"
    assert row["BATCH_ID"] == p.tasks[0].allocation_batch_id()
    assert row["OPER_ID"] == p.tasks[0].oper_id
    assert row["MODE_TYP"] == "Heuristic"
    assert row["PLAN_QTY"] == p.tasks[0].plan_qty
    assert row["CAPA_QTY"] == row["TARGET_EQP_CNT"] * 100 * p.horizon_hours
    assert row["ACHIVE_RATE"] == 1.0
    assert "CAPA_QTY=TARGET_EQP_CNT" in row["LOG_INF_VAL"]
    assert "ACHIVE_RATE=min(CAPA_QTY/PLAN_QTY,1)" in row["LOG_INF_VAL"]
    assert len(row["LOG_INF_VAL"]) <= 4000
    assert "TARGET_EQP_CNT" in row
    assert "CUR_EQP_CNT" in row
    assert isinstance(row["TARGET_EQP_CNT"], int)
    assert isinstance(row["CUR_EQP_CNT"], int)


def test_build_eqpallocation_rows_rl_mode():
    p = load_problem(TEST_DATA_DIR / "benchmark_02.json")
    res = report.evaluate_benchmark(p, model=None)
    rows = build_eqpallocation_rows(p, res["guide_allocation"], "ALLOC_RL")
    assert all(r["MODE_TYP"] == "RL" for r in rows)


def test_cur_eqp_cnt_from_init_assign():
    p = load_problem(TEST_DATA_DIR / "benchmark_01.json")
    res = report.evaluate_benchmark(p, model=None)
    rows = build_eqpallocation_rows(p, res["guide_allocation"], "ANALYTIC")
    assigned = [r for r in rows if r["CUR_EQP_CNT"] > 0]
    assert len(assigned) >= 1
    assert assigned[0]["CUR_EQP_CNT"] == p.init_assign.get(
        (assigned[0]["EQP_MODEL_CD"], 0), 0,
    )


def test_allocation_metrics_zero_target():
    p = load_problem(TEST_DATA_DIR / "benchmark_01.json")
    plan, capa, rate, log_val = allocation_metrics(p, 0, "M1", 0)
    assert plan == 300
    assert capa == 0
    assert rate == 0.0
    assert "TARGET_EQP_CNT(0)" in log_val


def test_insert_eqpallocation_sql_bind_names():
    from src.db.sql_loader import filter_rows_for_sql, load_sql, sql_bind_names
    import config

    row = {
        "FAC_ID": "F", "RULE_TIMEKEY": "RK", "BATCH_ID": "B1",
        "PLAN_PROD_KEY": "P1", "OPER_ID": "OP10", "EQP_MODEL_CD": "M1",
        "TARGET_EQP_CNT": 1, "CUR_EQP_CNT": 1, "MODE_TYP": "Heuristic",
        "PLAN_QTY": 300, "CAPA_QTY": 300, "ACHIVE_RATE": 1.0,
        "LOG_INF_VAL": "PLAN_QTY=300",
        "CRT_USER_ID": "X",
    }
    inf_sql = load_sql("write", "insert_eqpallocation", table=config.EQPALLOCATION_TABLE)
    inf_names = sql_bind_names(inf_sql)
    assert "PLAN_QTY" in inf_names
    assert "CAPA_QTY" in inf_names
    assert "ACHIVE_RATE" in inf_names
    assert "LOG_INF_VAL" in inf_names
    assert "CRT_TM" not in inf_names
    inf_row = filter_rows_for_sql(inf_sql, [row])[0]
    assert inf_row["LOG_INF_VAL"] == "PLAN_QTY=300"

    his_sql = load_sql("write", "insert_eqpallocation_his", table=config.EQPALLOCATION_HIS_TABLE)
    his_names = sql_bind_names(his_sql)
    assert "LOG_INF_VAL" in his_names
    assert "EVENT_TIMEKEY" not in his_names
