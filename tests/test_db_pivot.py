from db import rows_to_problem, filter_rows_by_facid


def test_rows_to_problem_pivots_gbn_cd():
    # RTS_LINEDSDB_INF 한 줄 = (rule_timekey, fac_id, batch_id, ppk, oper_id, oper_seq, eqp_model, gbn_cd, attr_val)
    rows = [
        ("20260529", "ICPRB", "B1", "P1", "OP10", 1, "M1", "UPH", "100"),
        ("20260529", "ICPRB", "B1", "P1", "OP10", 1, "M1", "ASSIGN_EQUIP_CNT", "1"),
        ("20260529", "ICPRB", "B1", "P1", "OP10", 1, "M1", "D0_TARGET_QTY", "300"),
        ("20260529", "ICPRB", "B1", "P1", "OP10", 1, "M1", "WIP_QTY", "1000"),
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
        ("20260529", "ICPRB", "B1", "P1", "OP10", 1, "M1", "UPH", "100"),
        ("20260529", "ICPRB", "B1", "P1", "OP10", 1, "M1", "D0_TARGET_QTY", "300"),
        ("20260529", "ICPRB", "B1", "P1", "OP10", 1, "M1", "WIP_QTY", "1000"),
        ("20260529", "OTHER", "B2", "P2", "OP20", 1, "M2", "UPH", "200"),
        ("20260529", "OTHER", "B2", "P2", "OP20", 1, "M2", "D0_TARGET_QTY", "500"),
    ]
    p = rows_to_problem(rows, horizon_hours=3, facid="ICPRB")
    assert p.facid == "ICPRB"
    assert len(p.tasks) == 1
    assert p.tasks[0].plan_prod_key == "P1"

    all_rows = rows_to_problem(rows, horizon_hours=3)
    assert len(all_rows.tasks) == 2
    assert all_rows.facid is None


def test_filter_rows_by_facid_raises_when_empty():
    rows = [("20260529", "ICPRB", "B1", "P1", "OP10", 1, "M1", "UPH", "100")]
    try:
        filter_rows_by_facid(rows, "UNKNOWN")
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "UNKNOWN" in str(exc)
