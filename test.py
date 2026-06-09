"""학습된 정책 평가 + RL/휴리스틱/최적 비교 리포트(md/html) 생성."""
from __future__ import annotations
from pathlib import Path
import numpy as np

from simulator import ProblemInstance, Simulator, heuristic_actions, run_policy, Move
from report_output import (
    render_detail_sections,
    render_html_report,
    enrich_eval_result,
    gantt_text,
    avg_utilization,
    render_guide_table,
)
import config


_ALLOC_MODEL_CACHE: dict = {}


def _load_alloc_model(path):
    """ppo_alloc.zip을 (경로, mtime) 기준 1회만 로드해 캐시. 실패 시 None+경고."""
    key = (str(path), path.stat().st_mtime)
    if key in _ALLOC_MODEL_CACHE:
        return _ALLOC_MODEL_CACHE[key]
    model = None
    try:
        import stable_baselines3 as sb3
        model = sb3.PPO.load(path)
    except Exception as e:  # 손상/비호환 zip, sb3 미설치 등 → 해석식 폴백
        import warnings
        warnings.warn(f"ppo_alloc.zip load 실패 ({e!r}); 해석식 가이드로 폴백.")
    _ALLOC_MODEL_CACHE[key] = model
    return model


def _guide_allocation(problem: ProblemInstance) -> dict:
    """가이드 수량(Mode 1). USE_ALLOC_MODEL이면 RL, 아니면 해석식."""
    if config.USE_ALLOC_MODEL:
        path = config.SAVED_MODELS_DIR / "ppo_alloc.zip"
        if path.exists():
            model = _load_alloc_model(path)
            if model is not None:
                try:
                    from alloc_env import AllocationEnv
                    env = AllocationEnv(problem, max_tasks=config.MAX_TASKS,
                                        max_models=config.MAX_MODELS)
                    obs, _ = env.reset()
                    action, _ = model.predict(obs, deterministic=True)
                    env.step(action)
                    return problem.complete_guide_allocation(env.get_allocation())
                except Exception as e:
                    import warnings
                    warnings.warn(f"AllocationEnv 추론 실패 ({e!r}); 해석식 가이드로 폴백.")
    return problem.complete_guide_allocation(problem.plan_target_allocation_int())


def _model_matches(model, problem: ProblemInstance) -> bool:
    """학습된 모델의 관측/액션 공간이 이 문제의 env와 같은 shape인지."""
    from env import DispatchEnv
    env = DispatchEnv(problem, max_tasks=config.MAX_TASKS,
                      max_models=config.MAX_MODELS, dwell_obs=config.DWELL_OBS)
    try:
        obs_ok = tuple(model.observation_space.shape) == tuple(env.observation_space.shape)
        act_ok = int(model.action_space.n) == int(env.action_space.n)
        return obs_ok and act_ok
    except Exception:
        return False


def _rl_policy_factory(model, problem: ProblemInstance):
    """model을 사용해 매 시간 이동 목록을 반환하는 policy_fn."""
    from env import DispatchEnv
    env = DispatchEnv(problem, max_tasks=config.MAX_TASKS,
                      max_models=config.MAX_MODELS, dwell_obs=config.DWELL_OBS)

    def policy_fn(sim: Simulator, s):
        env._state = s
        env._substeps = 0
        moves = []
        for _ in range(env.max_substeps):
            obs = env._obs()
            mask = env.action_masks()
            action, _ = model.predict(obs, action_masks=mask, deterministic=True)
            action = int(action)
            if action == 0:
                break
            mv = env.move_list[action - 1]
            if mv in set(sim.valid_moves(s)):
                sim.apply_move(s, mv)
                moves.append(mv)
            else:
                break
        return moves
    return policy_fn


def evaluate_benchmark(problem: ProblemInstance, model=None) -> dict:
    sim = Simulator(problem)
    h_final, h_trace, h_hourly = run_policy(sim, heuristic_actions)
    h_metrics = sim.metrics(h_final)
    h_extra = enrich_eval_result(problem, h_trace, h_hourly)
    out = {
        "heuristic": h_metrics["plan_achievement"],
        "optimal": problem.ground_truth.get("plan_achievement"),
        "heuristic_per_task": h_metrics["per_task"],
        "trace": h_trace,
        "hourly_stats": h_hourly,
        **{k: h_extra[k] for k in (
            "avg_utilization", "output_tables", "assign_rows",
            "eqpconvplan_rows", "conv_rows", "allocation_rows",
        )},
    }
    out["guide_allocation"] = _guide_allocation(problem)
    if model is not None and _model_matches(model, problem):
        sim2 = Simulator(problem)
        rl_final, rl_trace, rl_hourly = run_policy(sim2, _rl_policy_factory(model, problem))
        rl_metrics = sim2.metrics(rl_final)
        out["rl"] = rl_metrics["plan_achievement"]
        out["rl_per_task"] = rl_metrics["per_task"]
        out["rl_trace"] = rl_trace
        out["rl_hourly_stats"] = rl_hourly
        out["rl_avg_utilization"] = avg_utilization(rl_hourly)
        rl_extra = enrich_eval_result(problem, rl_trace, rl_hourly)
        out["rl_output_tables"] = rl_extra["output_tables"]
        out["rl_assign_rows"] = rl_extra["assign_rows"]
        out["rl_eqpconvplan_rows"] = rl_extra.get("eqpconvplan_rows", rl_extra.get("conv_rows", []))
        out["rl_conv_rows"] = out["rl_eqpconvplan_rows"]
        out["rl_allocation_rows"] = rl_extra["allocation_rows"]
    return out


def _gantt(problem: ProblemInstance, trace) -> str:
    return "```\n" + gantt_text(problem, trace) + "\n```"


def render_markdown(results: dict[str, tuple[ProblemInstance, dict]]) -> str:
    h_avg = np.mean([r["heuristic"] for _, r in results.values()])
    opt_vals = [r["optimal"] for _, r in results.values() if r["optimal"] is not None]
    opt_avg = np.mean(opt_vals) if opt_vals else 0.0
    has_rl = any("rl" in r for _, r in results.values())
    lines = ["# 모델 평가 리포트 (기록용)", ""]
    rl_avg_str = ""
    if has_rl:
        rl_avg_str = f" / RL: {np.mean([r.get('rl', 0) for _, r in results.values()]):.3f}"
    lines.append(f"- 평균 계획달성률 — 최적: {opt_avg:.3f} / 휴리스틱: {h_avg:.3f}{rl_avg_str}")
    lines.append("")
    lines.append(
        "- **액션:** 0=commit(이동 없이 1시간 경과), 1..N=장비 이동. "
        "이동 없이 commit만 선택 가능."
    )
    lines.append("")
    header = "| 벤치마크 | 최적 | 휴리스틱 | 평균 가동률 |" + (" RL | RL 가동률 |" if has_rl else "")
    sep = "|---|---|---|---|" + ("---|---|" if has_rl else "")
    lines.append(header)
    lines.append(sep)
    for name, (p, r) in results.items():
        opt = r["optimal"] if r["optimal"] is not None else 0.0
        util = r.get("avg_utilization", 0.0)
        line = f"| {name} | {opt:.3f} | {r['heuristic']:.3f} | {util:.3f} |"
        if has_rl:
            line += f" {r.get('rl', 0):.3f} | {r.get('rl_avg_utilization', 0):.3f} |"
        lines.append(line)
    lines.append("")
    for name, (p, r) in results.items():
        lines.append(f"## {name}")
        guide_md = render_guide_table(p, r.get("guide_allocation", {}))
        if guide_md:
            lines.append(guide_md)
            lines.append("")
        lines.append(f"- 비고: {p.ground_truth.get('note', '')}")
        lines.append(_gantt(p, r.get("rl_trace", r["trace"])))
        lines.append("")
        stats_key = "rl_hourly_stats" if "rl_hourly_stats" in r else "hourly_stats"
        trace_key = "rl_trace" if "rl_trace" in r else "trace"
        label = "RL" if stats_key == "rl_hourly_stats" else "휴리스틱"
        if r.get(stats_key):
            lines.append(render_detail_sections(
                p, r[stats_key], r.get(trace_key, r["trace"]), policy_label=label))
        lines.append("")
    return "\n".join(lines)


def write_report_files(
    results: dict[str, tuple[ProblemInstance, dict]],
    report_path: Path,
    html_report_path: Path | None = None,
) -> tuple[Path, Path]:
    """results dict → MD/HTML 파일 저장. (md_path, html_path) 반환."""
    report_path = Path(report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_markdown(results), encoding="utf-8")
    if html_report_path is None:
        html_report_path = report_path.with_suffix(".html")
    html_report_path = Path(html_report_path)
    html_report_path.parent.mkdir(parents=True, exist_ok=True)
    html_report_path.write_text(render_html_report(results), encoding="utf-8")
    return report_path, html_report_path


def default_infer_report_paths(problems, args) -> tuple[Path, Path]:
    """infer 결과 MD/HTML 기본 경로."""
    out_dir = config.ARTIFACTS_DIR / "inference"
    if getattr(args, "dataset", None):
        stem = _resolve_infer_stem(args.dataset)
        return out_dir / f"{stem}.md", out_dir / f"{stem}.html"
    if getattr(args, "benchmark_dataset", None):
        stem = _resolve_infer_stem(args.benchmark_dataset)
        return out_dir / f"{stem}.md", out_dir / f"{stem}.html"
    if getattr(args, "timekey", None):
        key = str(args.timekey)
        return out_dir / f"{key}.md", out_dir / f"{key}.html"
    if len(problems) == 1:
        key = problems[0].rule_timekey
        return out_dir / f"{key}.md", out_dir / f"{key}.html"
    return config.REPORT_PATH, config.HTML_REPORT_PATH


def _resolve_infer_stem(path_str: str) -> str:
    return Path(path_str).with_suffix("").name


def run_eval(benchmarks_dir: Path = config.TEST_DATA_DIR, model=None,
             report_path: Path = config.REPORT_PATH,
             html_report_path: Path | None = None) -> str:
    from simulator import load_problem
    results = {}
    for path in sorted(Path(benchmarks_dir).glob("*.json")):
        p = load_problem(path)
        results[path.stem] = (p, evaluate_benchmark(p, model))
    md_path, html_path = write_report_files(results, report_path, html_report_path)
    return Path(md_path).read_text(encoding="utf-8")
