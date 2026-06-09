from simulator import load_problem
from config import TEST_DATA_DIR, ASSIGN_TABLE, CONV_TABLE
import test as report
from report_output import ASSIGN_KEYS, build_conv_rows


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


def test_render_markdown_contains_output_tables(tmp_path):
    p = load_problem(TEST_DATA_DIR / "benchmark_02.json")
    res = report.evaluate_benchmark(p, model=None)
    md = report.render_markdown({"benchmark_02": (p, res)})
    assert "평균 계획달성률" in md
    assert "간트" in md
    assert ASSIGN_TABLE in md
    assert CONV_TABLE in md


def test_render_html_contains_output_tables(tmp_path):
    p = load_problem(TEST_DATA_DIR / "benchmark_01.json")
    res = report.evaluate_benchmark(p, model=None)
    from report_output import render_html_report
    html = render_html_report({"benchmark_01": (p, res)})
    assert ASSIGN_TABLE in html
    assert CONV_TABLE in html
    assert "EQP_ID" in html
    assert "START_TIME" in html


def test_run_eval_writes_html(tmp_path):
    md_path = tmp_path / "report.md"
    html_path = tmp_path / "report.html"
    report.run_eval(model=None, report_path=md_path, html_report_path=html_path)
    assert md_path.exists()
    assert html_path.exists()
    assert ASSIGN_TABLE in html_path.read_text(encoding="utf-8")


def test_evaluate_benchmark_includes_guide_allocation():
    p = load_problem(TEST_DATA_DIR / "benchmark_02.json")
    res = report.evaluate_benchmark(p, model=None)
    assert "guide_allocation" in res
    assert isinstance(res["guide_allocation"], dict)
    assert len(res["guide_allocation"]) > 0


def test_render_guide_table_output():
    from report_output import render_guide_table, guide_allocation_rows
    p = load_problem(TEST_DATA_DIR / "benchmark_02.json")
    res = report.evaluate_benchmark(p, model=None)
    md = render_guide_table(p, res["guide_allocation"])
    assert "가이드 수량" in md
    rows = [l for l in md.splitlines() if l.startswith("|") and "---" not in l]
    assert len(rows) >= 2  # 헤더 + 최소 1개 데이터 행
    zero_rows = guide_allocation_rows(p, {})
    assert all(r["target_count"] == 0 for r in zero_rows)
    assert all(isinstance(r["target_count"], int) for r in zero_rows)
    assert "가이드 수량" in render_guide_table(p, {})


def test_guide_allocation_rows():
    from report_output import guide_allocation_rows, render_guide_table
    p = load_problem(TEST_DATA_DIR / "benchmark_02.json")
    res = report.evaluate_benchmark(p, model=None)
    rows = guide_allocation_rows(p, res["guide_allocation"])
    assert len(rows) > 0
    assert "task" in rows[0]
    assert "model" in rows[0]
    assert "target_count" in rows[0]
    assert "/" in rows[0]["task"]
    md_rows = [l for l in render_guide_table(p, res["guide_allocation"]).splitlines()
               if l.startswith("|") and "---" not in l and "공정" not in l]
    assert len(md_rows) == len(rows)


def test_plan_target_allocation_int_sums_to_eqp_qty():
    from simulator import load_problem
    p = load_problem(TEST_DATA_DIR / "benchmark_09.json")
    alloc = p.plan_target_allocation_int()
    for model in p.models():
        total = sum(alloc.get((model, ti), 0) for ti in range(len(p.tasks)))
        assert total == p.eqp_qty[model]
        for (m, _ti), cnt in alloc.items():
            if m == model:
                assert isinstance(cnt, int)


def test_guide_allocation_rows_are_integers():
    from report_output import guide_allocation_rows
    p = load_problem(TEST_DATA_DIR / "benchmark_09.json")
    res = report.evaluate_benchmark(p, model=None)
    rows = guide_allocation_rows(p, res["guide_allocation"])
    assert len(rows) == len(p.tasks) * len(p.models())
    assert all(isinstance(r["target_count"], int) for r in rows)
