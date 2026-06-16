"""정적 달성률 산식 테스트."""
from pathlib import Path

from src.utils.json_io import load_problem
from src.views.pivot import static_task_rate
from src.stages.allocation.use_case import allocate
import config


def test_static_rate_benchmark01():
    p = load_problem(config.TEST_DATA_DIR / "benchmark_01.json")
    guide = allocate(p).as_dict()
    produced, rate = static_task_rate(p, guide, 0)
    assert produced == 100
    assert abs(rate - 1 / 3) < 1e-6


def test_static_rate_benchmark05():
    p = load_problem(config.TEST_DATA_DIR / "benchmark_05.json")
    guide = allocate(p).as_dict()
    produced, rate = static_task_rate(p, guide, 0)
    assert produced == 400
    assert abs(rate - 0.4) < 1e-6
