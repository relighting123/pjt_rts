from db import rows_to_problem


def test_rows_to_problem_pivots_gbn_cd():
    # RTS_LINEDSDB_INF 한 줄 = (rule_timekey, fac_id, batch_id, ppk, oper_id, oper_seq, eqp_model, gbn_cd, attr_val)
    rows = [
        ("20260529", "ICPRB", "B1", "P1", "OP10", 1, "M1", "UPH", "100"),
        ("20260529", "ICPRB", "B1", "P1", "OP10", 1, "M1", "ASSIGN_EQUIP_CNT", "1"),
        ("20260529", "ICPRB", "B1", "P1", "OP10", 1, "M1", "D0_TARGET_QTY", "300"),
        ("20260529", "ICPRB", "B1", "P1", "OP10", 1, "M1", "WIP_QTY", "1000"),
        ("20260529", "ICPRB", "B1", "P1", "OP10", 1, "M1", "TOOL_QTY", "1"),
    ]
    p = rows_to_problem(rows, horizon_hours=3, conv_groups={"G1": ["B1"]})
    assert len(p.tasks) == 1
    assert p.tasks[0].plan_qty == 300
    assert p.uph_of("M1", 0) == 100.0
    assert p.init_assign[("M1", 0)] == 1
    assert p.tool_qty[("B1", "M1")] == 1
