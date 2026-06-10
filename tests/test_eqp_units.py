"""장비 호기(EQP_ID) 추적·실제 호기 매핑 테스트."""
from config import TEST_DATA_DIR
from eqp_units import initial_positions, track_units, virtual_roster
from simulator import Equipment, load_problem
import test as report


def test_virtual_roster_numbering():
    p = load_problem(TEST_DATA_DIR / "benchmark_05.json")
    roster = virtual_roster(p)
    assert [e.eqp_id for e in roster] == ["M1-001", "M1-002"]
    assert all(e.eqp_model == "M1" for e in roster)


def test_initial_positions_real_roster():
    p = load_problem(TEST_DATA_DIR / "benchmark_03.json")
    assert [e.eqp_id for e in p.equipments] == ["ETX-101", "ETX-102"]
    pos = initial_positions(p)
    assert pos[("M1", 0)] == ["ETX-101", "ETX-102"]


def test_track_units_records_conversions():
    p = load_problem(TEST_DATA_DIR / "benchmark_03.json")
    res = report.evaluate_benchmark(p, model=None)
    hourly, conversions = track_units(p, res["trace"])
    assert len(hourly) == p.horizon_hours
    assert len(conversions) >= 1
    assert all(c["eqp_id"].startswith("ETX-") for c in conversions)
    # B1(OP10) → B2(OP20) 전환
    assert all(p.batch_of(c["from_index"]) != p.batch_of(c["to_index"]) for c in conversions)


def test_assign_rows_use_real_eqp_ids():
    p = load_problem(TEST_DATA_DIR / "benchmark_03.json")
    res = report.evaluate_benchmark(p, model=None)
    eqp_ids = {r["EQP_ID"] for r in res["assign_rows"]}
    assert eqp_ids <= {"ETX-101", "ETX-102"}
    assert eqp_ids  # 최소 1개 호기 배치


def test_assign_rows_eqp_id_continuity():
    """호기 identity가 시간대를 넘어 유지된다 (가상 호기도 동일)."""
    p = load_problem(TEST_DATA_DIR / "benchmark_05.json")
    res = report.evaluate_benchmark(p, model=None)
    by_eqp = {}
    for r in res["assign_rows"]:
        by_eqp.setdefault(r["EQP_ID"], []).append(r["SEQ_NO"])
    for seqs in by_eqp.values():
        assert seqs == list(range(1, len(seqs) + 1))


def test_conv_rows_carry_real_eqp_id():
    p = load_problem(TEST_DATA_DIR / "benchmark_03.json")
    res = report.evaluate_benchmark(p, model=None)
    assert len(res["conv_rows"]) >= 1
    for row in res["conv_rows"]:
        assert row["EQP_ID"].startswith("ETX-")
        assert row["EQP_MODEL_CD"] == "M1"


def test_conv_rows_without_roster_keep_dash():
    p = load_problem(TEST_DATA_DIR / "benchmark_02.json")
    res = report.evaluate_benchmark(p, model=None)
    assert len(res["conv_rows"]) >= 1
    assert all(r["EQP_ID"] == "-" for r in res["conv_rows"])


def test_problem_json_roundtrip_with_equipments(tmp_path):
    from simulator import save_problem
    p = load_problem(TEST_DATA_DIR / "benchmark_03.json")
    out = tmp_path / "rt.json"
    save_problem(p, out)
    p2 = load_problem(out)
    assert p2.equipments == p.equipments


def test_arrange_rows_to_equipments_builds_roster():
    from db.adapter import arrange_rows_to_equipments
    # dict(대소문자 무관)·tuple(EQP_ID, EQP_MODEL_CD, BATCH_ID, PLAN_PROD_KEY) 모두 수용
    rows = [
        {"EQP_ID": "ETX-201", "EQP_MODEL_CD": "M1", "BATCH_ID": "B1", "PLAN_PROD_KEY": "P1"},
        ["ETX-202", "M1", "B1", "P1"],
    ]
    equipments = arrange_rows_to_equipments(rows)
    assert equipments == [
        Equipment("ETX-201", "M1", "B1", "P1"),
        Equipment("ETX-202", "M1", "B1", "P1"),
    ]
    assert arrange_rows_to_equipments(None) == []


def test_rows_to_problem_uses_arrange_equipments():
    from db.adapter import arrange_rows_to_equipments, rows_to_problem
    rows = [
        ["RK1", "F1", "B1", "P1", "OP10", 1, "M1", "EQUIP_UPH", "100"],
        ["RK1", "F1", "B1", "P1", "OP10", 1, "M1", "EXEC_D0_PLAN", "300"],
        ["RK1", "F1", "B1", "P1", "OP10", 1, "M1", "AVAIL_WIP_QTY", "500"],
        ["RK1", "F1", "B1", "P1", "OP10", 1, "M1", "TOOL_QTY", "2"],
    ]
    arrange = [["ETX-201", "M1", "B1", "P1"], ["ETX-202", "M1", "B1", "P1"]]
    p = rows_to_problem(rows, horizon_hours=3, equipments=arrange_rows_to_equipments(arrange))
    assert [e.eqp_id for e in p.equipments] == ["ETX-201", "ETX-202"]
    # ASSIGN_EQUIP_CNT 미제공 → 호기 명단으로 init_assign 유도
    # (RTD_ARRANGE_INF에는 OPER_ID가 없으므로 PLAN_PROD_KEY·BATCH_ID로 task 매칭)
    assert p.init_assign == {("M1", 0): 2}
    assert p.eqp_qty == {"M1": 2}


def test_rows_to_problem_assign_cnt_takes_precedence():
    from db.adapter import arrange_rows_to_equipments, rows_to_problem
    rows = [
        ["RK1", "F1", "B1", "P1", "OP10", 1, "M1", "EQUIP_UPH", "100"],
        ["RK1", "F1", "B1", "P1", "OP10", 1, "M1", "ASSIGN_EQUIP_CNT", "1"],
    ]
    arrange = [["ETX-201", "M1", "B1", "P1"]]
    p = rows_to_problem(rows, horizon_hours=3, equipments=arrange_rows_to_equipments(arrange))
    assert p.init_assign == {("M1", 0): 1}
    assert len(p.equipments) == 1


def test_rows_to_problem_ignores_eqp_id_gbn():
    """GBN_CD='EQP_ID' 행은 더 이상 호기 명단으로 쓰지 않는다 (RTD_ARRANGE_INF로 이관)."""
    from db.adapter import rows_to_problem
    rows = [
        ["RK1", "F1", "B1", "P1", "OP10", 1, "M1", "EQUIP_UPH", "100"],
        ["RK1", "F1", "B1", "P1", "OP10", 1, "M1", "ASSIGN_EQUIP_CNT", "1"],
        ["RK1", "F1", "B1", "P1", "OP10", 1, "M1", "EQP_ID", "ETX-201"],
    ]
    p = rows_to_problem(rows, horizon_hours=3)
    assert p.equipments == []


def test_export_from_sample_rows_includes_arrange_equipments(tmp_path, monkeypatch):
    import config
    from db.export import export_from_sample_rows
    from simulator import load_problem
    monkeypatch.setattr(config, "INFERENCE_DATA_DIR", tmp_path)
    out = export_from_sample_rows()
    p = load_problem(out)
    assert [e.eqp_id for e in p.equipments] == ["ETX-101"]
    assert p.equipments[0].eqp_model == "M1"
