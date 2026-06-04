from simulator import load_problem
from config import BENCHMARKS_DIR
import train
import test as report


def test_rl_eval_skips_on_shape_mismatch():
    # bench01: 1 task/1 model (obs 4). bench02: 2 tasks/1 model (obs 7).
    b1 = load_problem(BENCHMARKS_DIR / "benchmark_01.json")
    b2 = load_problem(BENCHMARKS_DIR / "benchmark_02.json")
    model = train.train_model([b1], ppo_steps=64, bc_epochs=2, save_path=None)
    # 같은 shape(b1): RL 평가 수행
    res1 = report.evaluate_benchmark(b1, model)
    assert "rl" in res1
    # 다른 shape(b2): RL 건너뛰고 휴리스틱만
    res2 = report.evaluate_benchmark(b2, model)
    assert "rl" not in res2
