"""CLI 디스패처: train / infer / eval.

벤치마크 우선. --timekey 지정 시 DB(db.fetch_problem) 경로 사용.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import config


def _load_named_problems(args) -> list[tuple[str, object]]:
    """(리포트용 이름, ProblemInstance) 목록."""
    from simulator import load_problem
    if args.benchmark_dataset:
        path = Path(args.benchmark_dataset).with_suffix(".json")
        return [(path.stem, load_problem(path))]
    if getattr(args, "timekey", None):
        import db
        return [(str(args.timekey), db.fetch_problem(rule_timekey=args.timekey))]
    return [(p.stem, load_problem(p)) for p in sorted(config.BENCHMARKS_DIR.glob("benchmark_*.json"))]


def _load_problems(args):
    return [p for _, p in _load_named_problems(args)]


def cmd_train(args):
    import train
    problems = _load_problems(args)
    train.train_model(problems, ppo_steps=args.steps)
    print(f"학습 완료 → {config.MODEL_PATH}")
    import test as report
    from sb3_contrib import MaskablePPO
    model = MaskablePPO.load(config.MODEL_PATH)
    report.run_eval(model=model)
    print(f"평가 리포트 → {config.REPORT_PATH}")
    print(f"HTML 리포트 → {config.HTML_REPORT_PATH}")


def cmd_eval(args):
    import test as report
    model = None
    if Path(config.MODEL_PATH).exists() and not args.no_model:
        from sb3_contrib import MaskablePPO
        model = MaskablePPO.load(config.MODEL_PATH)
    report_path = Path(args.report) if args.report else config.REPORT_PATH
    report.run_eval(model=model, report_path=report_path)
    print(f"평가 리포트 → {report_path}")
    html_path = (
        config.HTML_REPORT_PATH
        if report_path == config.REPORT_PATH
        else report_path.with_suffix(".html")
    )
    print(f"HTML 리포트 → {html_path}")


def cmd_infer(args):
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
        rate = res.get("rl", res["heuristic"])
        guide = res.get("guide_allocation", {})
        n_guide = len(guide)
        print(f"{p.rule_timekey}: [가이드 수량] 공정×모델 {n_guide}건 / "
              f"[동적 운영] 평균 계획달성률 {rate:.3f}")
        results[name] = (p, res)

    md_default, html_default = report.default_infer_report_paths(problems, args)
    report_path = Path(args.report) if getattr(args, "report", None) else md_default
    html_path = Path(args.html) if getattr(args, "html", None) else html_default
    _, html_written = report.write_report_files(results, report_path, html_path)
    print(f"평가 리포트 → {report_path}")
    print(f"HTML 리포트 → {html_written}")


def build_parser():
    parser = argparse.ArgumentParser(description="장비 전환 스케줄링 RL: train/infer/eval")
    sub = parser.add_subparsers(dest="cmd", required=True)

    pt = sub.add_parser("train", help="모방학습+PPO 학습 후 벤치마크 평가")
    pt.add_argument("--benchmark-dataset", dest="benchmark_dataset")
    pt.add_argument("--timekey")
    pt.add_argument("--steps", type=int, default=config.DEFAULT_PPO_STEPS)
    pt.set_defaults(func=cmd_train)

    pi = sub.add_parser("infer", help="추론 + MD/HTML 리포트")
    pi.add_argument("--benchmark-dataset", dest="benchmark_dataset")
    pi.add_argument("--timekey")
    pi.add_argument("--report", help="MD 리포트 경로 (기본: artifacts/inference/<이름>.md)")
    pi.add_argument("--html", dest="html", help="HTML 리포트 경로 (기본: artifacts/inference/<이름>.html)")
    pi.set_defaults(func=cmd_infer)

    pe = sub.add_parser("eval", help="전체 벤치마크 평가 + md 리포트")
    pe.add_argument("--report")
    pe.add_argument("--no-model", action="store_true", help="휴리스틱만 평가")
    pe.set_defaults(func=cmd_eval)
    return parser


def main():
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
