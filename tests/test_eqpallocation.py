"""RTS_EQPALLOCATION_INF/HIS 행 변환 테스트."""
from config import TEST_DATA_DIR
from src.db.eqpallocation import (
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


def test_allocation_his_metrics_zero_target():
    from src.db.eqpallocation import allocation_his_metrics
    from config import TEST_DATA_DIR
    p = load_problem(TEST_DATA_DIR / "benchmark_01.json")
    plan, capa, rate = allocation_his_metrics(p, 0, "M1", 0)
    assert plan == 300
    assert capa == 0
    assert rate == 0.0


def test_filter_rows_for_sql_drops_his_only_columns():
    from src.db.sql_loader import filter_rows_for_sql, load_sql
    import config
    row = {
        "FAC_ID": "F", "RULE_TIMEKEY": "RK", "BATCH_ID": "B1",
        "PLAN_PROD_KEY": "P1", "OPER_ID": "OP10", "EQP_MODEL_CD": "M1",
        "TARGET_EQP_CNT": 1, "CUR_EQP_CNT": 1, "MODE_TYP": "Heuristic",
        "PLAN_QTY": 300, "CAPA_QTY": 300, "ACHIVE_RATE": 1.0,
        "CRT_USER_ID": "X",
    }
    inf = load_sql("write", "insert_eqpallocation", table=config.EQPALLOCATION_TABLE)
    assert "PLAN_QTY" not in filter_rows_for_sql(inf, [row])[0]
    his = load_sql("write", "insert_eqpallocation_his", table=config.EQPALLOCATION_HIS_TABLE)
    filtered = filter_rows_for_sql(his, [row])[0]
    assert filtered["ACHIVE_RATE"] == 1.0
    from src.db.sql_loader import load_sql, sql_bind_names
    import config

    sql = load_sql("write", "insert_eqpallocation", table=config.EQPALLOCATION_TABLE)
    names = sql_bind_names(sql)
    assert "FAC_ID" in names
    assert "BATCH_ID" in names
    assert "MODE_TYP" in names
    assert "CUR_EQP_CNT" in names
    assert "CRT_TM" not in names

    his_sql = load_sql("write", "insert_eqpallocation_his", table=config.EQPALLOCATION_HIS_TABLE)
    his_names = sql_bind_names(his_sql)
    assert "PLAN_QTY" in his_names
    assert "CAPA_QTY" in his_names
    assert "ACHIVE_RATE" in his_names
    assert "PLAN_QTY" not in names
    assert "EVENT_TIMEKEY" not in his_names
