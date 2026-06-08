#!/usr/bin/env python3
"""Step 1: Oracle DB 연결 및 MAX(RULE_TIMEKEY) 조회 테스트.

사용:
  pip install oracledb python-dotenv
  cp .env.example .env   # 접속 정보 입력
  PYTHONPATH=. python3 scripts/test_db_step1_connect.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    try:
        import oracledb  # noqa: F401
    except ImportError:
        print("FAIL: oracledb 미설치 — pip install oracledb python-dotenv")
        return 1

    import config
    from db.adapter import _connect, fetch_max_timekey

    cfg = config.load_config()
    print("=== Step 1: DB 연결 테스트 ===")
    print(f"user : {cfg['user']}")
    print(f"dsn  : {cfg['dsn']}")

    try:
        conn = _connect()
        print("OK   : 연결 성공")
        conn.close()
    except Exception as exc:
        print(f"FAIL : 연결 실패 — {exc}")
        return 1

    try:
        tk = fetch_max_timekey()
        print(f"OK   : MAX(RULE_TIMEKEY) = {tk}")
    except Exception as exc:
        print(f"FAIL : MAX(RULE_TIMEKEY) 조회 실패 — {exc}")
        return 1

    print("Step 1 완료")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
