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


def test_cli_help():
    r = subprocess.run([sys.executable, "run.py", "--help"],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0
    assert "train" in r.stdout and "infer" in r.stdout and "eval" in r.stdout
