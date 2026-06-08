"""Oracle live DB 테스트 (ORACLE_LIVE_TEST=1 + .env 필요).

CI/로컬 기본 pytest에서는 skip. scripts/test_db_step*.py 로 수동 실행 가능.
"""
from __future__ import annotations

import os
import subprocess
import sys

import pytest

import config

ROOT = config.ROOT
SCRIPTS = ROOT / "scripts"

pytestmark = pytest.mark.skipif(
    os.getenv("ORACLE_LIVE_TEST") != "1",
    reason="Set ORACLE_LIVE_TEST=1 and configure .env for live Oracle tests",
)


def _run_script(name: str, *extra: str) -> subprocess.CompletedProcess:
    script = SCRIPTS / name
    assert script.is_file(), f"missing {script}"
    return subprocess.run(
        [sys.executable, str(script), *extra],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        capture_output=True,
        text=True,
    )


def test_step1_connect_script():
    r = _run_script("test_db_step1_connect.py")
    assert r.returncode == 0, r.stdout + r.stderr


def test_step2_fetch_rows_script():
    r = _run_script("test_db_step2_fetch_rows.py")
    assert r.returncode == 0, r.stdout + r.stderr


def test_step2_fetch_rows_export(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "INFERENCE_DATA_DIR", tmp_path)
    r = _run_script("test_db_step2_fetch_rows.py", "--export")
    assert r.returncode == 0, r.stdout + r.stderr
    assert list(tmp_path.glob("*.json")), "export JSON not created"
