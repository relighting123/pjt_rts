from simulator import load_problem
from config import BENCHMARKS_DIR
import test as report


def test_evaluate_benchmark_with_policy_returns_rates():
    p = load_problem(BENCHMARKS_DIR / "benchmark_01.json")
    # 정책 없이(휴리스틱만) 평가 — RL 없어도 동작
    res = report.evaluate_benchmark(p, model=None)
    assert "heuristic" in res and "optimal" in res
    assert 0.0 <= res["heuristic"] <= 1.0


def test_render_markdown_contains_average_and_gantt(tmp_path):
    p = load_problem(BENCHMARKS_DIR / "benchmark_02.json")
    res = report.evaluate_benchmark(p, model=None)
    md = report.render_markdown({"benchmark_02": (p, res)})
    assert "평균 계획달성률" in md
    assert "간트" in md or "Gantt" in md
