import subprocess, sys
from config import ROOT


def test_cli_eval_runs_and_writes_report(tmp_path):
    out = tmp_path / "report.md"
    r = subprocess.run(
        [sys.executable, "run.py", "eval", "--no-model", "--report", str(out)],
        cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert out.exists()
    assert "평균 계획달성률" in out.read_text(encoding="utf-8")


def test_cli_infer_writes_html(tmp_path):
    html_out = tmp_path / "out.html"
    md_out = tmp_path / "out.md"
    r = subprocess.run(
        [sys.executable, "run.py", "infer",
         "--benchmark-dataset", "benchmarks/benchmark_01",
         "--html", str(html_out), "--report", str(md_out)],
        cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert html_out.exists(), r.stdout + r.stderr
    assert "RTS_ASSIGN_INF" in html_out.read_text(encoding="utf-8")
    assert "HTML 리포트" in r.stdout


def test_cli_help():
    r = subprocess.run([sys.executable, "run.py", "--help"],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0
    assert "train" in r.stdout and "infer" in r.stdout and "eval" in r.stdout


def test_infer_prints_guide_and_dynamic(capsys, tmp_path):
    import run
    from config import BENCHMARKS_DIR
    args = run.build_parser().parse_args([
        "infer", "--benchmark-dataset", str(BENCHMARKS_DIR / "benchmark_01"),
        "--report", str(tmp_path / "r.md"), "--html", str(tmp_path / "r.html"),
    ])
    args.func(args)
    out = capsys.readouterr().out
    assert "가이드" in out
    assert "동적 운영" in out
