"""학습된 정책 평가 + RL/휴리스틱/최적 비교 리포트(md) 생성."""
from __future__ import annotations
from pathlib import Path
import numpy as np

from simulator import ProblemInstance, Simulator, heuristic_actions, run_policy, Move
import config


def _model_matches(model, problem: ProblemInstance) -> bool:
    """학습된 모델의 관측/액션 공간이 이 문제의 env와 같은 shape인지."""
    from env import DispatchEnv
    env = DispatchEnv(problem)
    try:
        obs_ok = tuple(model.observation_space.shape) == tuple(env.observation_space.shape)
        act_ok = int(model.action_space.n) == int(env.action_space.n)
        return obs_ok and act_ok
    except Exception:
        return False


def _rl_policy_factory(model, problem: ProblemInstance):
    """model을 사용해 매 시간 이동 목록을 반환하는 policy_fn."""
    from env import DispatchEnv
    env = DispatchEnv(problem)

    def policy_fn(sim: Simulator, s):
        # env 상태를 sim 상태와 동기화
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
    h_final, h_trace = run_policy(sim, heuristic_actions)
    h_metrics = sim.metrics(h_final)
    out = {
        "heuristic": h_metrics["plan_achievement"],
        "optimal": problem.ground_truth.get("plan_achievement"),
        "heuristic_per_task": h_metrics["per_task"],
        "trace": h_trace,
    }
    if model is not None and _model_matches(model, problem):
        sim2 = Simulator(problem)
        rl_final, rl_trace = run_policy(sim2, _rl_policy_factory(model, problem))
        rl_metrics = sim2.metrics(rl_final)
        out["rl"] = rl_metrics["plan_achievement"]
        out["rl_per_task"] = rl_metrics["per_task"]
        out["rl_trace"] = rl_trace
    return out


def _gantt(problem: ProblemInstance, trace) -> str:
    """장비(model)별 시간대 배치를 텍스트 간트로."""
    lines = ["```", "간트 (model x hour → task)"]
    task_label = {i: f"{t.plan_prod_key}/{t.oper_id}" for i, t in enumerate(problem.tasks)}
    for model in problem.models():
        row = [f"{model:>8}"]
        for hour, applied, snapshot in trace:
            here = [task_label[ti] for (m, ti), c in snapshot.items() if m == model and c > 0]
            row.append((here[0] if here else "-").split("/")[0][:6].ljust(6))
        lines.append(" | ".join(row))
    lines.append("```")
    return "\n".join(lines)


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
    header = "| 벤치마크 | 최적 | 휴리스틱 |" + (" RL |" if has_rl else "")
    sep = "|---|---|---|" + ("---|" if has_rl else "")
    lines.append(header)
    lines.append(sep)
    for name, (p, r) in results.items():
        opt = r["optimal"] if r["optimal"] is not None else 0.0
        line = f"| {name} | {opt:.3f} | {r['heuristic']:.3f} |"
        if has_rl:
            line += f" {r.get('rl', 0):.3f} |"
        lines.append(line)
    lines.append("")
    for name, (p, r) in results.items():
        lines.append(f"## {name}")
        lines.append(f"- 비고: {p.ground_truth.get('note', '')}")
        lines.append(_gantt(p, r.get("rl_trace", r["trace"])))
        lines.append("")
    return "\n".join(lines)


def run_eval(benchmarks_dir: Path = config.BENCHMARKS_DIR, model=None,
             report_path: Path = config.REPORT_PATH) -> str:
    from simulator import load_problem
    results = {}
    for path in sorted(Path(benchmarks_dir).glob("benchmark_*.json")):
        p = load_problem(path)
        results[path.stem] = (p, evaluate_benchmark(p, model))
    md = render_markdown(results)
    Path(report_path).write_text(md, encoding="utf-8")
    return md
