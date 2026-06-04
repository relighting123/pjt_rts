from simulator import load_problem
from config import BENCHMARKS_DIR
import test as report
from report_output import TASK_DETAIL_KEYS


def test_evaluate_benchmark_with_policy_returns_rates():
    p = load_problem(BENCHMARKS_DIR / "benchmark_01.json")
    res = report.evaluate_benchmark(p, model=None)
    assert "heuristic" in res and "optimal" in res
    assert 0.0 <= res["heuristic"] <= 1.0
    assert "task_hourly_rows" in res
    assert "avg_utilization" in res


def test_task_hourly_rows_required_columns():
    p = load_problem(BENCHMARKS_DIR / "benchmark_01.json")
    res = report.evaluate_benchmark(p, model=None)
    rows = res["task_hourly_rows"]
    assert len(rows) == p.horizon_hours  # 1대 × 3시간
    event_tms = set()
    for row in rows:
        for key in TASK_DETAIL_KEYS:
            assert key in row
        assert row["ACHIEVE_RATE"] <= 1.0
        assert row["RULE_TIMEKEY"] == p.rule_timekey
        assert row["EQP_ID"] == "M1-001"
        assert row["SEQ_NO"] >= 1
        event_tms.add(row["EVENT_TM"])
    assert len(event_tms) == p.horizon_hours
    assert rows[0]["SEQ_NO"] == 1
    assert rows[-1]["SEQ_NO"] == p.horizon_hours


def test_allocation_rows_db_schema():
    p = load_problem(BENCHMARKS_DIR / "benchmark_01.json")
    res = report.evaluate_benchmark(p, model=None)
    from report_output import ALLOC_DB_KEYS
    for row in res["allocation_rows"]:
        for key in ALLOC_DB_KEYS:
            assert key in row
        assert "BATCH_ID" not in row


def test_render_markdown_contains_average_and_gantt(tmp_path):
    p = load_problem(BENCHMARKS_DIR / "benchmark_02.json")
    res = report.evaluate_benchmark(p, model=None)
    md = report.render_markdown({"benchmark_02": (p, res)})
    assert "평균 계획달성률" in md
    assert "간트" in md
    assert "RULE_TIMEKEY" in md
    assert "ACHIEVE_RATE" in md
    assert "평균 장비 가동률" in md or "가동률" in md


def test_render_html_contains_required_fields(tmp_path):
    p = load_problem(BENCHMARKS_DIR / "benchmark_01.json")
    res = report.evaluate_benchmark(p, model=None)
    from report_output import render_html_report
    html = render_html_report({"benchmark_01": (p, res)})
    assert "<table>" in html
    for col in (
        "RULE_TIMEKEY", "EVENT_TM", "EQP_ID", "EQP_MODEL_CD", "SEQ",
        "BATCH_ID", "PLAN_PROD_KEY", "ACHIEVE_RATE", "PRODUCE_QTY",
    ):
        assert col in html
    assert "commit" in html


def test_run_eval_writes_html(tmp_path):
    md_path = tmp_path / "report.md"
    html_path = tmp_path / "report.html"
    report.run_eval(model=None, report_path=md_path, html_report_path=html_path)
    assert md_path.exists()
    assert html_path.exists()
    assert "ACHIEVE_RATE" in html_path.read_text(encoding="utf-8")
