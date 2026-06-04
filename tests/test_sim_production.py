from simulator import load_problem, Simulator
from config import BENCHMARKS_DIR


def test_single_task_production_capped_by_capacity_and_wip():
    p = load_problem(BENCHMARKS_DIR / "benchmark_01.json")
    sim = Simulator(p)
    s = sim.reset()
    # 1대 x 100 UPH, WIP 1000 → 시간당 100 생산
    sim.advance_hour(s)
    assert s.produced[0] == 100
    assert s.wip[0] == 900
    sim.advance_hour(s)
    sim.advance_hour(s)
    assert s.produced[0] == 300
    m = sim.metrics(s)
    assert m["plan_achievement"] == 1.0  # 300/300


def test_production_capped_by_wip_when_queue_small():
    p = load_problem(BENCHMARKS_DIR / "benchmark_01.json")
    p.tasks[0] = p.tasks[0].__class__(  # init_wip을 50으로 축소
        "P1", "OP10", 1, "B1", 300, 50)
    sim = Simulator(p)
    s = sim.reset()
    sim.advance_hour(s)
    assert s.produced[0] == 50  # WIP 상한
    sim.advance_hour(s)
    assert s.produced[0] == 50  # 더 생산 못함
