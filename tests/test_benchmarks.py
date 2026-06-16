import pytest
from simulator import load_problem, evaluate
from config import BENCHMARKS_DIR

BENCHES = sorted(BENCHMARKS_DIR.glob("*.json"))


@pytest.mark.parametrize("path", BENCHES, ids=lambda p: p.stem)
def test_heuristic_matches_ground_truth(path):
    p = load_problem(path)
    res = evaluate(p)
    opt = res["optimal"]
    assert opt is not None, f"{path.name}: ground_truth.plan_achievement 누락"
    # 일부 벤치마크는 휴리스틱이 최적에 미달하도록 설계됨 (RL 우위 검증용)
    # ground_truth.heuristic_target이 있으면 그 값 기준으로 허용오차 검사
    heuristic_target = p.ground_truth.get("heuristic_target", opt)
    assert res["heuristic"] >= heuristic_target - 0.02, (
        f"{path.name}: heuristic {res['heuristic']} < target {heuristic_target}")
    assert res["heuristic"] <= opt + 1e-6, (
        f"{path.name}: heuristic {res['heuristic']} > optimal {opt} (최적해 오류?)")

