"""시뮬레이션 결과 → 시간대별 task 상세·장비 배치(RTS_RSLT) 행·HTML/MD 테이블."""
from __future__ import annotations
from datetime import datetime, timedelta
from html import escape

from simulator import ProblemInstance, Simulator


def offset_timekey(rule_timekey: str, hours: int) -> str:
    """RULE_TIMEKEY(16자)에 hours만큼 더한 START/END TIME."""
    s = rule_timekey.ljust(16, "0")[:16]
    suffix = s[14:]
    dt = datetime.strptime(s[:14], "%Y%m%d%H%M%S") + timedelta(hours=hours)
    return dt.strftime("%Y%m%d%H%M%S") + suffix


def build_task_hourly_rows(problem: ProblemInstance, hourly_stats: list[dict]) -> list[dict]:
    """시간대 × task별 필수 컬럼 행."""
    rows: list[dict] = []
    for stat in hourly_stats:
        hour = stat["hour"]
        timekey = offset_timekey(problem.rule_timekey, hour)
        cumulative = stat["cumulative_produced"]
        hourly = stat["hourly_produce"]
        for ti, task in enumerate(problem.tasks):
            produced = cumulative.get(ti, 0)
            plan = task.plan_qty
            achieve = round(min(produced / plan, 1.0), 4) if plan > 0 else 1.0
            rows.append({
                "RULE_TIMEKEY": timekey,
                "BATCH_ID": task.batch_id,
                "PLAN_PROD_KEY": task.plan_prod_key,
                "OPER_ID": task.oper_id,
                "PLAN_QTY": plan,
                "REMAIN_QTY": max(0, plan - produced),
                "PRODUCE_QTY": hourly.get(ti, 0),
                "ACHIEVE_RATE": achieve,
                "HOUR": hour,
                "UTIL_RATE": stat["util_rate"],
            })
    return rows


def _split_hourly_produce(problem: ProblemInstance, stat: dict, ti: int) -> dict[str, int]:
    """task ti의 시간당 생산량을 (model) UPH×active 비율로 분배."""
    p = problem
    total_q = stat["hourly_produce"].get(ti, 0)
    if total_q <= 0:
        return {}
    snapshot = stat["assign_snapshot"]
    weights: dict[str, float] = {}
    for model in p.models():
        active_units = snapshot.get((model, ti), 0)
        uph = p.uph_of(model, ti) or 0.0
        if active_units > 0 and uph > 0:
            weights[model] = active_units * uph
    total_w = sum(weights.values())
    if total_w <= 0:
        return {}
    out: dict[str, int] = {}
    allocated = 0
    models = list(weights)
    for i, model in enumerate(models):
        if i == len(models) - 1:
            out[model] = total_q - allocated
        else:
            share = int(total_q * weights[model] / total_w)
            out[model] = share
            allocated += share
    return out


def build_allocation_rows(
    problem: ProblemInstance,
    hourly_stats: list[dict],
    crt_user_id: str = "RL_AGENT",
) -> list[dict]:
    """RTS_RSLT_MAS/HIS 스키마에 맞는 장비 배치·생산 행."""
    rows: list[dict] = []
    seq = 0
    for stat in hourly_stats:
        hour = stat["hour"]
        start_time = offset_timekey(problem.rule_timekey, hour)
        end_time = offset_timekey(problem.rule_timekey, hour + 1)
        snapshot = stat["assign_snapshot"]
        by_model_task: dict[tuple[str, int], int] = {}
        for ti in range(len(problem.tasks)):
            split = _split_hourly_produce(problem, stat, ti)
            for model, qty in split.items():
                if qty <= 0:
                    continue
                by_model_task[(model, ti)] = by_model_task.get((model, ti), 0) + qty
        for (model, ti), produce_qty in sorted(by_model_task.items()):
            active = snapshot.get((model, ti), 0)
            if active <= 0:
                continue
            task = problem.tasks[ti]
            per_unit = produce_qty // active
            remainder = produce_qty % active
            for u in range(active):
                seq += 1
                qty = per_unit + (1 if u < remainder else 0)
                rows.append({
                    "RULE_TIMEKEY": problem.rule_timekey,
                    "EQP_ID": f"{model}-{u + 1:03d}",
                    "EQP_MODEL_CD": model,
                    "SEQ_NO": seq,
                    "START_TIME": start_time,
                    "END_TIME": end_time,
                    "PLAN_PROD_KEY": task.plan_prod_key,
                    "PRODUCE_QTY": qty,
                    "CRT_USER_ID": crt_user_id,
                })
    return rows


def avg_utilization(hourly_stats: list[dict]) -> float:
    if not hourly_stats:
        return 0.0
    return round(sum(s["util_rate"] for s in hourly_stats) / len(hourly_stats), 4)


def _markdown_table(headers: list[str], rows: list[dict], keys: list[str]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(k, "")) for k in keys) + " |")
    return "\n".join(lines)


TASK_DETAIL_KEYS = [
    "RULE_TIMEKEY", "BATCH_ID", "PLAN_PROD_KEY", "OPER_ID",
    "PLAN_QTY", "REMAIN_QTY", "PRODUCE_QTY", "ACHIEVE_RATE",
]
TASK_DETAIL_HEADERS = [
    "RULE_TIMEKEY", "BATCH_ID", "PLAN_PROD_KEY", "OPER",
    "PLAN_QTY", "REMAIN_QTY", "PRODUCE_QTY", "ACHIEVE_RATE",
]

ALLOC_KEYS = [
    "RULE_TIMEKEY", "EQP_ID", "EQP_MODEL_CD", "SEQ_NO",
    "START_TIME", "END_TIME", "PLAN_PROD_KEY", "PRODUCE_QTY", "CRT_USER_ID",
]
ALLOC_HEADERS = ALLOC_KEYS


def render_detail_sections(
    problem: ProblemInstance,
    hourly_stats: list[dict],
    policy_label: str = "heuristic",
) -> str:
    """MD용 시간대별 상세 + 장비 배치 테이블."""
    task_rows = build_task_hourly_rows(problem, hourly_stats)
    alloc_rows = build_allocation_rows(problem, hourly_stats)
    util_avg = avg_utilization(hourly_stats)
    lines = [
        f"### {policy_label} — 시간대별 계획/생산 (평균 장비 가동률: {util_avg:.3f})",
        "",
        _markdown_table(TASK_DETAIL_HEADERS, task_rows, TASK_DETAIL_KEYS),
        "",
        f"### {policy_label} — 장비 배치 (RTS_RSLT 형식)",
        "",
        _markdown_table(ALLOC_HEADERS, alloc_rows, ALLOC_KEYS),
        "",
    ]
    return "\n".join(lines)


def _html_table(headers: list[str], rows: list[dict], keys: list[str]) -> str:
    head = "".join(f"<th>{escape(h)}</th>" for h in headers)
    body_rows = []
    for row in rows:
        cells = "".join(f"<td>{escape(str(row.get(k, '')))}</td>" for k in keys)
        body_rows.append(f"<tr>{cells}</tr>")
    body = "\n".join(body_rows)
    return f"<table><thead><tr>{head}</tr></thead><tbody>\n{body}\n</tbody></table>"


def gantt_text(problem: ProblemInstance, trace) -> str:
    """장비(model)별 시간대 배치를 텍스트 간트로."""
    lines = ["간트 (model x hour → task)"]
    task_label = {i: f"{t.plan_prod_key}/{t.oper_id}" for i, t in enumerate(problem.tasks)}
    for model in problem.models():
        row = [f"{model:>8}"]
        for hour, applied, snapshot in trace:
            here = [task_label[ti] for (m, ti), c in snapshot.items() if m == model and c > 0]
            row.append((here[0] if here else "-").split("/")[0][:6].ljust(6))
        lines.append(" | ".join(row))
    return "\n".join(lines)


def render_html_report(results: dict[str, tuple[ProblemInstance, dict]]) -> str:
    """벤치마크 평가 결과 HTML."""
    import numpy as np

    h_avg = np.mean([r["heuristic"] for _, r in results.values()])
    opt_vals = [r["optimal"] for _, r in results.values() if r["optimal"] is not None]
    opt_avg = np.mean(opt_vals) if opt_vals else 0.0
    has_rl = any("rl" in r for _, r in results.values())
    rl_avg = np.mean([r.get("rl", 0) for _, r in results.values()]) if has_rl else None

    summary = f"평균 계획달성률 — 최적: {opt_avg:.3f} / 휴리스틱: {h_avg:.3f}"
    if rl_avg is not None:
        summary += f" / RL: {rl_avg:.3f}"

    parts = [
        "<!DOCTYPE html>",
        "<html lang='ko'><head><meta charset='utf-8'>",
        "<title>모델 평가 리포트</title>",
        "<style>",
        "body{font-family:sans-serif;margin:1.5rem;line-height:1.5}",
        "table{border-collapse:collapse;margin:1rem 0;width:100%;font-size:0.85rem}",
        "th,td{border:1px solid #ccc;padding:0.35rem 0.5rem;text-align:left}",
        "th{background:#f0f0f0}",
        "h2{margin-top:2rem;border-bottom:1px solid #ddd;padding-bottom:0.25rem}",
        "h3{margin-top:1.25rem;color:#333}",
        ".summary{background:#f8f8f8;padding:0.75rem;border-radius:4px}",
        ".note{color:#555;font-size:0.9rem}",
        "pre{background:#fafafa;padding:0.75rem;overflow-x:auto}",
        "</style></head><body>",
        "<h1>모델 평가 리포트</h1>",
        f"<p class='summary'>{escape(summary)}</p>",
        "<p class='note'><strong>액션 공간:</strong> "
        "0=commit(이동 없이 1시간 경과). 1..N=장비 이동. "
        "이동하지 않고 commit만 선택하면 해당 시간대 재배치 없이 생산 진행.</p>",
    ]

    bench_header = ["벤치마크", "최적", "휴리스틱"] + (["RL"] if has_rl else [])
    bench_rows = []
    for name, (_, r) in results.items():
        row = {
            "벤치마크": name,
            "최적": f"{r['optimal'] if r['optimal'] is not None else 0.0:.3f}",
            "휴리스틱": f"{r['heuristic']:.3f}",
        }
        if has_rl:
            row["RL"] = f"{r.get('rl', 0):.3f}"
        bench_rows.append(row)
    parts.append("<h2>벤치마크 요약</h2>")
    parts.append(_html_table(bench_header, bench_rows, bench_header))

    for name, (p, r) in results.items():
        parts.append(f"<h2>{escape(name)}</h2>")
        parts.append(f"<p class='note'>{escape(p.ground_truth.get('note', ''))}</p>")
        trace_key = "rl_trace" if "rl_trace" in r else "trace"
        stats_key = "rl_hourly_stats" if "rl_hourly_stats" in r else "hourly_stats"
        label = "RL" if stats_key == "rl_hourly_stats" else "휴리스틱"
        hourly = r.get(stats_key, [])
        if hourly:
            util_avg = avg_utilization(hourly)
            parts.append(
                f"<p>평균 장비 가동률 ({escape(label)}): <strong>{util_avg:.3f}</strong></p>"
            )
            task_rows = build_task_hourly_rows(p, hourly)
            parts.append("<h3>시간대별 계획/생산</h3>")
            parts.append(_html_table(TASK_DETAIL_HEADERS, task_rows, TASK_DETAIL_KEYS))
            alloc_rows = build_allocation_rows(p, hourly)
            parts.append("<h3>장비 배치 (RTS_RSLT)</h3>")
            parts.append(_html_table(ALLOC_HEADERS, alloc_rows, ALLOC_KEYS))
        parts.append(f"<pre>{escape(gantt_text(p, r.get(trace_key, r['trace'])))}</pre>")

    parts.append("</body></html>")
    return "\n".join(parts)


def enrich_eval_result(problem: ProblemInstance, trace: list, hourly_stats: list[dict]) -> dict:
    """evaluate_benchmark 반환 dict에 상세 행·가동률 요약 추가."""
    return {
        "hourly_stats": hourly_stats,
        "task_hourly_rows": build_task_hourly_rows(problem, hourly_stats),
        "allocation_rows": build_allocation_rows(problem, hourly_stats),
        "avg_utilization": avg_utilization(hourly_stats),
        "trace": trace,
    }
