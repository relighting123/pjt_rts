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
    initial_sidebar_state="collapsed",
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
    merge_assign_rows,
    PLAN_ACHV_HEADERS, PLAN_ACHV_KEYS,
    ASSIGN_HEADERS, ASSIGN_KEYS,
    CONV_HEADERS, CONV_KEYS,
)
import config


def _parse_tm(s: str) -> datetime:
    return datetime.strptime(s[:14].ljust(14, "0"), "%Y%m%d%H%M%S")


@st.cache_data(show_spinner="시뮬레이션 실행 중…")
def _load_and_eval(path_str: str):
    p = load_problem(path_str)
    res = evaluate_benchmark(p, model=None)
    return p, res


def compute_total_move(hourly_stats: list[dict]) -> int:
    if not hourly_stats:
        return 0
    return sum(hourly_stats[-1]["cumulative_produced"].values())


def render_kpi_row(problem, result, total_move: int) -> None:
    util_avg = result.get("avg_utilization", avg_utilization(result["hourly_stats"]))
    achievement = result["heuristic"]
    optimal = result.get("optimal")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("move량 (총 생산)", f"{total_move:,}")
    c2.metric("장비 가동률", f"{util_avg:.1%}")
    if optimal is not None:
        c3.metric("계획 달성률", f"{achievement:.1%}", delta=f"{achievement - optimal:+.1%}")
        c4.metric("최적 달성률 (기준)", f"{optimal:.1%}")
    else:
        c3.metric("계획 달성률", f"{achievement:.1%}")
        c4.metric("최적 달성률 (기준)", "N/A")

    note = problem.ground_truth.get("note", "")
    if note:
        st.info(f"ℹ️ {note}")
    st.caption(
        f"RULE_TIMEKEY: **{problem.rule_timekey}** │ "
        f"Horizon: **{problem.horizon_hours}h** │ "
        f"Tasks: **{len(problem.tasks)}** │ "
        f"장비 합계: **{sum(problem.eqp_qty.values())}대**"
    )


def render_charts(bm_name: str, result: dict, problem) -> None:
    hourly_stats = result["hourly_stats"]
    assign_rows = result["assign_rows"]
    assign_merged = merge_assign_rows(assign_rows)
    per_task = result.get("heuristic_per_task", {})

    if not _HAS_PLOTLY:
        st.warning("`pip install plotly pandas` 설치 후 재시작하면 차트가 표시됩니다.")
        return

    # 상단 2열: 시간별 생산량 | Task별 달성률
    col_l, col_r = st.columns(2)

    with col_l:
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
            fig_h.update_layout(height=300, margin=dict(l=10, r=10, t=50, b=10))
            st.plotly_chart(fig_h, use_container_width=True, key=f"hourly_{bm_name}")
        else:
            st.info("시간별 통계 데이터 없음")

    with col_r:
        if per_task:
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
            fig_bar.update_layout(height=300, margin=dict(l=10, r=10, t=50, b=10))
            st.plotly_chart(fig_bar, use_container_width=True, key=f"per_task_{bm_name}")
        else:
            st.info("Task별 달성률 데이터 없음")

    # 전체 폭: 장비 배치 간트차트
    st.subheader("장비 배치 간트차트")
    if not assign_merged:
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

        if not gantt_data:
            st.info("간트 표시 데이터가 없습니다.")
        else:
            df_g = pd.DataFrame(gantt_data)
            n_eqp = df_g["장비ID"].nunique()
            fig = px.timeline(
                df_g,
                x_start="시작",
                x_end="종료",
                y="장비ID",
                color="작업",
                hover_data=["생산량", "모델"],
                title=f"{bm_name} — 장비 배치 타임라인",
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
            st.plotly_chart(fig, use_container_width=True, key=f"gantt_{bm_name}")


def render_tables(result: dict) -> None:
    plan_achv_rows = result["plan_achv_rows"]
    assign_rows = result["assign_rows"]
    assign_merged = merge_assign_rows(assign_rows)
    conv_rows = result["conv_rows"]

    with st.expander(f"📋 PLAN_ACHV_INF ({len(plan_achv_rows)}행)", expanded=False):
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

    orig_n = len(assign_rows)
    mrgd_n = len(assign_merged)
    with st.expander(
        f"🔧 ASSIGN_INF — 병합 후 {mrgd_n}행 (원래 {orig_n}행, {orig_n - mrgd_n}행 절감)",
        expanded=False,
    ):
        if assign_merged and _HAS_PLOTLY:
            df_as = pd.DataFrame(assign_merged)[ASSIGN_KEYS].copy()
            df_as.columns = ASSIGN_HEADERS
            st.dataframe(df_as, use_container_width=True, hide_index=True)
        elif assign_merged:
            st.json(assign_merged[:10])
        else:
            st.info("데이터 없음")

    with st.expander(f"🔄 CONV_INF ({len(conv_rows)}행)", expanded=False):
        if conv_rows and _HAS_PLOTLY:
            df_cv = pd.DataFrame(conv_rows)[CONV_KEYS].copy()
            df_cv.columns = CONV_HEADERS
            st.dataframe(df_cv, use_container_width=True, hide_index=True)
        elif conv_rows:
            st.json(conv_rows)
        else:
            st.info("전환(Conversion) 이벤트 없음")


# ────────────────────────────────────────────────────────────────
# Benchmark 파일 탐색
# ────────────────────────────────────────────────────────────────
benchmark_files = sorted(config.BENCHMARKS_DIR.glob("benchmark_*.json"))
if not benchmark_files:
    st.error("benchmarks/ 폴더에 JSON 파일이 없습니다.")
    st.stop()

benchmark_names = [f.stem for f in benchmark_files]
tab_labels = [f"BM-{i+1:02d}" for i in range(len(benchmark_names))] + ["📊 전체 비교"]

# ────────────────────────────────────────────────────────────────
# 메인 타이틀
# ────────────────────────────────────────────────────────────────
st.title("🏭 RTS 장비 스케줄링 대시보드")

all_tabs = st.tabs(tab_labels)

# ────────────────────────────────────────────────────────────────
# 벤치마크별 탭 (BM-01 ~ BM-09)
# ────────────────────────────────────────────────────────────────
for i, (tab, bm_name) in enumerate(zip(all_tabs[:-1], benchmark_names)):
    with tab:
        bm_path = config.BENCHMARKS_DIR / f"{bm_name}.json"
        problem, result = _load_and_eval(str(bm_path))

        total_move = compute_total_move(result["hourly_stats"])

        # Zone A: KPI 수치 (상단)
        render_kpi_row(problem, result, total_move)
        st.divider()

        # Zone B: 차트 (중간)
        render_charts(tab_labels[i], result, problem)
        st.divider()

        # Zone C: 세부 데이터 (하단)
        render_tables(result)

# ────────────────────────────────────────────────────────────────
# 전체 비교 탭
# ────────────────────────────────────────────────────────────────
with all_tabs[-1]:
    st.subheader("전체 벤치마크 비교")

    summary_rows = []
    for i, bm_name in enumerate(benchmark_names):
        bm_path = config.BENCHMARKS_DIR / f"{bm_name}.json"
        p, r = _load_and_eval(str(bm_path))
        util_avg = r.get("avg_utilization", avg_utilization(r["hourly_stats"]))
        achievement = r["heuristic"]
        optimal = r.get("optimal")
        total_move = compute_total_move(r["hourly_stats"])
        gap = achievement - optimal if optimal is not None else None
        summary_rows.append({
            "벤치마크": tab_labels[i],
            "계획달성률": achievement,
            "최적달성률": optimal,
            "Gap": gap,
            "장비가동률": util_avg,
            "move량": total_move,
            "horizon(h)": p.horizon_hours,
            "tasks": len(p.tasks),
        })

    # 상단 요약 KPI
    valid_achievements = [r["계획달성률"] for r in summary_rows]
    valid_optims = [r["최적달성률"] for r in summary_rows if r["최적달성률"] is not None]
    valid_gaps = [r["Gap"] for r in summary_rows if r["Gap"] is not None]
    valid_utils = [r["장비가동률"] for r in summary_rows]

    km1, km2, km3 = st.columns(3)
    km1.metric("평균 계획달성률", f"{sum(valid_achievements)/len(valid_achievements):.1%}")
    km2.metric("평균 장비가동률", f"{sum(valid_utils)/len(valid_utils):.1%}")
    if valid_gaps:
        km3.metric("평균 Gap (휴리스틱−최적)", f"{sum(valid_gaps)/len(valid_gaps):+.1%}")
    else:
        km3.metric("평균 Gap (휴리스틱−최적)", "N/A")

    st.divider()

    if _HAS_PLOTLY:
        # 비교 차트 2열
        cc_l, cc_r = st.columns(2)

        with cc_l:
            df_cmp = pd.DataFrame(summary_rows)
            bar_rows = []
            for row in summary_rows:
                bar_rows.append({"벤치마크": row["벤치마크"], "구분": "휴리스틱", "달성률": row["계획달성률"]})
                if row["최적달성률"] is not None:
                    bar_rows.append({"벤치마크": row["벤치마크"], "구분": "최적", "달성률": row["최적달성률"]})
            df_bar = pd.DataFrame(bar_rows)
            fig_cmp = px.bar(
                df_bar,
                x="벤치마크",
                y="달성률",
                color="구분",
                barmode="group",
                title="계획달성률 비교 (휴리스틱 vs 최적)",
                color_discrete_map={"휴리스틱": "#636EFA", "최적": "#EF553B"},
            )
            fig_cmp.update_yaxes(range=[0, 1.05], tickformat=".0%")
            fig_cmp.update_layout(height=320, margin=dict(l=10, r=10, t=50, b=10))
            st.plotly_chart(fig_cmp, use_container_width=True, key="cmp_achievement")

        with cc_r:
            df_util = pd.DataFrame(summary_rows)
            fig_util = px.bar(
                df_util,
                x="벤치마크",
                y="장비가동률",
                title="벤치마크별 평균 장비가동률",
                color="장비가동률",
                color_continuous_scale="Blues",
                text=df_util["장비가동률"].apply(lambda x: f"{x:.1%}"),
            )
            fig_util.update_yaxes(range=[0, 1.05], tickformat=".0%")
            fig_util.update_layout(height=320, margin=dict(l=10, r=10, t=50, b=10))
            st.plotly_chart(fig_util, use_container_width=True, key="cmp_utilization")

        st.divider()

        # 요약 테이블
        st.subheader("벤치마크 요약 테이블")
        df_summary = pd.DataFrame(summary_rows)
        df_display = df_summary.copy()
        df_display["계획달성률"] = df_display["계획달성률"].map(lambda x: f"{x:.1%}")
        df_display["최적달성률"] = df_display["최적달성률"].map(
            lambda x: f"{x:.1%}" if x is not None else "N/A"
        )
        df_display["Gap"] = df_display["Gap"].map(
            lambda x: f"{x:+.1%}" if x is not None else "N/A"
        )
        df_display["장비가동률"] = df_display["장비가동률"].map(lambda x: f"{x:.1%}")
        df_display["move량"] = df_display["move량"].map(lambda x: f"{x:,}")
        st.dataframe(df_display, use_container_width=True, hide_index=True)

    else:
        st.warning("`pip install plotly pandas` 설치 후 재시작하면 차트가 표시됩니다.")
        for row in summary_rows:
            st.write(
                f"**{row['벤치마크']}**: 달성률 {row['계획달성률']:.1%}, "
                f"가동률 {row['장비가동률']:.1%}, move {row['move량']:,}"
            )
