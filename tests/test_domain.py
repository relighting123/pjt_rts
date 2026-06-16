from src.utils.json_io import load_problem
from config import BENCHMARKS_DIR


def test_load_problem_indexes_tasks_and_uph():
    p = load_problem(BENCHMARKS_DIR / "benchmark_01.json")
    assert p.rule_timekey == "2026052922500000"
    assert p.horizon_hours == 3
    assert len(p.tasks) == 1
    t = p.tasks[0]
    assert (t.plan_prod_key, t.oper_id, t.batch_id, t.plan_qty) == ("P1", "OP10", "B1", 300)
    assert t.wip_qty == 1000
    assert t.init_wip == t.wip_qty
    # uph 조회: (model, task_index)
    assert p.uph_of("M1", 0) == 100.0
    # 부적격(미등록 model)은 None
    assert p.uph_of("M9", 0) is None
    # 초기 배치
    assert p.init_assign[("M1", 0)] == 1
    # batch / 전환그룹
    assert p.batch_of(0) == "B1"
    assert p.conv_group_of("B1") == "G1"


def test_load_problem_accepts_wip_qty_alias(tmp_path):
    import json
    from src.utils.json_io import load_problem, save_problem

    doc = {
        "rule_timekey": "T",
        "horizon_hours": 1,
        "tasks": [{
            "plan_prod_key": "P1", "oper_id": "OP10", "oper_seq": 1,
            "batch_id": "B1", "plan_qty": 100, "wip_qty": 500,
        }],
        "uph": [{"plan_prod_key": "P1", "oper_id": "OP10", "eqp_model": "M1", "uph": 10}],
        "eqp_qty": {"M1": 1},
        "init_assign": [],
        "tool_qty": [],
    }
    path = tmp_path / "wip.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    p = load_problem(path)
    assert p.tasks[0].wip_qty == 500

    out = tmp_path / "out.json"
    save_problem(p, out, include_ground_truth=False)
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert saved["tasks"][0]["wip_qty"] == 500


def test_next_task_index_follows_oper_seq():
    p = load_problem(BENCHMARKS_DIR / "benchmark_01.json")
    # 단일 OPER → 다음 공정 없음
    assert p.next_task_index(0) is None
