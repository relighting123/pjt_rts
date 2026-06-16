"""CLI 진입점: train / infer / eval / export.

데이터 경로:
  data/raw/train/        — 학습 JSON
  data/raw/test/         — 벤치마크
  data/raw/inference/    — 추론 입력 JSON
  data/processed/inference/ — 추론 결과 JSON
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
        config.INFERENCE_INPUT_DIR,
        config.TEST_DATA_DIR,
        config.TRAIN_DATA_DIR,
    ):
        cand = base / p.name
        if cand.is_file():
            return cand
    return p


def _load_named_problems(args) -> list[tuple[str, object]]:
    from src.utils.json_io import load_problem

    if getattr(args, "dataset", None):
        path = _resolve_json_path(args.dataset)
        return [(path.stem, load_problem(path))]

    if args.benchmark_dataset:
        path = _resolve_json_path(args.benchmark_dataset)
        return [(path.stem, load_problem(path))]

    if getattr(args, "timekey", None):
        from src.db.pipeline import input_json_path, snapshot_key
        fac = config.require_facid(getattr(args, "facid", None))
        key = snapshot_key(str(args.timekey), fac)
        path = input_json_path(str(args.timekey), fac)
        if not path.is_file():
            raise FileNotFoundError(
                f"{path} 없음. DB export:\n"
                f"  python main.py export --timekey {args.timekey} --facid {fac}"
            )
        return [(key, load_problem(path))]

    return [(p.stem, load_problem(p)) for p in sorted(config.TEST_DATA_DIR.glob("*.json"))]


def _load_problems(args, default_dir: Path | None = None):
    from src.utils.json_io import load_problem
    if getattr(args, "use_db", False):
        from src.db.pipeline import load_train_problems_from_export
        return load_train_problems_from_export()
    if getattr(args, "dataset", None) or args.benchmark_dataset or getattr(args, "timekey", None):
        return [p for _, p in _load_named_problems(args)]
    directory = default_dir or config.TRAIN_DATA_DIR
    return [load_problem(p) for p in sorted(Path(directory).glob("*.json"))]


def cmd_train(args):
    if args.use_db or args.from_timekey or args.to_timekey:
        from src.db.export import export_train_range
        paths = export_train_range(
            args.from_timekey, args.to_timekey, args.lookback_days, args.horizon,
            facid=getattr(args, "facid", None),
            batchid=getattr(args, "batchid", None),
        )
        print(f"DB → JSON {len(paths)}건 → {config.TRAIN_DATA_DIR}")
        args.use_db = True

    from src.train import run_train
    problems = _load_problems(args, default_dir=config.TRAIN_DATA_DIR)
    run_train(problems=problems, ppo_steps=args.steps)
    print(f"학습 완료 → {config.MODEL_PATH}")
    print("결과 확인: http://localhost:8000 (UI)")


def cmd_eval(args):
    from src.evaluate import evaluate_benchmark
    from src.utils.json_io import load_problem
    from agents.model_store import load_dispatch_model
    model = None
    if Path(config.MODEL_PATH).exists() and not args.no_model:
        model = load_dispatch_model()
    results = {}
    for path in sorted(config.TEST_DATA_DIR.glob("*.json")):
        p = load_problem(path)
        res = evaluate_benchmark(p, model)
        results[path.stem] = res
        parts = [f"H={res['heuristic']:.3f}"]
        if res.get("rl") is not None:
            parts.append(f"RL={res['rl']:.3f}")
        if res.get("optimal") is not None:
            parts.append(f"OPT={res['optimal']:.3f}")
        print(f"  {path.stem}: {' / '.join(parts)}")
    if results:
        avg_h = sum(r["heuristic"] for r in results.values()) / len(results)
        print(f"\n평균 휴리스틱 달성률: {avg_h:.3f}")
    print("결과 확인: http://localhost:8000 (UI)")


def cmd_infer(args):
    if getattr(args, "dataset", None) or args.benchmark_dataset:
        from src.evaluate import evaluate_benchmark
        from src.utils.json_io import load_problem
        from agents.model_store import load_dispatch_model
        named = _load_named_problems(args)
        model = load_dispatch_model() if Path(config.MODEL_PATH).exists() else None
        for name, p in named:
            res = evaluate_benchmark(p, model)
            parts = [f"H={res['heuristic']:.3f}"]
            if res.get("rl") is not None:
                parts.append(f"RL={res['rl']:.3f}")
            if res.get("optimal") is not None:
                parts.append(f"OPT={res['optimal']:.3f}")
            print(f"  {name}: {' / '.join(parts)}")
        print("결과 확인: http://localhost:8000 (UI)")
        return

    from src.inference import run_infer
    from src.utils.ops_log import OPS_LOG_PATH

    out = run_infer(
        args.timekey,
        facid=getattr(args, "facid", None),
        batchid=getattr(args, "batchid", None),
        horizon_hours=args.horizon,
        skip_input_export=args.skip_export,
        write_db=not args.no_db,
    )
    label = out["rule_timekey"] + (f" [{out['facid']}]" if out.get("facid") else "")
    print(f"{label}: 입력 JSON → {out['input_json']}")
    print(f"{label}: 결과 JSON → {out['result_json']}")
    print(f"[동적 운영] 평균 계획달성률 {out['plan_achievement']:.3f}")
    if not args.no_db:
        print("DB 기록 완료 (RTS_EQPALLOCATION / ASSIGN / EQPCONVPLAN)")
    print(f"ops 로그 → {OPS_LOG_PATH}")


def cmd_export(args):
    from src.db.export import export_from_db, export_from_sample_rows, export_train_range
    from src.utils.ops_log import OPS_LOG_PATH, log_ops

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
        from src.db.adapter import resolve_timekey
        args.timekey = resolve_timekey(None, facid=fac)
    log_ops(
        "export.start",
        rule_timekey=args.timekey,
        facid=fac,
        batchid=bid,
        batchid_like=f"%{bid}%",
        horizon_hours=args.horizon,
        output=args.output,
        ops_log=OPS_LOG_PATH,
    )
    path = export_from_db(
        args.timekey, output_path=args.output, horizon_hours=args.horizon,
        facid=fac, batchid=bid,
    )
    log_ops("export.done", rule_timekey=args.timekey, facid=fac, batchid=bid, output=path)
    print(f"input JSON 저장 → {path}")
    print(f"ops 로그 → {OPS_LOG_PATH}")


def build_parser():
    parser = argparse.ArgumentParser(description="장비 전환 스케줄링 RL")
    sub = parser.add_subparsers(dest="cmd", required=True)

    pt = sub.add_parser("train", help="학습 (기본 data/raw/train/)")
    pt.add_argument("--dataset")
    pt.add_argument("--benchmark-dataset", dest="benchmark_dataset")
    pt.add_argument("--use-db", action="store_true")
    pt.add_argument("--from-timekey", dest="from_timekey")
    pt.add_argument("--to-timekey", dest="to_timekey")
    pt.add_argument("--lookback-days", type=int, default=config.DEFAULT_TRAIN_LOOKBACK_DAYS)
    pt.add_argument("--horizon", type=int, default=12)
    pt.add_argument("--facid")
    pt.add_argument("--batchid")
    pt.add_argument("--steps", type=int, default=config.DEFAULT_PPO_STEPS)
    pt.set_defaults(func=cmd_train)

    pi = sub.add_parser("infer", help="추론 (DB 또는 --dataset)")
    pi.add_argument("--dataset")
    pi.add_argument("--benchmark-dataset", dest="benchmark_dataset")
    pi.add_argument("--timekey")
    pi.add_argument("--facid")
    pi.add_argument("--batchid")
    pi.add_argument("--horizon", type=int, default=12)
    pi.add_argument("--skip-export", action="store_true")
    pi.add_argument("--no-db", action="store_true")
    pi.set_defaults(func=cmd_infer)

    pe = sub.add_parser("eval", help="data/raw/test 전체 평가")
    pe.add_argument("--no-model", action="store_true")
    pe.set_defaults(func=cmd_eval)

    px = sub.add_parser("export", help="DB → JSON")
    px.add_argument("--timekey")
    px.add_argument("--facid")
    px.add_argument("--batchid")
    px.add_argument("--train", action="store_true")
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
