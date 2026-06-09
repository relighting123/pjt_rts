"""시뮬레이션 결과 → 출력 테이블별 행 빌더·HTML/MD 리포트.

출력 Oracle 테이블 (config.py):
  RTS_PLAN_ACHV_INF/HIS — 시간대별 계획·생산·달성 (task 단위)
  RTS_ASSIGN_INF/HIS    — 장비 배치·생산 (eqp 단위)
  RTS_EQPCONVPLAN_INF/HIS — 장비 전환 계획 (batch/tool 전환)
"""
from __future__ import annotations
from datetime import datetime, timedelta
from html import escape
from pathlib import Path

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
    sys_id: str | None = None,
) -> list[dict]:
    """RTS_PLAN_ACHV_INF/HIS — 시간대 × task 계획/생산/달성."""
    sys_id = sys_id or config.SYS_ID
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
                "CRT_USER_ID": sys_id,
            })
    return rows


def build_assign_rows(
    problem: ProblemInstance,
    hourly_stats: list[dict],
    sys_id: str | None = None,
) -> list[dict]:
    """RTS_ASSIGN_INF/HIS — 시간대 × 장비 배치·생산. SEQ_NO는 EQP_ID(호기)별."""
    sys_id = sys_id or config.SYS_ID
    rows: list[dict] = []
    seq_by_eqp: dict[str, int] = {}
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

        # 같은 hour 내에서 모델별 누적 unit 번호 (task마다 재시작하면 중복 EQP_ID 발생)
        model_unit_offset: dict[str, int] = {}
        for model, ti, active in sorted(assignments):
            task = problem.tasks[ti]
            model_total = _split_hourly_produce(problem, stat, ti).get(model, 0)
            per_unit = model_total // active if active else 0
            remainder = model_total % active if active else 0
            offset = model_unit_offset.get(model, 0)
            for u in range(active):
                qty = per_unit + (1 if u < remainder else 0)
                if qty == 0:
                    # 재공 없음(WIP=0) 또는 idle 전환 중 — 배치 행 생략
                    continue
                eqp_id = f"{model}-{offset + u + 1:03d}"
                seq_by_eqp[eqp_id] = seq_by_eqp.get(eqp_id, 0) + 1
                rows.append({
                    "RULE_TIMEKEY": rule_timekey,
                    "EQP_ID": eqp_id,
                    "EQP_MODEL_CD": model,
                    "SEQ_NO": seq_by_eqp[eqp_id],
                    "START_TIME": start_time,
                    "END_TIME": end_time,
                    "PLAN_PROD_KEY": task.plan_prod_key,
                    "OPER_ID": task.oper_id,
                    "PRODUCE_QTY": qty,
                    "CRT_USER_ID": sys_id,
                })
            model_unit_offset[model] = offset + active
    return rows


def build_eqpconvplan_rows(problem: ProblemInstance, trace: list) -> list[dict]:
    """RTS_EQPCONVPLAN_INF/HIS — batch 전환 계획."""
    from db.eqpconvplan import build_eqpconvplan_rows as _build
    return _build(problem, trace)


def build_conv_rows(problem: ProblemInstance, trace: list, sys_id: str | None = None) -> list[dict]:
    """하위호환 alias."""
    return build_eqpconvplan_rows(problem, trace)


def merge_assign_rows(rows: list[dict]) -> list[dict]:
    """ASSIGN_INF rows에서 EQP_ID·EQP_MODEL_CD·PLAN_PROD_KEY·OPER_ID가 같고
    시간이 연속(현재 END_TIME == 다음 START_TIME)인 행만 병합.
    재공 없는 구간(WIP=0·idle)은 build_assign_rows에서 이미 제외되므로
    비연속 구간은 병합하지 않아 갭이 유지된다.
    """
    if not rows:
        return rows
    sorted_rows = sorted(rows, key=lambda r: (r["EQP_ID"], r["START_TIME"]))
    merged: list[dict] = []
    current: dict | None = None
    for row in sorted_rows:
        if current is None:
            current = dict(row)
        elif (
            current["EQP_ID"] == row["EQP_ID"]
            and current["EQP_MODEL_CD"] == row["EQP_MODEL_CD"]
            and current["PLAN_PROD_KEY"] == row["PLAN_PROD_KEY"]
            and current.get("OPER_ID") == row.get("OPER_ID")
            and current["RULE_TIMEKEY"] == row["RULE_TIMEKEY"]
            and current["END_TIME"] == row["START_TIME"]   # 시간 연속인 경우만 병합
        ):
            current["END_TIME"] = row["END_TIME"]
            current["PRODUCE_QTY"] = current["PRODUCE_QTY"] + row["PRODUCE_QTY"]
        else:
            merged.append(current)
            current = dict(row)
    if current is not None:
        merged.append(current)
    return merged


def avg_utilization(hourly_stats: list[dict]) -> float:
    if not hourly_stats:
        return 0.0
    return round(sum(s["util_rate"] for s in hourly_stats) / len(hourly_stats), 4)


def build_eqpallocation_rows(
    problem: ProblemInstance,
    guide_allocation: dict,
    guide_source: str = "ANALYTIC",
    sys_id: str | None = None,
) -> list[dict]:
    """RTS_EQPALLOCATION_INF/HIS — 공정×모델 목표·현재 장비 대수 (0 포함)."""
    from db.eqpallocation import build_eqpallocation_rows as _build
    return _build(problem, guide_allocation, guide_source, sys_id)


def build_guide_rows(
    problem: ProblemInstance,
    guide_allocation: dict,
    guide_source: str = "ANALYTIC",
    sys_id: str | None = None,
) -> list[dict]:
    """하위호환 alias."""
    return build_eqpallocation_rows(problem, guide_allocation, guide_source, sys_id)


def detect_guide_source() -> str:
    """가이드 산출 방식: ANALYTIC | ALLOC_RL."""
    alloc_path = config.SAVED_MODELS_DIR / "ppo_alloc.zip"
    if config.USE_ALLOC_MODEL and alloc_path.exists():
        return "ALLOC_RL"
    return "ANALYTIC"


def build_inference_result_document(
    problem: ProblemInstance,
    eval_result: dict,
    policy: str = "RL",
    sys_id: str | None = None,
) -> dict:
    """추론 결과 JSON (가이드 + 동적 운영). schema_version=1."""
    sys_id = sys_id or config.SYS_ID
    use_rl = policy == "RL" and eval_result.get("rl") is not None
    plan_achv_key = "rl_plan_achv_rows" if use_rl else "plan_achv_rows"
    assign_key = "rl_assign_rows" if use_rl else "assign_rows"
    conv_key = "rl_eqpconvplan_rows" if use_rl else "eqpconvplan_rows"
    achievement = eval_result.get("rl" if use_rl else "heuristic", 0.0)
    util = eval_result.get("rl_avg_utilization" if use_rl else "avg_utilization", 0.0)
    guide_src = detect_guide_source()
    alloc_rows = build_eqpallocation_rows(
        problem, eval_result.get("guide_allocation", {}), guide_src, sys_id,
    )
    doc = {
        "schema_version": 1,
        "rule_timekey": problem.rule_timekey,
        "policy": "RL" if use_rl else "HEURISTIC",
        "plan_achievement": float(achievement),
        "eqp_util_rate": float(util or 0.0),
        "guide": {
            "source": guide_src,
            "eqpallocation_rows": alloc_rows,
            "rows": alloc_rows,
        },
        "dynamic": {
            "plan_achv_rows": eval_result.get(plan_achv_key, []),
            "assign_rows": eval_result.get(assign_key, []),
            "eqpconvplan_rows": eval_result.get(
                conv_key,
                eval_result.get("rl_conv_rows" if use_rl else "conv_rows", []),
            ),
        },
    }
    if problem.facid:
        doc["facid"] = problem.facid
    return doc


def save_inference_result_document(doc: dict, path: str | Path) -> Path:
    import json
    import config

    path = config.replace_file(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def load_inference_result_document(path: str | Path) -> dict:
    import json
    return json.loads(Path(path).read_text(encoding="utf-8"))


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
    "RULE_TIMEKEY", "EQP_ID", "EQP_MODEL_CD", "SEQ_NO",
    "START_TIME", "END_TIME", "PLAN_PROD_KEY", "OPER_ID", "PRODUCE_QTY", "CRT_USER_ID",
]
ASSIGN_HEADERS = [
    "RULE_TIMEKEY", "EQP_ID", "EQP_MODEL_CD", "SEQ",
    "START_TIME", "END_TIME", "PLAN_PROD_KEY", "OPER_ID", "PRODUCE_QTY", "CRT_USER_ID",
]

EQPCONVPLAN_KEYS = [
    "FAC_ID", "RULE_TIMEKEY", "JOB_ID", "TESTER_EQP_MODEL_CD",
    "CONV_START_TM", "CONV_END_TM", "CONV_TIME",
    "LOT_CD", "TEMPER_VAL", "PLAN_PROD_ATTR_VAL",
    "TO_LOT_CD", "TO_TEMPER_VAL", "TO_PLAN_PROD_ATTR_VAL",
    "PRCS_STAT_CD", "REASON_CD",
]
EQPCONVPLAN_HEADERS = [
    "FAC_ID", "RULE_TIMEKEY", "JOB_ID", "TESTER_EQP_MODEL",
    "CONV_START", "CONV_END", "CONV_TIME",
    "LOT_CD", "TEMPER", "FROM_PLAN",
    "TO_LOT_CD", "TO_TEMPER", "TO_PLAN",
    "STATUS", "REASON",
]
CONV_KEYS = EQPCONVPLAN_KEYS
CONV_HEADERS = EQPCONVPLAN_HEADERS

EQPALLOCATION_KEYS = [
    "FAC_ID", "RULE_TIMEKEY", "BATCH_ID", "PLAN_PROD_KEY", "OPER_ID", "EQP_MODEL_CD",
    "TARGET_EQP_CNT", "CUR_EQP_CNT", "MODE_TYP", "CRT_USER_ID",
]
EQPALLOCATION_HEADERS = [
    "FAC_ID", "RULE_TIMEKEY", "BATCH_ID", "PLAN_PROD_KEY", "OPER_ID", "EQP_MODEL",
    "TARGET_EQP_CNT", "CUR_EQP_CNT", "MODE_TYP", "CRT_USER_ID",
]
GUIDE_KEYS = EQPALLOCATION_KEYS
GUIDE_HEADERS = EQPALLOCATION_HEADERS

# 하위호환 alias
TASK_DETAIL_KEYS = PLAN_ACHV_KEYS
TASK_DETAIL_HEADERS = PLAN_ACHV_HEADERS
ALLOC_DB_KEYS = [
    "RULE_TIMEKEY", "EQP_ID", "EQP_MODEL_CD", "SEQ_NO",
    "START_TIME", "END_TIME", "PLAN_PROD_KEY", "OPER_ID", "PRODUCE_QTY", "CRT_USER_ID",
]


def build_output_tables(
    problem: ProblemInstance,
    hourly_stats: list[dict],
    trace: list,
    sys_id: str | None = None,
) -> dict[str, list[dict]]:
    """출력 테이블별 행 dict."""
    sid = sys_id or config.SYS_ID
    return {
        config.PLAN_ACHV_TABLE: build_plan_achv_rows(problem, hourly_stats, sid),
        config.ASSIGN_TABLE: build_assign_rows(problem, hourly_stats, sid),
        config.EQPCONVPLAN_TABLE: build_eqpconvplan_rows(problem, trace),
    }


# 하위호환
def build_task_hourly_rows(problem: ProblemInstance, hourly_stats: list[dict]) -> list[dict]:
    return build_plan_achv_rows(problem, hourly_stats)


def build_allocation_rows(
    problem: ProblemInstance,
    hourly_stats: list[dict],
    sys_id: str | None = None,
) -> list[dict]:
    sid = sys_id or config.SYS_ID
    return [{k: row[k] for k in ALLOC_DB_KEYS} for row in build_assign_rows(
        problem, hourly_stats, sid)]


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
        f"#### {config.EQPCONVPLAN_TABLE} / {config.EQPCONVPLAN_HIS_TABLE}",
        _markdown_table(EQPCONVPLAN_HEADERS, tables[config.EQPCONVPLAN_TABLE], EQPCONVPLAN_KEYS),
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


_GANTT_COLORS = [
    "#4472C4", "#ED7D31", "#70AD47", "#FFC000", "#9E3891",
    "#00B0F0", "#FF0000", "#00B050", "#7030A0", "#C55A11",
]


def gantt_html_table(problem: ProblemInstance, trace: list) -> str:
    """장비 모델 × 시간 컬러 테이블 간트차트 (HTML)."""
    task_keys = sorted({f"{t.plan_prod_key}/{t.oper_id}" for t in problem.tasks})
    color_map = {k: _GANTT_COLORS[i % len(_GANTT_COLORS)] for i, k in enumerate(task_keys)}

    hours = [h for h, _, _ in trace]
    th_hours = "".join(
        f"<th style='text-align:center;min-width:60px;white-space:nowrap'>H{h}</th>"
        for h in hours
    )
    header = f"<tr><th>모델</th>{th_hours}</tr>"

    body_rows = []
    for model in problem.models():
        cells = [f"<td><strong>{escape(model)}</strong></td>"]
        for _h, _applied, snapshot in trace:
            tally: dict[str, int] = {}
            for ti in range(len(problem.tasks)):
                cnt = snapshot.get((model, ti), 0)
                if cnt > 0:
                    t = problem.tasks[ti]
                    key = f"{t.plan_prod_key}/{t.oper_id}"
                    tally[key] = tally.get(key, 0) + cnt
            if tally:
                main = max(tally, key=lambda k: tally[k])
                bg = color_map.get(main, "#ccc")
                label = "<br>".join(f"{escape(k)}({v})" for k, v in sorted(tally.items()))
                cells.append(
                    f"<td style='background:{bg};color:#fff;text-align:center;"
                    f"padding:4px 6px'>{label}</td>"
                )
            else:
                cells.append("<td style='color:#aaa;text-align:center'>—</td>")
        body_rows.append(f"<tr>{''.join(cells)}</tr>")

    tbl_style = "border-collapse:collapse;font-size:0.85rem;margin:0.5rem 0"
    return (
        f"<table style='{tbl_style}'>"
        f"<thead>{header}</thead>"
        f"<tbody>{''.join(body_rows)}</tbody>"
        f"</table>"
    )


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
        f"{escape(config.EQPCONVPLAN_TABLE)}(전환계획). "
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
            parts.append(f"<h3>{escape(label)} — 간트차트</h3>")
            parts.append(gantt_html_table(p, trace))
            parts.append(f"<h3>{escape(label)} — 출력 테이블</h3>")
            parts.append(f"<h4>{escape(config.PLAN_ACHV_TABLE)} / {escape(config.PLAN_ACHV_HIS_TABLE)}</h4>")
            parts.append(_html_table(PLAN_ACHV_HEADERS, tables[config.PLAN_ACHV_TABLE], PLAN_ACHV_KEYS))
            assign_merged = merge_assign_rows(tables[config.ASSIGN_TABLE])
            orig_n = len(tables[config.ASSIGN_TABLE])
            merged_n = len(assign_merged)
            parts.append(
                f"<h4>{escape(config.ASSIGN_TABLE)} / {escape(config.ASSIGN_HIS_TABLE)} "
                f"<small>(병합 후 {merged_n}행 / 원래 {orig_n}행)</small></h4>"
            )
            parts.append(_html_table(ASSIGN_HEADERS, assign_merged, ASSIGN_KEYS))
            parts.append(
                f"<h4>{escape(config.EQPCONVPLAN_TABLE)} / "
                f"{escape(config.EQPCONVPLAN_HIS_TABLE)}</h4>"
            )
            parts.append(_html_table(
                EQPCONVPLAN_HEADERS, tables[config.EQPCONVPLAN_TABLE], EQPCONVPLAN_KEYS,
            ))
        parts.append(f"<pre>{escape(gantt_text(p, trace))}</pre>")

    parts.append("</body></html>")
    return "\n".join(parts)


def guide_allocation_rows(problem, guide_allocation: dict) -> list[dict]:
    """Streamlit/HTML용 가이드 배분 행 목록 (미배분 공정은 0)."""
    complete = problem.complete_guide_allocation(guide_allocation)
    rows = []
    for (model, ti), cnt in sorted(complete.items(), key=lambda x: (x[0][1], x[0][0])):
        t = problem.tasks[ti]
        rows.append({
            "task": f"{t.plan_prod_key}/{t.oper_id}",
            "model": model,
            "target_count": int(cnt),
        })
    return rows


def render_guide_table(problem, guide_allocation: dict) -> str:
    """가이드 수량(Mode 1)을 공정×모델 대수 표(markdown)로."""
    rows = guide_allocation_rows(problem, guide_allocation)
    if not rows:
        return ""
    lines = ["**가이드 수량 (재공 무한 기준 목표 배치)**", "",
             "| 공정(PLAN_PROD_KEY/OPER) | 모델 | 목표 대수 |", "|---|---|---|"]
    for row in guide_allocation_rows(problem, guide_allocation):
        lines.append(f"| {row['task']} | {row['model']} | {row['target_count']} |")
    return "\n".join(lines)


def enrich_eval_result(problem: ProblemInstance, trace: list, hourly_stats: list[dict]) -> dict:
    """evaluate_benchmark 반환 dict에 출력 테이블별 행 추가."""
    tables = build_output_tables(problem, hourly_stats, trace)
    return {
        "hourly_stats": hourly_stats,
        "output_tables": tables,
        "plan_achv_rows": tables[config.PLAN_ACHV_TABLE],
        "assign_rows": tables[config.ASSIGN_TABLE],
        "eqpconvplan_rows": tables[config.EQPCONVPLAN_TABLE],
        "conv_rows": tables[config.EQPCONVPLAN_TABLE],
        "task_hourly_rows": tables[config.PLAN_ACHV_TABLE],
        "allocation_rows": [{k: row[k] for k in ALLOC_DB_KEYS} for row in tables[config.ASSIGN_TABLE]],
        "avg_utilization": avg_utilization(hourly_stats),
        "trace": trace,
    }
