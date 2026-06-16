from src.utils.json_io import load_problem
from src.simulation.kernel.simulator import Simulator
from agents.heuristic import heuristic_actions
from agents.runner import run_policy
from config import BENCHMARKS_DIR


def _teacher_policy(sim, s):
    return heuristic_actions(sim, s)


def test_heuristic_reaches_ground_truth_bench01():
    p = load_problem(BENCHMARKS_DIR / "benchmark_01.json")
    sim = Simulator(p)
    run = run_policy(sim, _teacher_policy)
    m = sim.metrics(run.final_state)
    assert m["plan_achievement"] >= p.ground_truth["plan_achievement"] - 1e-6


def test_heuristic_reaches_ground_truth_bench02_with_conversion():
    p = load_problem(BENCHMARKS_DIR / "benchmark_02.json")
    sim = Simulator(p)
    run = run_policy(sim, _teacher_policy)
    trace = run.legacy_trace
    m = sim.metrics(run.final_state)
    # PA 200 + PB 100 모두 달성 (전환 1h Idle 포함 4h 안에)
    assert m["plan_achievement"] >= 0.999
    # trace는 (hour, [moves], snapshot) 시퀀스
    assert len(trace) == p.horizon_hours
