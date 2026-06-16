from src.utils.json_io import load_problem
from config import TEST_DATA_DIR
import src.evaluate as report
from src.utils.rows import ASSIGN_KEYS, guide_allocation_rows





def test_evaluate_benchmark_with_policy_returns_rates():

    p = load_problem(TEST_DATA_DIR / "benchmark_01.json")

    res = report.evaluate_benchmark(p, model=None)

    assert "heuristic" in res and "optimal" in res

    assert 0.0 <= res["heuristic"] <= 1.0

    assert "assign_rows" in res

    assert "conv_rows" in res

    assert "avg_utilization" in res





def test_assign_rows_eqp_and_seq():

    p = load_problem(TEST_DATA_DIR / "benchmark_01.json")

    res = report.evaluate_benchmark(p, model=None)

    rows = res["assign_rows"]

    assert len(rows) == p.horizon_hours

    assert rows[0]["EQP_ID"] == "M1-001"

    assert [r["SEQ_NO"] for r in rows] == [1, 2, 3]

    for key in ASSIGN_KEYS:

        assert key in rows[0]

    assert "EVENT_TM" not in rows[0]





def test_assign_seq_per_eqp_id():

    """SEQ는 전역이 아니라 EQP_ID(호기)별로 1부터 증가."""

    p = load_problem(TEST_DATA_DIR / "benchmark_05.json")

    res = report.evaluate_benchmark(p, model=None)

    rows = res["assign_rows"]

    by_eqp: dict[str, list[int]] = {}

    for row in rows:

        by_eqp.setdefault(row["EQP_ID"], []).append(row["SEQ_NO"])

    assert set(by_eqp) == {"M1-001", "M1-002"}

    assert by_eqp["M1-001"] == [1, 2]

    assert by_eqp["M1-002"] == [1, 2]





def test_conv_rows_on_benchmark_02():

    p = load_problem(TEST_DATA_DIR / "benchmark_02.json")

    res = report.evaluate_benchmark(p, model=None)

    assert len(res["conv_rows"]) >= 1





def test_evaluate_benchmark_includes_guide_allocation():

    p = load_problem(TEST_DATA_DIR / "benchmark_02.json")

    res = report.evaluate_benchmark(p, model=None)

    assert "guide_allocation" in res

    assert isinstance(res["guide_allocation"], dict)

    assert len(res["guide_allocation"]) > 0





def test_guide_allocation_rows():

    p = load_problem(TEST_DATA_DIR / "benchmark_02.json")

    res = report.evaluate_benchmark(p, model=None)

    rows = guide_allocation_rows(p, res["guide_allocation"])

    assert len(rows) > 0

    assert "task" in rows[0]

    assert "model" in rows[0]

    assert "target_count" in rows[0]

    assert "/" in rows[0]["task"]

    zero_rows = guide_allocation_rows(p, {})

    assert all(r["target_count"] == 0 for r in zero_rows)

    assert all(isinstance(r["target_count"], int) for r in zero_rows)





def test_plan_target_allocation_int_sums_to_eqp_qty():

    p = load_problem(TEST_DATA_DIR / "benchmark_09.json")

    alloc = p.plan_target_allocation_int()

    for model in p.models():

        total = sum(alloc.get((model, ti), 0) for ti in range(len(p.tasks)))

        assert total == p.eqp_qty[model]

        for (m, _ti), cnt in alloc.items():

            if m == model:

                assert isinstance(cnt, int)





def test_guide_allocation_rows_are_integers():

    p = load_problem(TEST_DATA_DIR / "benchmark_09.json")

    res = report.evaluate_benchmark(p, model=None)

    rows = guide_allocation_rows(p, res["guide_allocation"])

    assert len(rows) == len(p.tasks) * len(p.models())

    assert all(isinstance(r["target_count"], int) for r in rows)


