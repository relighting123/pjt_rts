import pytest
from simulator import load_problem, evaluate
from config import BENCHMARKS_DIR

BENCHES = sorted(BENCHMARKS_DIR.glob("benchmark_*.json"))


@pytest.mark.parametrize("path", BENCHES, ids=lambda p: p.stem)
def test_heuristic_matches_ground_truth(path):
    p = load_problem(path)
    res = evaluate(p)
    opt = res["optimal"]
    assert opt is not None, f"{path.name}: ground_truth.plan_achievement 누락"
    # 휴리스틱은 최적 이하이되, 설계상 최적에 도달해야 함(허용오차 2%p)
    assert res["heuristic"] >= opt - 0.02, (
        f"{path.name}: heuristic {res['heuristic']} < optimal {opt}")
    assert res["heuristic"] <= opt + 1e-6, (
        f"{path.name}: heuristic {res['heuristic']} > optimal {opt} (최적해 오류?)")
