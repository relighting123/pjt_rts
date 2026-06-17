"""시뮬레이션 결과 → Oracle 출력 테이블 행·추론 JSON 빌더.

출력 Oracle 테이블 (config.py) — 상세: db/sql/reference/00_output_tables.md
  RTS_EQPALLOCATION_INF/HIS — Mode 1 가이드 (공정×모델 목표·현재 장비 대수)
  RTS_ASSIGN_INF/HIS        — Mode 2 장비 배치·생산 (eqp×hour)
  RTS_EQPCONVPLAN_INF/HIS   — Mode 2 batch 전환 계획
"""
from __future__ import annotations
from datetime import datetime, timedelta
from pathlib import Path

import config
from src.simulation.domain.problem import ProblemInstance, Move


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


def finalize_assign_rows(rows: list[dict]) -> list[dict]:
    """연속 동일 작업 구간 병합 후 EQP_ID별 SEQ_NO 재부여."""
    merged = merge_assign_rows(rows)
    seq_by_eqp: dict[str, int] = {}
    out: list[dict] = []
    for row in sorted(merged, key=lambda r: (r["EQP_ID"], r["START_TIME"])):
        eqp = row["EQP_ID"]
        seq_by_eqp[eqp] = seq_by_eqp.get(eqp, 0) + 1
        out.append({**row, "SEQ_NO": seq_by_eqp[eqp]})
    return out


def build_assign_rows(
    problem: ProblemInstance,
    hourly_stats: list[dict],
    sys_id: str | None = None,
    trace: list | None = None,
) -> list[dict]:
    """RTS_ASSIGN_INF/HIS — 시간대 × 장비 배치·생산. SEQ_NO는 EQP_ID(호기)별.

    trace가 있으면 호기 단위 추적(eqp_units)으로 EQP_ID 연속성을 보장하고,
    problem.equipments(실제 호기 명단)가 있으면 실제 호기 ID를 사용한다.
    trace가 없으면 시간대별 가상 번호 부여(레거시)로 동작.
    """
    sys_id = sys_id or config.SYS_ID
    rows: list[dict] = []
    seq_by_eqp: dict[str, int] = {}
    rule_timekey = problem.rule_timekey

    hourly_positions = None
    if trace is not None:
        from src.utils.eqp_units import track_units
        hourly_positions, _ = track_units(problem, trace)

    for k, stat in enumerate(hourly_stats):
        hour = stat["hour"]
        event_tm = event_tm_for_hour(rule_timekey, hour)
        start_time = event_tm
        end_time = event_tm_for_hour(rule_timekey, hour + 1)
        snapshot = stat["assign_snapshot"]

        # (model, ti) -> [eqp_id]: 추적 결과 우선, 없으면 시간대별 가상 번호
        if hourly_positions is not None and k < len(hourly_positions):
            positions = hourly_positions[k]
        else:
            positions = {}
            model_unit_offset: dict[str, int] = {}
            for model in problem.models():
                for ti in range(len(problem.tasks)):
                    active = snapshot.get((model, ti), 0)
                    if active <= 0:
                        continue
                    offset = model_unit_offset.get(model, 0)
                    positions[(model, ti)] = [
                        f"{model}-{offset + u + 1:03d}" for u in range(active)
                    ]
                    model_unit_offset[model] = offset + active

        for (model, ti), unit_ids in sorted(positions.items()):
            task = problem.tasks[ti]
            active = len(unit_ids)
            model_total = _split_hourly_produce(problem, stat, ti).get(model, 0)
            per_unit = model_total // active if active else 0
            remainder = model_total % active if active else 0
            for u, eqp_id in enumerate(sorted(unit_ids)):
                qty = per_unit + (1 if u < remainder else 0)
                if qty == 0:
                    # 재공 없음(WIP=0) 또는 전환중 — 배치 행 생략
                    continue
                seq_by_eqp[eqp_id] = seq_by_eqp.get(eqp_id, 0) + 1
                rows.append({
                    "RULE_TIMEKEY": rule_timekey,
                    "EQP_ID": eqp_id,
                    "EQP_MODEL_CD": model,
                    "SEQ_NO": seq_by_eqp[eqp_id],
                    "START_TIME": start_time,
                    "END_TIME": end_time,
                    "BATCH_ID": task.allocation_batch_id(),
                    "PLAN_PROD_KEY": task.plan_prod_key,
                    "OPER_ID": task.oper_id,
                    "PRODUCE_QTY": qty,
                    "CRT_USER_ID": sys_id,
                })
    return finalize_assign_rows(rows)


def build_eqpconvplan_rows(problem: ProblemInstance, trace: list) -> list[dict]:
    """RTS_EQPCONVPLAN_INF/HIS — batch 전환 계획."""
    from src.db.eqpconvplan import build_eqpconvplan_rows as _build
    return _build(problem, trace)


def build_conv_rows(problem: ProblemInstance, trace: list, sys_id: str | None = None) -> list[dict]:
    """하위호환 alias."""
    return build_eqpconvplan_rows(problem, trace)


def merge_assign_rows(rows: list[dict]) -> list[dict]:
    """ASSIGN_INF rows에서 EQP_ID·EQP_MODEL_CD·PLAN_PROD_KEY·OPER_ID가 같고
    시간이 연속(현재 END_TIME == 다음 START_TIME)인 행만 병합.
    재공 없는 구간(WIP=0·전환중)은 build_assign_rows에서 이미 제외되므로
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
            and current.get("BATCH_ID") == row.get("BATCH_ID")
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
    from src.db.eqpallocation import build_eqpallocation_rows as _build
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


ASSIGN_KEYS = [
    "RULE_TIMEKEY", "EQP_ID", "EQP_MODEL_CD", "SEQ_NO",
    "START_TIME", "END_TIME", "BATCH_ID", "PLAN_PROD_KEY", "OPER_ID",
    "PRODUCE_QTY", "CRT_USER_ID",
]
ASSIGN_HEADERS = [
    "RULE_TIMEKEY", "EQP_ID", "EQP_MODEL_CD", "SEQ",
    "START_TIME", "END_TIME", "BATCH_ID", "PLAN_PROD_KEY", "OPER_ID",
    "PRODUCE_QTY", "CRT_USER_ID",
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
    "TARGET_EQP_CNT", "CUR_EQP_CNT", "MODE_TYP",
    "PLAN_QTY", "CAPA_QTY", "ACHIVE_RATE", "LOG_INF_VAL", "CRT_USER_ID",
]
EQPALLOCATION_HEADERS = [
    "FAC_ID", "RULE_TIMEKEY", "BATCH_ID", "PLAN_PROD_KEY", "OPER_ID", "EQP_MODEL",
    "TARGET_EQP_CNT", "CUR_EQP_CNT", "MODE_TYP",
    "PLAN_QTY", "CAPA_QTY", "ACHIVE_RATE", "LOG_INF_VAL", "CRT_USER_ID",
]
GUIDE_KEYS = EQPALLOCATION_KEYS
GUIDE_HEADERS = EQPALLOCATION_HEADERS

ALLOC_DB_KEYS = [
    "RULE_TIMEKEY", "EQP_ID", "EQP_MODEL_CD", "SEQ_NO",
    "START_TIME", "END_TIME", "BATCH_ID", "PLAN_PROD_KEY", "OPER_ID",
    "PRODUCE_QTY", "CRT_USER_ID",
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
        config.ASSIGN_TABLE: build_assign_rows(problem, hourly_stats, sid, trace=trace),
        config.EQPCONVPLAN_TABLE: build_eqpconvplan_rows(problem, trace),
    }


def build_allocation_rows(
    problem: ProblemInstance,
    hourly_stats: list[dict],
    sys_id: str | None = None,
    trace: list | None = None,
) -> list[dict]:
    sid = sys_id or config.SYS_ID
    return [{k: row[k] for k in ALLOC_DB_KEYS} for row in build_assign_rows(
        problem, hourly_stats, sid, trace=trace)]


def guide_allocation_rows(problem, guide_allocation: dict) -> list[dict]:
    """대시보드용 가이드 배분 행 목록 (미배분 공정은 0)."""
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


def enrich_eval_result(problem: ProblemInstance, trace: list, hourly_stats: list[dict]) -> dict:
    """evaluate_benchmark 반환 dict에 출력 테이블별 행 추가."""
    tables = build_output_tables(problem, hourly_stats, trace)
    return {
        "hourly_stats": hourly_stats,
        "output_tables": tables,
        "assign_rows": tables[config.ASSIGN_TABLE],
        "eqpconvplan_rows": tables[config.EQPCONVPLAN_TABLE],
        "conv_rows": tables[config.EQPCONVPLAN_TABLE],
        "allocation_rows": [{k: row[k] for k in ALLOC_DB_KEYS} for row in tables[config.ASSIGN_TABLE]],
        "avg_utilization": avg_utilization(hourly_stats),
        "trace": trace,
    }
