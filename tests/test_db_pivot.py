from src.db import rows_to_problem, filter_rows_by_facid, filter_rows_by_batchid, batch_like_pattern


def test_rows_to_problem_pivots_gbn_cd():
    rows = [
        ("20260529", "ICPRB", "B1", "P1", "OP10", 1, "M1", "EQUIP_UPH", "100"),
        ("20260529", "ICPRB", "B1", "P1", "OP10", 1, "M1", "ASSIGN_EQUIP_CNT", "1"),
        ("20260529", "ICPRB", "B1", "P1", "OP10", 1, "M1", "EXEC_D0_PLAN", "300"),
        ("20260529", "ICPRB", "B1", "P1", "OP10", 1, "M1", "AVAIL_WIP_QTY", "1000"),
        ("20260529", "ICPRB", "B1", "P1", "OP10", 1, "M1", "TOOL_QTY", "1"),
    ]
    p = rows_to_problem(rows, horizon_hours=3)
    assert len(p.tasks) == 1
    assert p.tasks[0].plan_qty == 300
    assert p.uph_of("M1", 0) == 100.0
    assert p.init_assign[("M1", 0)] == 1
    assert p.tool_qty[("B1", "M1")] == 1
    assert p.tool_cap("B1", "M1") == 1


def test_rows_to_problem_accepts_legacy_gbn_aliases():
    rows = [
        ("20260529", "ICPRB", "B1", "P1", "OP10", 1, "M1", "UPH", "100"),
        ("20260529", "ICPRB", "B1", "P1", "OP10", 1, "M1", "EXEC_D0_PLAN", "300"),
        ("20260529", "ICPRB", "B1", "P1", "OP10", 1, "M1", "AVAIL_WIP_QTY", "1000"),
    ]
    p = rows_to_problem(rows, horizon_hours=3)
    assert p.tasks[0].plan_qty == 300
    assert p.tasks[0].wip_qty == 1000
    assert p.uph_of("M1", 0) == 100.0


def test_rows_to_problem_filters_facid():
    rows = [
        ("20260529", "ICPRB", "B1", "P1", "OP10", 1, "M1", "EQUIP_UPH", "100"),
        ("20260529", "ICPRB", "B1", "P1", "OP10", 1, "M1", "EXEC_D0_PLAN", "300"),
        ("20260529", "ICPRB", "B1", "P1", "OP10", 1, "M1", "AVAIL_WIP_QTY", "1000"),
        ("20260529", "OTHER", "B2", "P2", "OP20", 1, "M2", "EQUIP_UPH", "200"),
        ("20260529", "OTHER", "B2", "P2", "OP20", 1, "M2", "EXEC_D0_PLAN", "500"),
    ]
    p = rows_to_problem(rows, horizon_hours=3, facid="ICPRB")
    assert p.facid == "ICPRB"
    assert len(p.tasks) == 1
    assert p.tasks[0].plan_prod_key == "P1"

    all_rows = rows_to_problem(rows, horizon_hours=3)
    assert len(all_rows.tasks) == 2
    assert all_rows.facid is None


def test_rows_to_problem_filters_batchid():
    rows = [
        ("20260529", "ICPRB", "B1", "P1", "OP10", 1, "M1", "EQUIP_UPH", "100"),
        ("20260529", "ICPRB", "B1", "P1", "OP10", 1, "M1", "EXEC_D0_PLAN", "300"),
        ("20260529", "ICPRB", "B2", "P2", "OP20", 1, "M2", "EQUIP_UPH", "200"),
    ]
    p = rows_to_problem(rows, horizon_hours=3, batchid="B1")
    assert len(p.tasks) == 1
    assert p.tasks[0].batch_id == "B1"


def test_batch_like_pattern_wraps_percent():
    assert batch_like_pattern("B1") == "%B1%"


def test_tool_qty_joins_by_lot_cd_not_batch_id():
    """WIP(9C) vs 장비(9C/92) BATCH_ID 불일치여도 LOT_CD=9C로 TOOL 조인."""
    rows = [
        ("20260529", "ICPRB", "9C", "P1", "OP10", 1, "", "AVAIL_WIP_QTY", "1000"),
        ("20260529", "ICPRB", "9C", "P1", "OP10", 1, "", "EXEC_D0_PLAN", "300"),
        ("20260529", "ICPRB", "9C/92", "P1", "OP10", 1, "M1", "EQUIP_UPH", "100"),
        ("20260529", "ICPRB", "9C/92", "P1", "OP10", 1, "M1", "ASSIGN_EQUIP_CNT", "1"),
        ("20260529", "ICPRB", "9C/92", "P1", "OP10", 1, "M1", "TOOL_QTY", "2"),
    ]
    p = rows_to_problem(rows, horizon_hours=3)
    assert p.tasks[0].batch_id == "9C"
    assert p.tool_qty[("9C", "M1")] == 2
    assert p.tool_cap("9C", "M1") == 2


def test_rows_to_problem_accepts_dict_rows():
    rows = [
        {
            "rule_timekey": "20260529",
            "fac_id": "ICPRB",
            "batch_id": "B1",
            "lot_cd": "B1",
            "temper_val": "-",
            "plan_prod_key": "P1",
            "oper_id": "OP10",
            "oper_seq": 1,
            "eqp_model": "M1",
            "gbn_cd": "EQUIP_UPH",
            "attr_val": "100",
        },
        {
            "RULE_TIMEKEY": "20260529",
            "FAC_ID": "ICPRB",
            "BATCH_ID": "B1",
            "LOT_CD": "B1",
            "TEMPER_VAL": "-",
            "PLAN_PROD_KEY": "P1",
            "OPER_ID": "OP10",
            "OPER_SEQ": 1,
            "EQP_MODEL_CD": "M1",
            "GBN_CD": "EXEC_D0_PLAN",
            "ATTR_VAL": "300",
        },
    ]
    p = rows_to_problem(rows, horizon_hours=3)
    assert len(p.tasks) == 1
    assert p.tasks[0].plan_qty == 300
    assert p.uph_of("M1", 0) == 100.0


def test_rows_to_problem_accepts_new_tuple_with_lot_columns():
    rows = [
        (
            "20260529", "ICPRB", "9C/92", "9C", "92",
            "P1", "OP10", 1, "M1", "TOOL_QTY", "3",
        ),
        (
            "20260529", "ICPRB", "9C", "9C", "-",
            "P1", "OP10", 1, "", "AVAIL_WIP_QTY", "500",
        ),
        (
            "20260529", "ICPRB", "9C", "9C", "-",
            "P1", "OP10", 1, "", "EXEC_D0_PLAN", "100",
        ),
    ]
    p = rows_to_problem(rows, horizon_hours=3)
    assert p.tool_qty[("9C", "M1")] == 3
    assert p.tasks[0].batch_id == "9C"


def test_filter_rows_by_facid_raises_when_empty():
    rows = [("20260529", "ICPRB", "B1", "P1", "OP10", 1, "M1", "EQUIP_UPH", "100")]
    try:
        filter_rows_by_facid(rows, "UNKNOWN")
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "UNKNOWN" in str(exc)
