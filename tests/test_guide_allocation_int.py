from src.utils.json_io import load_problem
from config import TEST_DATA_DIR


def test_largest_remainder_preserves_total():
    from src.simulation.domain.problem import largest_remainder
    assert sum(largest_remainder([0.67, 0.67, 0.67], 2)) == 2
    assert largest_remainder([1.2, 0.8], 2) == [1, 1]


def test_analytic_guide_matches_eqp_qty_per_model():
    p = load_problem(TEST_DATA_DIR / "benchmark_02.json")
    guide = p.complete_guide_allocation(p.plan_target_allocation_int())
    for model in p.models():
        assert sum(guide.get((model, ti), 0) for ti in range(len(p.tasks))) == p.eqp_qty[model]
