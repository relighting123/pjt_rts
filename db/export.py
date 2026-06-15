"""DB 스냅샷 → data/inference · data/train JSON 변환.

추론 파이프라인: Oracle fetch → data/inference/{RULE_TIMEKEY}.json → infer
"""
from __future__ import annotations
import json
from pathlib import Path

import config
from simulator import save_problem


def export_from_rows(
    rows,
    output_path: str | Path,
    horizon_hours: int = 12,
    rule_timekey: str | None = None,
    switch_time_hours: int | None = None,
    facid: str | None = None,
    batchid: str | None = None,
) -> Path:
    """DB long-format 행 → inference JSON (가상 호기 {model}-{seq:03d})."""
    from db.adapter import rows_to_problem

    sw = switch_time_hours if switch_time_hours is not None else config.DEFAULT_SWITCH_TIME_HOURS
    fac = config.resolve_facid(facid)
    bid = config.resolve_batchid(batchid)
    problem = rows_to_problem(
        rows, horizon_hours, switch_time_hours=sw, rule_timekey=rule_timekey,
        facid=fac, batchid=bid,
    )
    return save_problem(problem, output_path, include_ground_truth=False)


def export_from_db(
    rule_timekey: str,
    output_path: str | Path | None = None,
    horizon_hours: int = 12,
    facid: str | None = None,
    batchid: str | None = None,
) -> Path:
    """Oracle RTS_LINEDSDB_INF → data/inference JSON."""
    from db.adapter import fetch_problem
    from db.pipeline import input_json_path

    fac = config.require_facid(facid)
    bid = config.require_batchid(batchid)
    problem = fetch_problem(
        rule_timekey=rule_timekey, horizon_hours=horizon_hours, facid=fac, batchid=bid,
    )
    out = Path(output_path) if output_path else input_json_path(rule_timekey, fac)
    return save_problem(problem, out, include_ground_truth=False)


def export_train_range(
    from_timekey: str | None = None,
    to_timekey: str | None = None,
    lookback_days: int | None = None,
    horizon_hours: int = 12,
    output_dir: Path | None = None,
    facid: str | None = None,
    batchid: str | None = None,
) -> list[Path]:
    """학습 구간 DB 스냅샷 → data/train/{RULE_TIMEKEY}.json."""
    from db.pipeline import export_train_snapshots

    return export_train_snapshots(
        from_timekey, to_timekey, lookback_days, horizon_hours, output_dir, facid, batchid,
    )


def export_from_sample_rows(output_path: str | Path | None = None) -> Path:
    """db/sample_rows.json (Oracle 없이) → data/inference/{RULE_TIMEKEY}.json."""
    sample_path = Path(__file__).parent / "sample_rows.json"
    meta = json.loads(sample_path.read_text(encoding="utf-8"))
    rows = [tuple(r) for r in meta["rows"]]
    rk = str(meta["rule_timekey"])
    default_out = config.INFERENCE_DATA_DIR / f"{rk}.json"
    out = Path(output_path) if output_path else default_out
    return export_from_rows(
        rows,
        out,
        horizon_hours=int(meta.get("horizon_hours", 12)),
        rule_timekey=meta.get("rule_timekey"),
        facid=meta.get("facid") or meta.get("fac_id"),
        batchid=meta.get("batchid") or "B1",
    )
