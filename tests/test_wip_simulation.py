from src.simulation.kernel.simulator import Simulator
from src.simulation.domain.state import SimState
from src.utils.json_io import load_problem
from src.views.wip import wip_product_summary
from config import TEST_DATA_DIR


def test_wip_product_summary_groups_by_product():
    p = load_problem(TEST_DATA_DIR / "benchmark_02.json")
    rows = wip_product_summary(p)
    keys = {r["plan_prod_key"] for r in rows}
    assert keys == {"PA", "PB"}
    assert sum(r["init_wip"] for r in rows) == sum(t.init_wip for t in p.tasks)


def test_simulator_until_wip_exhausted_stops_when_wip_zero():
    p = load_problem(TEST_DATA_DIR / "benchmark_06.json")
    max_h = 48
    sim = Simulator(p, until_wip_exhausted=True, max_hours=max_h)
    s = sim.reset()
    steps = 0
    while not sim.is_done(s) and steps < max_h + 5:
        sim.advance_hour(s)
        steps += 1
    assert sum(s.wip.values()) == 0
    assert s.hour <= max_h


def test_evaluate_until_wip_exhausted_returns_final_wip():
    from src.evaluate import evaluate_benchmark

    p = load_problem(TEST_DATA_DIR / "benchmark_06.json")
    res = evaluate_benchmark(p, model=None, until_wip_exhausted=True)
    assert res["heuristic_final_wip"] is not None
    assert sum(res["heuristic_final_wip"].values()) == 0
    assert res["heuristic_sim_hours"] >= 1
