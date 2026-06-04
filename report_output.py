"""시뮬레이션 결과 → 출력 테이블별 행 빌더·HTML/MD 리포트.

출력 Oracle 테이블 (config.py):
  RTS_PLAN_ACHV_INF/HIS — 시간대별 계획·생산·달성 (task 단위)
  RTS_ASSIGN_INF/HIS    — 장비 배치·생산 (eqp 단위)
  RTS_CONV_INF/HIS      — batch(tool) 전환 이벤트
"""
from __future__ import annotations
from datetime import datetime, timedelta
from html import escape

import config
from simulator import ProblemInstance, Move


def event_tm_for_hour(rule_timekey: str, hours: int) -> str:
    """RULE_TIMEKEY 기준 hours만큼 더한 EVENT_TM (16자)."""
    s = rule_timekey.ljust(16, "0")[:16]
    suffix = s[14:]
    dt = datetime.strptime(s[:14], "%Y%m%d%H%M%S") + timedelta(hours=hours)
    return dt.strftime("%Y%m%d%H%M%S") + suffix


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


def build_plan_achv_rows(
    problem: ProblemInstance,
    hourly_stats: list[dict],
    crt_user_id: str = "RL_AGENT",
) -> list[dict]:
    """RTS_PLAN_ACHV_INF/HIS — 시간대 × task 계획/생산/달성."""
    rows: list[dict] = []
    rule_timekey = problem.rule_timekey
    for stat in hourly_stats:
        hour = stat["hour"]
        event_tm = event_tm_for_hour(rule_timekey, hour)
        cumulative = stat["cumulative_produced"]
        hourly = stat["hourly_produce"]
        for ti, task in enumerate(problem.tasks):
            produced = cumulative.get(ti, 0)
            plan = task.plan_qty
            achieve = round(min(produced / plan, 1.0), 4) if plan > 0 else 1.0
            rows.append({
                "RULE_TIMEKEY": rule_timekey,
                "EVENT_TM": event_tm,
                "BATCH_ID": task.batch_id,
                "PLAN_PROD_KEY": task.plan_prod_key,
                "OPER_ID": task.oper_id,
                "PLAN_QTY": plan,
                "REMAIN_QTY": max(0, plan - produced),
                "PRODUCE_QTY": hourly.get(ti, 0),
                "ACHIEVE_RATE": achieve,
                "EQP_UTIL_RATE": stat["util_rate"],
                "CRT_USER_ID": crt_user_id,
            })
    return rows


def build_assign_rows(
    problem: ProblemInstance,
    hourly_stats: list[dict],
    crt_user_id: str = "RL_AGENT",
) -> list[dict]:
    """RTS_ASSIGN_INF/HIS — 시간대 × 장비 배치·생산."""
    rows: list[dict] = []
    seq = 0
    rule_timekey = problem.rule_timekey
    for stat in hourly_stats:
        hour = stat["hour"]
        event_tm = event_tm_for_hour(rule_timekey, hour)
        start_time = event_tm
        end_time = event_tm_for_hour(rule_timekey, hour + 1)
        snapshot = stat["assign_snapshot"]

        assignments: list[tuple[str, int, int]] = []
        for model in problem.models():
            for ti in range(len(problem.tasks)):
                active = snapshot.get((model, ti), 0)
                if active > 0:
                    assignments.append((model, ti, active))

        for model, ti, active in sorted(assignments):
            task = problem.tasks[ti]
            model_total = _split_hourly_produce(problem, stat, ti).get(model, 0)
            per_unit = model_total // active if active else 0
            remainder = model_total % active if active else 0
            for u in range(active):
                seq += 1
                qty = per_unit + (1 if u < remainder else 0)
                rows.append({
                    "RULE_TIMEKEY": rule_timekey,
                    "EVENT_TM": event_tm,
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


def build_conv_rows(
    problem: ProblemInstance,
    trace: list,
    crt_user_id: str = "RL_AGENT",
) -> list[dict]:
    """RTS_CONV_INF/HIS — batch(tool) 전환 이벤트 (cross-batch move)."""
    rows: list[dict] = []
    seq = 0
    rule_timekey = problem.rule_timekey
    unit_idx: dict[str, int] = {}

    for hour, applied_moves, _snapshot in trace:
        event_tm = event_tm_for_hour(rule_timekey, hour)
        for mv in applied_moves:
            if not isinstance(mv, Move):
                continue
            from_batch = problem.batch_of(mv.from_index)
            to_batch = problem.batch_of(mv.to_index)
            if from_batch == to_batch:
                continue
            from_task = problem.tasks[mv.from_index]
            to_task = problem.tasks[mv.to_index]
            unit_idx[mv.model] = unit_idx.get(mv.model, 0) + 1
            seq += 1
            rows.append({
                "RULE_TIMEKEY": rule_timekey,
                "EVENT_TM": event_tm,
                "EQP_ID": f"{mv.model}-{unit_idx[mv.model]:03d}",
                "EQP_MODEL_CD": mv.model,
                "SEQ_NO": seq,
                "START_TIME": event_tm,
                "END_TIME": event_tm,
                "FROM_BATCH_ID": from_batch,
                "TO_BATCH_ID": to_batch,
                "FROM_PLAN_PROD_KEY": from_task.plan_prod_key,
                "TO_PLAN_PROD_KEY": to_task.plan_prod_key,
                "FROM_OPER_ID": from_task.oper_id,
                "TO_OPER_ID": to_task.oper_id,
                "CRT_USER_ID": crt_user_id,
            })
    return rows


def avg_utilization(hourly_stats: list[dict]) -> float:
    if not hourly_stats:
        return 0.0
    return round(sum(s["util_rate"] for s in hourly_stats) / len(hourly_stats), 4)


def _markdown_table(headers: list[str], rows: list[dict], keys: list[str]) -> str:
    if not rows:
        return "_데이터 없음_"
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(k, "")) for k in keys) + " |")
    return "\n".join(lines)


PLAN_ACHV_KEYS = [
    "RULE_TIMEKEY", "EVENT_TM", "BATCH_ID", "PLAN_PROD_KEY", "OPER_ID",
    "PLAN_QTY", "REMAIN_QTY", "PRODUCE_QTY", "ACHIEVE_RATE", "EQP_UTIL_RATE",
]
PLAN_ACHV_HEADERS = [
    "RULE_TIMEKEY", "EVENT_TM", "BATCH_ID", "PLAN_PROD_KEY", "OPER",
    "PLAN_QTY", "REMAIN_QTY", "PRODUCE_QTY", "ACHIEVE_RATE", "EQP_UTIL_RATE",
]

ASSIGN_KEYS = [
    "RULE_TIMEKEY", "EVENT_TM", "EQP_ID", "EQP_MODEL_CD", "SEQ_NO",
    "START_TIME", "END_TIME", "PLAN_PROD_KEY", "PRODUCE_QTY", "CRT_USER_ID",
]
ASSIGN_HEADERS = [
    "RULE_TIMEKEY", "EVENT_TM", "EQP_ID", "EQP_MODEL_CD", "SEQ",
    "START_TIME", "END_TIME", "PLAN_PROD_KEY", "PRODUCE_QTY", "CRT_USER_ID",
]

CONV_KEYS = [
    "RULE_TIMEKEY", "EVENT_TM", "EQP_ID", "EQP_MODEL_CD", "SEQ_NO",
    "START_TIME", "END_TIME",
    "FROM_BATCH_ID", "TO_BATCH_ID",
    "FROM_PLAN_PROD_KEY", "TO_PLAN_PROD_KEY", "FROM_OPER_ID", "TO_OPER_ID",
    "CRT_USER_ID",
]
CONV_HEADERS = [
    "RULE_TIMEKEY", "EVENT_TM", "EQP_ID", "EQP_MODEL_CD", "SEQ",
    "START_TIME", "END_TIME",
    "FROM_BATCH", "TO_BATCH",
    "FROM_PLAN_PROD_KEY", "TO_PLAN_PROD_KEY", "FROM_OPER", "TO_OPER",
    "CRT_USER_ID",
]

# 하위호환 alias
TASK_DETAIL_KEYS = PLAN_ACHV_KEYS
TASK_DETAIL_HEADERS = PLAN_ACHV_HEADERS
ALLOC_DB_KEYS = [
    "RULE_TIMEKEY", "EQP_ID", "EQP_MODEL_CD", "SEQ_NO",
    "START_TIME", "END_TIME", "PLAN_PROD_KEY", "PRODUCE_QTY", "CRT_USER_ID",
]


def build_output_tables(
    problem: ProblemInstance,
    hourly_stats: list[dict],
    trace: list,
    crt_user_id: str = "RL_AGENT",
) -> dict[str, list[dict]]:
    """출력 테이블별 행 dict."""
    return {
        config.PLAN_ACHV_TABLE: build_plan_achv_rows(problem, hourly_stats, crt_user_id),
        config.ASSIGN_TABLE: build_assign_rows(problem, hourly_stats, crt_user_id),
        config.CONV_TABLE: build_conv_rows(problem, trace, crt_user_id),
    }


# 하위호환
def build_task_hourly_rows(problem: ProblemInstance, hourly_stats: list[dict]) -> list[dict]:
    return build_plan_achv_rows(problem, hourly_stats)


def build_allocation_rows(
    problem: ProblemInstance,
    hourly_stats: list[dict],
    crt_user_id: str = "RL_AGENT",
) -> list[dict]:
    return [{k: row[k] for k in ALLOC_DB_KEYS} for row in build_assign_rows(
        problem, hourly_stats, crt_user_id)]


def render_detail_sections(
    problem: ProblemInstance,
    hourly_stats: list[dict],
    trace: list,
    policy_label: str = "heuristic",
) -> str:
    """MD용 출력 테이블 3종."""
    tables = build_output_tables(problem, hourly_stats, trace)
    util_avg = avg_utilization(hourly_stats)
    lines = [
        f"### {policy_label} — 출력 테이블 (평균 장비 가동률: {util_avg:.3f})",
        "",
        f"#### {config.PLAN_ACHV_TABLE} / {config.PLAN_ACHV_HIS_TABLE}",
        _markdown_table(PLAN_ACHV_HEADERS, tables[config.PLAN_ACHV_TABLE], PLAN_ACHV_KEYS),
        "",
        f"#### {config.ASSIGN_TABLE} / {config.ASSIGN_HIS_TABLE}",
        _markdown_table(ASSIGN_HEADERS, tables[config.ASSIGN_TABLE], ASSIGN_KEYS),
        "",
        f"#### {config.CONV_TABLE} / {config.CONV_HIS_TABLE}",
        _markdown_table(CONV_HEADERS, tables[config.CONV_TABLE], CONV_KEYS),
        "",
    ]
    return "\n".join(lines)


def _html_table(headers: list[str], rows: list[dict], keys: list[str]) -> str:
    if not rows:
        return "<p><em>데이터 없음</em></p>"
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
        "h4{margin-top:1rem;color:#444;font-size:0.95rem}",
        ".summary{background:#f8f8f8;padding:0.75rem;border-radius:4px}",
        ".note{color:#555;font-size:0.9rem}",
        "pre{background:#fafafa;padding:0.75rem;overflow-x:auto}",
        "</style></head><body>",
        "<h1>모델 평가 리포트</h1>",
        f"<p class='summary'>{escape(summary)}</p>",
        "<p class='note'><strong>출력 테이블:</strong> "
        f"{escape(config.PLAN_ACHV_TABLE)}(계획/달성), "
        f"{escape(config.ASSIGN_TABLE)}(장비배치), "
        f"{escape(config.CONV_TABLE)}(batch전환). "
        "입력: "
        f"{escape(config.INPUT_TABLE)}.</p>",
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
        trace = r.get(trace_key, r.get("trace", []))
        if hourly:
            util_avg = avg_utilization(hourly)
            parts.append(
                f"<p>평균 장비 가동률 ({escape(label)}): <strong>{util_avg:.3f}</strong></p>"
            )
            tables = build_output_tables(p, hourly, trace)
            parts.append(f"<h3>{escape(label)} — 출력 테이블</h3>")
            parts.append(f"<h4>{escape(config.PLAN_ACHV_TABLE)} / {escape(config.PLAN_ACHV_HIS_TABLE)}</h4>")
            parts.append(_html_table(PLAN_ACHV_HEADERS, tables[config.PLAN_ACHV_TABLE], PLAN_ACHV_KEYS))
            parts.append(f"<h4>{escape(config.ASSIGN_TABLE)} / {escape(config.ASSIGN_HIS_TABLE)}</h4>")
            parts.append(_html_table(ASSIGN_HEADERS, tables[config.ASSIGN_TABLE], ASSIGN_KEYS))
            parts.append(f"<h4>{escape(config.CONV_TABLE)} / {escape(config.CONV_HIS_TABLE)}</h4>")
            parts.append(_html_table(CONV_HEADERS, tables[config.CONV_TABLE], CONV_KEYS))
        parts.append(f"<pre>{escape(gantt_text(p, trace))}</pre>")

    parts.append("</body></html>")
    return "\n".join(parts)


def enrich_eval_result(problem: ProblemInstance, trace: list, hourly_stats: list[dict]) -> dict:
    """evaluate_benchmark 반환 dict에 출력 테이블별 행 추가."""
    tables = build_output_tables(problem, hourly_stats, trace)
    return {
        "hourly_stats": hourly_stats,
        "output_tables": tables,
        "plan_achv_rows": tables[config.PLAN_ACHV_TABLE],
        "assign_rows": tables[config.ASSIGN_TABLE],
        "conv_rows": tables[config.CONV_TABLE],
        "task_hourly_rows": tables[config.PLAN_ACHV_TABLE],
        "allocation_rows": [{k: row[k] for k in ALLOC_DB_KEYS} for row in tables[config.ASSIGN_TABLE]],
        "avg_utilization": avg_utilization(hourly_stats),
        "trace": trace,
    }
