"""CLI 디스패처: train / infer / eval / export.

데이터 경로:
  data/train/              — 학습 JSON ({RULE_TIMEKEY}.json, DB export 포함)
  data/test/               — 평가·Streamlit 벤치마크
  data/inference/          — 추론 입력·결과 JSON

추론(운영): DB → data/inference/{timekey}.json → infer → {timekey}_result.json → DB write
학습(운영): DB 구간(또는 최근 30일) → data/train/{timekey}.json → train
"""
from __future__ import annotations
import argparse
from pathlib import Path
import config


def _resolve_json_path(path: str | Path) -> Path:
    p = Path(path)
    if not p.suffix:
        p = p.with_suffix(".json")
    if p.is_file():
        return p
    for base in (
        config.INFERENCE_DATA_DIR,
        config.TEST_DATA_DIR,
        config.TRAIN_DATA_DIR,
    ):
        cand = base / p.name
        if cand.is_file():
            return cand
    return p


def _load_named_problems(args) -> list[tuple[str, object]]:
    from simulator import load_problem

    if getattr(args, "dataset", None):
        path = _resolve_json_path(args.dataset)
        return [(path.stem, load_problem(path))]

    if args.benchmark_dataset:
        path = _resolve_json_path(args.benchmark_dataset)
        return [(path.stem, load_problem(path))]

    if getattr(args, "timekey", None):
        from db.pipeline import input_json_path, snapshot_key
        fac = config.require_facid(getattr(args, "facid", None))
        key = snapshot_key(str(args.timekey), fac)
        path = input_json_path(str(args.timekey), fac)
        if not path.is_file():
            raise FileNotFoundError(
                f"{path} 없음. DB export:\n"
                f"  python run.py export --timekey {args.timekey} --facid {fac}"
            )
        return [(key, load_problem(path))]

    return [(p.stem, load_problem(p)) for p in sorted(config.TEST_DATA_DIR.glob("*.json"))]


def _load_problems(args, default_dir: Path | None = None):
    from simulator import load_problem
    if getattr(args, "use_db", False):
        from db.pipeline import load_train_problems_from_export
        return load_train_problems_from_export()
    if getattr(args, "dataset", None) or args.benchmark_dataset or getattr(args, "timekey", None):
        return [p for _, p in _load_named_problems(args)]
    directory = default_dir or config.TRAIN_DATA_DIR
    return [load_problem(p) for p in sorted(Path(directory).glob("*.json"))]


def cmd_train(args):
    if args.use_db or args.from_timekey or args.to_timekey:
        from db.export import export_train_range
        paths = export_train_range(
            args.from_timekey, args.to_timekey, args.lookback_days, args.horizon,
            facid=getattr(args, "facid", None),
            batchid=getattr(args, "batchid", None),
        )
        print(f"DB → JSON {len(paths)}건 → {config.TRAIN_DATA_DIR}")
        args.use_db = True

    import train
    problems = _load_problems(args, default_dir=config.TRAIN_DATA_DIR)
    if not problems:
        raise SystemExit("학습 문제 없음. --use-db 또는 data/train/ JSON 확인.")
    train.train_model(problems, ppo_steps=args.steps)
    print(f"학습 완료 → {config.MODEL_PATH}")
    import test as report
    from sb3_contrib import MaskablePPO
    model = MaskablePPO.load(config.MODEL_PATH)
    report.run_eval(model=model)
    print(f"평가 리포트 → {config.REPORT_PATH}")


def cmd_eval(args):
    import test as report
    model = None
    if Path(config.MODEL_PATH).exists() and not args.no_model:
        from sb3_contrib import MaskablePPO
        model = MaskablePPO.load(config.MODEL_PATH)
    report_path = Path(args.report) if args.report else config.REPORT_PATH
    report.run_eval(model=model, report_path=report_path)
    print(f"평가 리포트 → {report_path}")


def cmd_infer(args):
    if getattr(args, "dataset", None) or args.benchmark_dataset:
        import test as report
        named = _load_named_problems(args)
        problems = [p for _, p in named]
        model = None
        if Path(config.MODEL_PATH).exists():
            from sb3_contrib import MaskablePPO
            model = MaskablePPO.load(config.MODEL_PATH)
        results = {}
        for name, p in named:
            res = report.evaluate_benchmark(p, model)
            results[name] = (p, res)
        md_default, html_default = report.default_infer_report_paths(problems, args)
        report_path = Path(args.report) if getattr(args, "report", None) else md_default
        html_path = Path(args.html) if getattr(args, "html", None) else html_default
        report.write_report_files(results, report_path, html_path)
        print(f"평가 리포트 → {report_path}")
        return

    from db.pipeline import run_inference

    out = run_inference(
        args.timekey,
        facid=getattr(args, "facid", None),
        batchid=getattr(args, "batchid", None),
        horizon_hours=args.horizon,
        skip_input_export=args.skip_export,
        write_db=not args.no_db,
        write_report=not args.no_report,
        report_path=Path(args.report) if getattr(args, "report", None) else None,
        html_path=Path(args.html) if getattr(args, "html", None) else None,
    )
    label = out["rule_timekey"] + (f" [{out['facid']}]" if out.get("facid") else "")
    print(f"{label}: 입력 JSON → {out['input_json']}")
    print(f"{label}: 결과 JSON → {out['result_json']}")
    print(f"[동적 운영] 평균 계획달성률 {out['plan_achievement']:.3f}")
    if not args.no_db:
        print("DB 기록 완료 (RTS_GUIDE / PLAN_ACHV / ASSIGN / CONV)")
    if out.get("report_paths"):
        print(f"리포트 → {out['report_paths'][0]}")


def cmd_export(args):
    from db.export import export_from_db, export_from_sample_rows, export_train_range

    if args.sample:
        path = export_from_sample_rows(output_path=args.output)
        print(f"input JSON 저장 → {path}")
        return
    if args.train:
        paths = export_train_range(
            args.from_timekey, args.to_timekey, args.lookback_days, args.horizon,
            facid=getattr(args, "facid", None),
            batchid=getattr(args, "batchid", None),
        )
        print(f"학습 JSON {len(paths)}건 → {config.TRAIN_DATA_DIR}")
        return
    fac = config.require_facid(getattr(args, "facid", None))
    bid = config.require_batchid(getattr(args, "batchid", None))
    if not args.timekey:
        from db.adapter import resolve_timekey
        args.timekey = resolve_timekey(None, facid=fac)
        print(f"--timekey 미지정 → MAX(RULE_TIMEKEY) [{fac}] = {args.timekey}")
    path = export_from_db(
        args.timekey, output_path=args.output, horizon_hours=args.horizon,
        facid=fac, batchid=bid,
    )
    print(f"facid={fac}")
    print(f"batchid LIKE %{bid}%")
    print(f"input JSON 저장 → {path}")


def build_parser():
    parser = argparse.ArgumentParser(description="장비 전환 스케줄링 RL")
    sub = parser.add_subparsers(dest="cmd", required=True)

    pt = sub.add_parser("train", help="학습 (기본 data/train/, --use-db 시 DB→JSON)")
    pt.add_argument("--dataset")
    pt.add_argument("--benchmark-dataset", dest="benchmark_dataset")
    pt.add_argument("--use-db", action="store_true", help="DB 구간 export 후 data/train 학습")
    pt.add_argument("--from-timekey", dest="from_timekey")
    pt.add_argument("--to-timekey", dest="to_timekey")
    pt.add_argument("--lookback-days", type=int, default=config.DEFAULT_TRAIN_LOOKBACK_DAYS)
    pt.add_argument("--horizon", type=int, default=12)
    pt.add_argument("--facid", help="facid 필수 (.env DEFAULT_FACID 가능)")
    pt.add_argument("--batchid", help="batchid 필수 (.env DEFAULT_BATCHID 가능, LIKE %값%)")
    pt.add_argument("--steps", type=int, default=config.DEFAULT_PPO_STEPS)
    pt.set_defaults(func=cmd_train)

    pi = sub.add_parser("infer", help="DB→JSON→추론→JSON→DB (로컬은 --dataset)")
    pi.add_argument("--dataset")
    pi.add_argument("--benchmark-dataset", dest="benchmark_dataset")
    pi.add_argument("--timekey", help="미지정 시 MAX(RULE_TIMEKEY)")
    pi.add_argument("--facid", help="facid 필수 (.env DEFAULT_FACID 가능)")
    pi.add_argument("--batchid", help="batchid 필수 (.env DEFAULT_BATCHID 가능, LIKE %값%)")
    pi.add_argument("--horizon", type=int, default=12)
    pi.add_argument("--skip-export", action="store_true", help="기존 input JSON 사용")
    pi.add_argument("--no-db", action="store_true", help="결과 DB write 생략")
    pi.add_argument("--no-report", action="store_true")
    pi.add_argument("--report")
    pi.add_argument("--html", dest="html")
    pi.set_defaults(func=cmd_infer)

    pe = sub.add_parser("eval", help="data/test 전체 평가")
    pe.add_argument("--report")
    pe.add_argument("--no-model", action="store_true")
    pe.set_defaults(func=cmd_eval)

    px = sub.add_parser("export", help="DB → JSON")
    px.add_argument("--timekey", help="추론 input (미지정=MAX)")
    px.add_argument("--facid", help="facid 필수 (.env DEFAULT_FACID 가능)")
    px.add_argument("--batchid", help="batchid 필수 (.env DEFAULT_BATCHID 가능, LIKE %값%)")
    px.add_argument("--train", action="store_true", help="학습 구간 → data/train/{RULE_TIMEKEY}.json")
    px.add_argument("--from-timekey", dest="from_timekey")
    px.add_argument("--to-timekey", dest="to_timekey")
    px.add_argument("--lookback-days", type=int, default=config.DEFAULT_TRAIN_LOOKBACK_DAYS)
    px.add_argument("--output")
    px.add_argument("--horizon", type=int, default=12)
    px.add_argument("--sample", action="store_true")
    px.set_defaults(func=cmd_export)
    return parser


def main():
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
