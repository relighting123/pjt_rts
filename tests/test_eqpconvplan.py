"""RTS_EQPCONVPLAN_INF/HIS 행 변환 테스트."""
from dataclasses import replace
from datetime import datetime, timedelta

from config import TEST_DATA_DIR
from src.db.eqpconvplan import (
    build_eqpconvplan_rows,
    conv_start_end_tm,
    split_batch_lot_temper,
)
from src.simulation.domain.problem import Move
from src.simulation.kernel.simulator import Simulator
from src.utils.json_io import load_problem
import src.evaluate as report


def test_split_batch_lot_temper():
    assert split_batch_lot_temper("9C/92") == ("9C", "92")
    assert split_batch_lot_temper("QQ/-30") == ("QQ", "-30")
    assert split_batch_lot_temper("B1") == ("B1", "-")


def test_conv_start_end_tm_adds_one_hour():
    start, end = conv_start_end_tm("2026052715000000")
    assert start == "202605271500"
    assert end == "202605271600"


def test_build_eqpconvplan_rows_from_trace():
    p = load_problem(TEST_DATA_DIR / "benchmark_02.json")
    res = report.evaluate_benchmark(p, model=None)
    rows = build_eqpconvplan_rows(p, res["trace"])
    assert len(rows) >= 1
    row = rows[0]
    assert row["PRCS_STAT_CD"] == "WAIT"
    assert row["RTS_GBN_CD"] == "RTS"
    assert row["EQP_ID"] == "-"
    assert row["EQP_MODEL_CD"] == "-"
    assert row["CONV_TIME"] == 1
    assert row["REASON_CD"] == "RTS-001"
    assert row["REASON_CTN"] == "테스트 데이터"
    assert row["TRANSMIT_YN"] == "N"
    assert row["CRT_USER_ID"] == "RTS"
    assert row["CHG_USER_ID"] == "RTS"
    assert row["JOB_ID"].startswith("CONV_")
    assert row["RULE_TIMEKEY"] == p.rule_timekey


def test_build_eqpconvplan_rows_batch_split():
    """9C/92 → QQ/-30 전환 시 LOT/TEMPER 분리."""
    p = load_problem(TEST_DATA_DIR / "benchmark_02.json")
    trace = [
        (
            0,
            [
                Move(model="MODEL-A", from_index=0, to_index=1),
            ],
            None,
        ),
    ]
    p.tasks[0] = replace(p.tasks[0], batch_id="9C/92")
    p.tasks[1] = replace(p.tasks[1], batch_id="QQ/-30")
    rows = build_eqpconvplan_rows(p, trace, facid="FAC-01")
    assert len(rows) == 1
    row = rows[0]
    assert row["FAC_ID"] == "FAC-01"
    assert row["LOT_CD"] == "9C"
    assert row["TEMPER_VAL"] == "92"
    assert row["TO_LOT_CD"] == "QQ"
    assert row["TO_TEMPER_VAL"] == "-30"
    assert row["OPER_ID"] == p.tasks[0].oper_id
    assert row["TO_OPER_ID"] == p.tasks[1].oper_id
    assert row["TESTER_EQP_MODEL_CD"] == "MODEL-A"
    rk = p.rule_timekey
    dt = datetime.strptime(rk[:14], "%Y%m%d%H%M%S")
    assert row["CONV_START_TM"] == dt.strftime("%Y%m%d%H%M")
    assert row["CONV_END_TM"] == (dt + timedelta(hours=1)).strftime("%Y%m%d%H%M")


def test_insert_eqpconvplan_sql_bind_names():
    from src.db.sql_loader import load_sql, sql_bind_names
    import config

    sql = load_sql("write", "insert_eqpconvplan", table=config.EQPCONVPLAN_TABLE)
    names = sql_bind_names(sql)
    assert "FAC_ID" in names
    assert "CONV_START_TM" in names
    assert "OPER_ID" in names
    assert "TO_OPER_ID" in names
    assert "CRT_TM" not in names
    assert "CHG_TM" not in names

    his_sql = load_sql("write", "insert_eqpconvplan_his", table=config.EQPCONVPLAN_HIS_TABLE)
    his_names = sql_bind_names(his_sql)
    assert "EVENT_TIMEKEY" not in his_names
