#!/usr/bin/env python3
"""Step 1: Oracle DB 연결 및 MAX(RULE_TIMEKEY) 조회 테스트.

사용:
  pip install oracledb python-dotenv
  cp .env.example .env   # DEFAULT_FACID 포함
  PYTHONPATH=. python3 scripts/test_db_step1_connect.py
  PYTHONPATH=. python3 scripts/test_db_step1_connect.py --facid ICPRB
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Step 1: DB 연결 + MAX(RULE_TIMEKEY)")
    p.add_argument("--facid", help="facid 필수 (.env DEFAULT_FACID 가능)")
    return p.parse_args()


def main() -> int:
    try:
        import oracledb  # noqa: F401
    except ImportError:
        print("FAIL: oracledb 미설치 — pip install oracledb python-dotenv")
        return 1

    args = _parse_args()
    import config
    from src.db.adapter import _connect, fetch_max_timekey

    try:
        fac = config.require_facid(args.facid)
    except ValueError as exc:
        print(f"FAIL : {exc}")
        return 1

    cfg = config.load_config()
    print("=== Step 1: DB 연결 테스트 ===")
    print(f"user : {cfg['user']}")
    print(f"dsn  : {cfg['dsn']}")
    print(f"facid: {fac}")

    try:
        conn = _connect()
        print("OK   : 연결 성공")
        conn.close()
    except Exception as exc:
        print(f"FAIL : 연결 실패 — {exc}")
        return 1

    try:
        tk = fetch_max_timekey(fac)
        print(f"OK   : MAX(RULE_TIMEKEY) [{fac}] = {tk}")
    except Exception as exc:
        print(f"FAIL : MAX(RULE_TIMEKEY) 조회 실패 — {exc}")
        return 1

    print("Step 1 완료")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
