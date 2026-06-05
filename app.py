"""Streamlit 대시보드: RTS 장비 스케줄링 시뮬레이션 결과 조회."""
from __future__ import annotations
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st

st.set_page_config(
    page_title="RTS 스케줄링 대시보드",
    page_icon="🏭",
    layout="wide",
)

try:
    import plotly.express as px
    import pandas as pd
    _HAS_PLOTLY = True
except ImportError:
    _HAS_PLOTLY = False

from simulator import load_problem
from test import evaluate_benchmark
from report_output import (
    avg_utilization,
    gantt_text,
    merge_assign_rows,
    PLAN_ACHV_HEADERS, PLAN_ACHV_KEYS,
    ASSIGN_HEADERS, ASSIGN_KEYS,
    CONV_HEADERS, CONV_KEYS,
)
import config


def _parse_tm(s: str) -> datetime:
    return datetime.strptime(s[:14].ljust(14, "0"), "%Y%m%d%H%M%S")


# ────────────────────────────────────────────────────────────────
# Sidebar
# ────────────────────────────────────────────────────────────────
benchmark_files = sorted(config.BENCHMARKS_DIR.glob("benchmark_*.json"))
if not benchmark_files:
    st.error("benchmarks/ 폴더에 JSON 파일이 없습니다.")
    st.stop()

benchmark_names = [f.stem for f in benchmark_files]

with st.sidebar:
    st.header("⚙️ 설정")
    selected = st.selectbox("벤치마크 선택", benchmark_names, index=0)
    bm_path = config.BENCHMARKS_DIR / f"{selected}.json"
    st.caption(f"📄 {bm_path.name}")
    st.divider()
    if not _HAS_PLOTLY:
        st.warning("plotly / pandas 미설치\n\n`pip install plotly pandas`")


# ────────────────────────────────────────────────────────────────
# Load & Evaluate (cached)
# ────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner="시뮬레이션 실행 중…")
def _load_and_eval(path_str: str):
    p = load_problem(path_str)
    res = evaluate_benchmark(p, model=None)
    return p, res


problem, result = _load_and_eval(str(bm_path))

hourly_stats = result["hourly_stats"]
trace = result["trace"]
plan_achv_rows = result["plan_achv_rows"]
assign_rows = result["assign_rows"]
assign_merged = merge_assign_rows(assign_rows)
conv_rows = result["conv_rows"]
util_avg = result.get("avg_utilization", avg_utilization(hourly_stats))
achievement = result["heuristic"]
optimal = result.get("optimal")


# ────────────────────────────────────────────────────────────────
# Header
# ────────────────────────────────────────────────────────────────
st.title("🏭 RTS 장비 스케줄링 대시보드")

c1, c2, c3, c4 = st.columns(4)
c1.metric("계획달성률 (휴리스틱)", f"{achievement:.1%}")
if optimal is not None:
    c2.metric("최적 달성률", f"{optimal:.1%}")
    c3.metric("Gap (휴리스틱 − 최적)", f"{achievement - optimal:+.1%}")
else:
    c2.metric("최적 달성률", "N/A")
    c3.metric("Gap", "N/A")
c4.metric("평균 장비 가동률", f"{util_avg:.1%}")

note = problem.ground_truth.get("note", "")
if note:
    st.info(f"ℹ️ {note}")

st.caption(
    f"RULE_TIMEKEY: **{problem.rule_timekey}** │ "
    f"Horizon: **{problem.horizon_hours}h** │ "
    f"Tasks: **{len(problem.tasks)}** │ "
    f"장비 합계: **{sum(problem.eqp_qty.values())}대**"
)
st.divider()


# ────────────────────────────────────────────────────────────────
# Tabs
# ────────────────────────────────────────────────────────────────
tab_gantt, tab_plan, tab_assign, tab_conv, tab_text = st.tabs([
    "📊 간트차트",
    "📋 PLAN_ACHV_INF",
    "🔧 ASSIGN_INF (병합)",
    "🔄 CONV_INF",
    "📝 텍스트 간트",
])


# ── Tab 1: Plotly Gantt ──────────────────────────────────────────
with tab_gantt:
    st.subheader("장비 배치 간트차트 (ASSIGN_INF 기반)")

    if not _HAS_PLOTLY:
        st.warning("`pip install plotly pandas` 설치 후 재시작하면 차트가 표시됩니다.")
    elif not assign_merged:
        st.info("ASSIGN 데이터가 없습니다.")
    else:
        gantt_data = []
        for r in assign_merged:
            try:
                start = _parse_tm(r["START_TIME"])
                end = _parse_tm(r["END_TIME"])
                if end <= start:
                    end = start + timedelta(hours=1)
            except Exception:
                continue
            task_label = f"{r['PLAN_PROD_KEY']}/{r.get('OPER_ID', '')}"
            gantt_data.append({
                "장비ID": r["EQP_ID"],
                "작업": task_label,
                "시작": start,
                "종료": end,
                "생산량": r["PRODUCE_QTY"],
                "모델": r["EQP_MODEL_CD"],
            })

        df_g = pd.DataFrame(gantt_data)
        if df_g.empty:
            st.info("간트 표시 데이터가 없습니다.")
        else:
            n_eqp = df_g["장비ID"].nunique()
            fig = px.timeline(
                df_g,
                x_start="시작",
                x_end="종료",
                y="장비ID",
                color="작업",
                hover_data=["생산량", "모델"],
                title=f"{selected} — 장비 배치 타임라인",
                labels={"장비ID": "장비", "작업": "PLAN_PROD_KEY"},
                color_discrete_sequence=px.colors.qualitative.Set2,
            )
            fig.update_yaxes(autorange="reversed", title_text="장비")
            fig.update_xaxes(title_text="시간")
            fig.update_layout(
                height=max(380, 80 * n_eqp + 160),
                legend_title_text="작업(PLAN_PROD_KEY)",
                margin=dict(l=10, r=10, t=60, b=10),
            )
            st.plotly_chart(fig, use_container_width=True)

    # Task별 달성률
    st.subheader("Task별 달성률")
    per_task = result.get("heuristic_per_task", {})
    if per_task and _HAS_PLOTLY:
        rows_pt = [
            {
                "Task": k,
                "계획(plan_qty)": v["plan"],
                "생산(produced)": v["produced"],
                "달성률": v["rate"],
            }
            for k, v in per_task.items()
        ]
        df_pt = pd.DataFrame(rows_pt)
        fig_bar = px.bar(
            df_pt,
            x="Task",
            y="달성률",
            color="달성률",
            color_continuous_scale="RdYlGn",
            range_color=[0, 1],
            text=df_pt["달성률"].apply(lambda x: f"{x:.1%}"),
            title="Task별 계획달성률",
            hover_data=["계획(plan_qty)", "생산(produced)"],
        )
        fig_bar.update_yaxes(range=[0, 1.05], tickformat=".0%")
        fig_bar.update_layout(height=320, margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig_bar, use_container_width=True)
    elif per_task:
        for k, v in per_task.items():
            st.write(f"- **{k}**: {v['produced']}/{v['plan']} ({v['rate']:.1%})")


# ── Tab 2: PLAN_ACHV_INF ────────────────────────────────────────
with tab_plan:
    st.subheader(f"RTS_PLAN_ACHV_INF — {len(plan_achv_rows)}행")
    if plan_achv_rows and _HAS_PLOTLY:
        df_pa = pd.DataFrame(plan_achv_rows)[PLAN_ACHV_KEYS].copy()
        df_pa.columns = PLAN_ACHV_HEADERS
        df_pa["ACHIEVE_RATE"] = df_pa["ACHIEVE_RATE"].map(lambda x: f"{float(x):.1%}")
        df_pa["EQP_UTIL_RATE"] = df_pa["EQP_UTIL_RATE"].map(lambda x: f"{float(x):.1%}")
        st.dataframe(df_pa, use_container_width=True, hide_index=True)
    elif plan_achv_rows:
        st.json(plan_achv_rows[:10])
    else:
        st.info("데이터 없음")


# ── Tab 3: ASSIGN_INF (merged) ───────────────────────────────────
with tab_assign:
    orig_n = len(assign_rows)
    mrgd_n = len(assign_merged)
    st.subheader(
        f"RTS_ASSIGN_INF — 병합 후 **{mrgd_n}행** "
        f"(원래 {orig_n}행, {orig_n - mrgd_n}행 절감)"
    )
    st.caption(
        "EQP_ID · EQP_MODEL_CD · PLAN_PROD_KEY · RULE_TIMEKEY가 같은 연속 행을 병합. "
        "START_TIME은 첫 행, END_TIME은 마지막 행, PRODUCE_QTY는 합산."
    )
    if assign_merged and _HAS_PLOTLY:
        df_as = pd.DataFrame(assign_merged)[ASSIGN_KEYS].copy()
        df_as.columns = ASSIGN_HEADERS
        st.dataframe(df_as, use_container_width=True, hide_index=True)
    elif assign_merged:
        st.json(assign_merged[:10])
    else:
        st.info("데이터 없음")


# ── Tab 4: CONV_INF ──────────────────────────────────────────────
with tab_conv:
    st.subheader(f"RTS_CONV_INF — {len(conv_rows)}행")
    if conv_rows and _HAS_PLOTLY:
        df_cv = pd.DataFrame(conv_rows)[CONV_KEYS].copy()
        df_cv.columns = CONV_HEADERS
        st.dataframe(df_cv, use_container_width=True, hide_index=True)
    elif conv_rows:
        st.json(conv_rows)
    else:
        st.info("전환(Conversion) 이벤트 없음")


# ── Tab 5: Text Gantt + Hourly stats ────────────────────────────
with tab_text:
    st.subheader("텍스트 간트 (model × hour → task)")
    st.code(gantt_text(problem, trace), language="text")

    st.subheader("시간별 통계")
    if _HAS_PLOTLY:
        hourly_data = []
        for stat in hourly_stats:
            hourly_data.append({
                "Hour": stat["hour"],
                "시간대 생산량": sum(stat["hourly_produce"].values()),
                "누적 생산량": sum(stat["cumulative_produced"].values()),
                "가동률": stat["util_rate"],
            })
        if hourly_data:
            df_h = pd.DataFrame(hourly_data)
            fig_h = px.bar(
                df_h,
                x="Hour",
                y="시간대 생산량",
                title="시간별 생산량",
                text="시간대 생산량",
                color="가동률",
                color_continuous_scale="Blues",
            )
            fig_h.update_layout(height=280, margin=dict(l=10, r=10, t=50, b=10))
            st.plotly_chart(fig_h, use_container_width=True)
            st.dataframe(
                df_h.assign(**{"가동률": df_h["가동률"].map(lambda x: f"{x:.1%}")}),
                use_container_width=True,
                hide_index=True,
            )
