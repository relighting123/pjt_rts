from simulator import load_problem
from config import BENCHMARKS_DIR, PLAN_ACHV_TABLE, ASSIGN_TABLE, CONV_TABLE
import test as report
from report_output import PLAN_ACHV_KEYS, ASSIGN_KEYS, build_conv_rows


def test_evaluate_benchmark_with_policy_returns_rates():
    p = load_problem(BENCHMARKS_DIR / "benchmark_01.json")
    res = report.evaluate_benchmark(p, model=None)
    assert "heuristic" in res and "optimal" in res
    assert 0.0 <= res["heuristic"] <= 1.0
    assert "plan_achv_rows" in res
    assert "assign_rows" in res
    assert "conv_rows" in res
    assert "avg_utilization" in res


def test_plan_achv_rows_required_columns():
    p = load_problem(BENCHMARKS_DIR / "benchmark_01.json")
    res = report.evaluate_benchmark(p, model=None)
    rows = res["plan_achv_rows"]
    assert len(rows) == p.horizon_hours * len(p.tasks)
    event_tms = set()
    for row in rows:
        for key in PLAN_ACHV_KEYS:
            assert key in row
        assert row["ACHIEVE_RATE"] <= 1.0
        assert row["RULE_TIMEKEY"] == p.rule_timekey
        event_tms.add(row["EVENT_TM"])
    assert len(event_tms) == p.horizon_hours


def test_assign_rows_eqp_and_seq():
    p = load_problem(BENCHMARKS_DIR / "benchmark_01.json")
    res = report.evaluate_benchmark(p, model=None)
    rows = res["assign_rows"]
    assert len(rows) == p.horizon_hours
    assert rows[0]["EQP_ID"] == "M1-001"
    assert [r["SEQ_NO"] for r in rows] == [1, 2, 3]
    for key in ASSIGN_KEYS:
        assert key in rows[0]


def test_assign_seq_per_eqp_id():
    """SEQ는 전역이 아니라 EQP_ID(호기)별로 1부터 증가."""
    p = load_problem(BENCHMARKS_DIR / "benchmark_05.json")
    res = report.evaluate_benchmark(p, model=None)
    rows = res["assign_rows"]
    by_eqp: dict[str, list[int]] = {}
    for row in rows:
        by_eqp.setdefault(row["EQP_ID"], []).append(row["SEQ_NO"])
    assert set(by_eqp) == {"M1-001", "M1-002"}
    assert by_eqp["M1-001"] == [1, 2]
    assert by_eqp["M1-002"] == [1, 2]


def test_conv_rows_on_benchmark_02():
    p = load_problem(BENCHMARKS_DIR / "benchmark_02.json")
    res = report.evaluate_benchmark(p, model=None)
    assert len(res["conv_rows"]) >= 1


def test_render_markdown_contains_output_tables(tmp_path):
    p = load_problem(BENCHMARKS_DIR / "benchmark_02.json")
    res = report.evaluate_benchmark(p, model=None)
    md = report.render_markdown({"benchmark_02": (p, res)})
    assert "평균 계획달성률" in md
    assert "간트" in md
    assert PLAN_ACHV_TABLE in md
    assert ASSIGN_TABLE in md
    assert CONV_TABLE in md


def test_render_html_contains_output_tables(tmp_path):
    p = load_problem(BENCHMARKS_DIR / "benchmark_01.json")
    res = report.evaluate_benchmark(p, model=None)
    from report_output import render_html_report
    html = render_html_report({"benchmark_01": (p, res)})
    assert PLAN_ACHV_TABLE in html
    assert ASSIGN_TABLE in html
    assert CONV_TABLE in html
    assert "EQP_ID" in html
    assert "EVENT_TM" in html


def test_run_eval_writes_html(tmp_path):
    md_path = tmp_path / "report.md"
    html_path = tmp_path / "report.html"
    report.run_eval(model=None, report_path=md_path, html_report_path=html_path)
    assert md_path.exists()
    assert html_path.exists()
    assert ASSIGN_TABLE in html_path.read_text(encoding="utf-8")


def test_evaluate_benchmark_includes_guide_allocation():
    from simulator import load_problem
    from config import BENCHMARKS_DIR
    import test as report
    p = load_problem(BENCHMARKS_DIR / "benchmark_02.json")
    res = report.evaluate_benchmark(p, model=None)
    assert "guide_allocation" in res
    assert isinstance(res["guide_allocation"], dict)
    assert len(res["guide_allocation"]) > 0
