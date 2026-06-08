#!/usr/bin/env python3
"""Step 2: fetch_rows → rows_to_problem → data/inference JSON export.

사용:
  PYTHONPATH=. python3 scripts/test_db_step2_fetch_rows.py --facid ICPRB --batchid B1
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Step 2: fetch_rows DB 읽기 테스트")
    p.add_argument("--timekey", help="RULE_TIMEKEY (미지정 시 MAX)")
    p.add_argument("--facid", help="facid 필수 (.env DEFAULT_FACID 가능)")
    p.add_argument("--batchid", help="batchid 필수 (.env DEFAULT_BATCHID 가능, LIKE %값%)")
    p.add_argument("--horizon", type=int, default=12)
    p.add_argument("--no-export", action="store_true")
    p.add_argument("--output")
    return p.parse_args()


def main() -> int:
    try:
        import oracledb  # noqa: F401
    except ImportError:
        print("FAIL: oracledb 미설치 — pip install oracledb python-dotenv")
        return 1

    args = _parse_args()
    from db.adapter import fetch_rows, resolve_timekey, rows_to_problem
    from db.export import export_from_rows
    from db.pipeline import input_json_path
    import config
    from ops_log import log_ops, OPS_LOG_PATH

    print("=== Step 2: fetch_rows 테스트 ===")

    try:
        fac = config.require_facid(args.facid)
        bid = config.require_batchid(args.batchid)
    except ValueError as exc:
        print(f"FAIL : {exc}")
        return 1

    try:
        tk = resolve_timekey(args.timekey, facid=fac)
        if args.timekey is None:
            print(f"timekey: MAX(RULE_TIMEKEY) = {tk}")
        else:
            print(f"timekey: {tk}")
        print(f"facid: {fac}")
        print(f"batchid LIKE %{bid}%")
        log_ops(
            "step2.start",
            rule_timekey=args.timekey or "MAX",
            facid=fac,
            batchid=bid,
            batchid_like=f"%{bid}%",
            horizon_hours=args.horizon,
            no_export=args.no_export,
            ops_log=OPS_LOG_PATH,
        )
    except Exception as exc:
        print(f"FAIL : timekey 확인 실패 — {exc}")
        return 1

    try:
        rows = fetch_rows(tk, facid=fac, batchid=bid)
    except Exception as exc:
        print(f"FAIL : fetch_rows 실패 — {exc}")
        return 1

    if not rows:
        print(f"FAIL : {tk} / facid={fac} / batchid LIKE %{bid}% 행 없음")
        return 1

    print(f"OK   : fetch_rows — {len(rows)}행")
    print(f"sample row: {rows[0]}")

    gbn_counts = Counter(r[7] for r in rows)
    print("GBN_CD 분포:", dict(sorted(gbn_counts.items())))

    try:
        problem = rows_to_problem(
            rows, args.horizon, rule_timekey=tk, facid=fac, batchid=bid,
        )
    except Exception as exc:
        print(f"FAIL : rows_to_problem 실패 — {exc}")
        return 1

    print(f"OK   : rows_to_problem — task {len(problem.tasks)}개, model {len(problem.models())}개")
    if problem.tasks:
        t0 = problem.tasks[0]
        print(
            f"       첫 task: {t0.plan_prod_key}/{t0.oper_id} "
            f"plan={t0.plan_qty} wip={t0.wip_qty}"
        )

    if not args.no_export:
        out = Path(args.output) if args.output else input_json_path(tk, fac)
        try:
            path = export_from_rows(
                rows, out, horizon_hours=args.horizon, rule_timekey=tk,
                facid=fac, batchid=bid,
            )
            print(f"OK   : JSON 저장 → {path}")
            print(f"       inference 폴더: {path.parent}")
        except Exception as exc:
            print(f"FAIL : JSON export 실패 — {exc}")
            return 1
    else:
        print("SKIP : JSON export (--no-export)")

    log_ops(
        "step2.done",
        rule_timekey=tk,
        facid=fac,
        batchid=bid,
        row_count=len(rows),
        task_count=len(problem.tasks),
    )
    print("Step 2 완료")
    print(f"ops 로그 → {OPS_LOG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
