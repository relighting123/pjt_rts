from db import rows_to_problem, filter_rows_by_facid, filter_rows_by_batchid, batch_like_pattern


def test_rows_to_problem_pivots_gbn_cd():
    # RTS_LINEDSDB_INF 한 줄 = (rule_timekey, fac_id, batch_id, ppk, oper_id, oper_seq, eqp_model, gbn_cd, attr_val)
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


def test_task_and_equipment_batch_id_mismatch_breaks_tool_lookup():
    """TASK(9C) vs 장비(9C/92) BATCH_ID 불일치 시 tool·전환 그룹 키가 어긋난다."""
    rows = [
        ("20260529", "ICPRB", "9C", "P1", "OP10", 1, "", "AVAIL_WIP_QTY", "1000"),
        ("20260529", "ICPRB", "9C", "P1", "OP10", 1, "", "EXEC_D0_PLAN", "300"),
        ("20260529", "ICPRB", "9C/92", "P1", "OP10", 1, "M1", "EQUIP_UPH", "100"),
        ("20260529", "ICPRB", "9C/92", "P1", "OP10", 1, "M1", "ASSIGN_EQUIP_CNT", "1"),
        ("20260529", "ICPRB", "9C/92", "P1", "OP10", 1, "M1", "TOOL_QTY", "2"),
    ]
    p = rows_to_problem(rows, horizon_hours=3)
    assert p.tasks[0].batch_id == "9C"
    assert p.tool_qty.get(("9C/92", "M1")) == 2
    assert p.tool_qty.get(("9C", "M1"), 0) == 0


def test_filter_rows_by_facid_raises_when_empty():
    rows = [("20260529", "ICPRB", "B1", "P1", "OP10", 1, "M1", "EQUIP_UPH", "100")]
    try:
        filter_rows_by_facid(rows, "UNKNOWN")
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "UNKNOWN" in str(exc)
