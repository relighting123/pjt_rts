"""DB ↔ JSON 파이프라인 오케스트레이션.

추론: resolve timekey → input JSON → infer → result JSON → DB write
학습: timekey 범위(또는 최근 30일) → train JSON export → 학습
"""
from __future__ import annotations
from pathlib import Path

import config
from simulator import load_problem
from report_output import (
    build_inference_result_document,
    save_inference_result_document,
    load_inference_result_document,
)


def snapshot_key(rule_timekey: str, facid: str | None = None) -> str:
    """JSON 파일 stem: {timekey} 또는 {timekey}_{facid}."""
    rk = str(rule_timekey)
    if facid:
        return f"{rk}_{facid}"
    return rk


def input_json_path(rule_timekey: str, facid: str | None = None) -> Path:
    return config.INFERENCE_DATA_DIR / f"{snapshot_key(rule_timekey, facid)}.json"


def result_json_path(rule_timekey: str, facid: str | None = None) -> Path:
    return config.INFERENCE_DATA_DIR / f"{snapshot_key(rule_timekey, facid)}_result.json"


def export_input_json(
    rule_timekey: str | None = None,
    horizon_hours: int = 12,
    output_path: Path | None = None,
    facid: str | None = None,
) -> tuple[str, str, Path]:
    """DB → data/inference JSON. (timekey, facid, path) 반환."""
    from db.export import export_from_db

    from db.adapter import resolve_timekey

    rk = resolve_timekey(rule_timekey)
    fac = config.require_facid(facid)
    out = output_path or input_json_path(rk, fac)
    path = export_from_db(rk, output_path=out, horizon_hours=horizon_hours, facid=fac)
    return rk, fac, path


def export_train_snapshots(
    from_timekey: str | None = None,
    to_timekey: str | None = None,
    lookback_days: int | None = None,
    horizon_hours: int = 12,
    output_dir: Path | None = None,
    facid: str | None = None,
) -> list[Path]:
    """DB 구간(또는 최근 N일) → data/train/{RULE_TIMEKEY}.json."""
    from db.adapter import list_timekeys_in_range
    from db.export import export_from_db

    fac = config.require_facid(facid)
    out_dir = Path(output_dir) if output_dir else config.TRAIN_DATA_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for rk in list_timekeys_in_range(from_timekey, to_timekey, lookback_days):
        stem = snapshot_key(rk, fac)
        paths.append(export_from_db(
            rk, output_path=out_dir / f"{stem}.json",
            horizon_hours=horizon_hours, facid=fac,
        ))
    return paths


def run_inference(
    rule_timekey: str | None = None,
    *,
    facid: str | None = None,
    horizon_hours: int = 12,
    skip_input_export: bool = False,
    input_path: Path | None = None,
    write_db: bool = True,
    write_report: bool = True,
    report_path: Path | None = None,
    html_path: Path | None = None,
    policy: str = "RL",
):
    """DB→input JSON→추론→result JSON→(선택)DB write→(선택)MD/HTML."""
    import test as report
    from pathlib import Path as P

    rk = str(rule_timekey) if rule_timekey else None
    fac = config.require_facid(facid)
    if input_path is None:
        if skip_input_export:
            if rk is None:
                raise ValueError("skip_input_export 시 rule_timekey 필요")
            inp = input_json_path(rk, fac)
            if not inp.is_file():
                raise FileNotFoundError(
                    f"입력 JSON 없음: {inp}\n"
                    f"  python run.py export --timekey {rk} --facid {fac}"
                )
        else:
            rk, fac, inp = export_input_json(rk, horizon_hours, facid=fac)
    else:
        inp = Path(input_path)
        problem_probe = load_problem(inp)
        rk = problem_probe.rule_timekey
        fac = problem_probe.facid or fac

    problem = load_problem(inp)
    model = None
    if P(config.MODEL_PATH).exists():
        from sb3_contrib import MaskablePPO
        model = MaskablePPO.load(config.MODEL_PATH)

    eval_result = report.evaluate_benchmark(problem, model)
    result_doc = build_inference_result_document(problem, eval_result, policy=policy)
    result_path = save_inference_result_document(result_doc, result_json_path(rk, fac))

    if write_db:
        from db.adapter import write_inference_result
        write_inference_result(rk, result_doc)

    report_paths = None
    if write_report:
        stem = snapshot_key(rk, fac)
        md_default, html_default = (
            config.ARTIFACTS_DIR / "inference" / f"{stem}.md",
            config.ARTIFACTS_DIR / "inference" / f"{stem}.html",
        )
        md_p = report_path or md_default
        html_p = html_path or html_default
        report.write_report_files({stem: (problem, eval_result)}, md_p, html_p)
        report_paths = (md_p, html_p)

    rate = eval_result.get("rl", eval_result["heuristic"])
    return {
        "rule_timekey": rk,
        "facid": fac,
        "input_json": inp,
        "result_json": result_path,
        "plan_achievement": float(rate),
        "result_doc": result_doc,
        "report_paths": report_paths,
    }


def load_train_problems_from_export(export_dir: Path | None = None) -> list:
    from simulator import load_problem

    directory = export_dir or config.TRAIN_DATA_DIR
    return [load_problem(p) for p in sorted(Path(directory).glob("*.json"))]
