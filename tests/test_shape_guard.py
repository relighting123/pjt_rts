from src.utils.json_io import load_problem
from config import BENCHMARKS_DIR
from src.training.dispatch import train_model
import src.evaluate as report


def test_rl_eval_applies_within_padding():
    # 고정 패딩(MAX_TASKS/MAX_MODELS) 설계 — 동일 패딩 내 모든 문제에 RL 적용 가능
    b1 = load_problem(BENCHMARKS_DIR / "benchmark_01.json")
    b2 = load_problem(BENCHMARKS_DIR / "benchmark_02.json")
    model = train_model([b1], ppo_steps=64, bc_epochs=2, save_path=None)
    # 두 벤치마크 모두 MAX_TASKS/MAX_MODELS 내 → 같은 obs/action 공간 → RL 적용
    res1 = report.evaluate_benchmark(b1, model)
    assert "rl" in res1
    res2 = report.evaluate_benchmark(b2, model)
    assert "rl" in res2  # 패딩으로 동일 shape → RL 적용


def test_rl_eval_skips_on_none_model():
    b1 = load_problem(BENCHMARKS_DIR / "benchmark_01.json")
    res = report.evaluate_benchmark(b1, model=None)
    assert "rl" not in res
