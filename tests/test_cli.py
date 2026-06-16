import subprocess, sys
from config import ROOT


def test_cli_eval_runs(tmp_path):
    r = subprocess.run(
        [sys.executable, "run.py", "eval", "--no-model"],
        cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "H=" in r.stdout
    assert "결과 확인" in r.stdout


def test_cli_infer_benchmark_prints_summary(tmp_path):
    r = subprocess.run(
        [sys.executable, "run.py", "infer", "--benchmark-dataset", "benchmark_01"],
        cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "H=" in r.stdout
    assert "결과 확인" in r.stdout


def test_cli_help():
    r = subprocess.run([sys.executable, "run.py", "--help"],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0
    assert "train" in r.stdout and "infer" in r.stdout and "eval" in r.stdout and "export" in r.stdout


def test_infer_prints_ui_url(capsys, tmp_path):
    import run
    from config import BENCHMARKS_DIR
    args = run.build_parser().parse_args([
        "infer", "--benchmark-dataset", str(BENCHMARKS_DIR / "benchmark_01"),
    ])
    args.func(args)
    out = capsys.readouterr().out
    assert "결과 확인" in out
    assert "H=" in out
