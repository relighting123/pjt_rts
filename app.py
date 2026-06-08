"""Streamlit 대시보드: RTS 장비 스케줄링 시뮬레이션 결과 조회."""
from __future__ import annotations
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent))

if __name__ == "__main__":
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        if get_script_run_ctx() is None:
            print("app.py는 Streamlit UI 전용입니다.")
            print("  streamlit run app.py")
            print("CLI 추론/학습은: python run.py infer | train | eval")
            raise SystemExit(1)
    except ImportError:
        print("streamlit 미설치. pip install -e \".[web]\" 후 streamlit run app.py")
        raise SystemExit(1)

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
    guide_allocation_rows,
    PLAN_ACHV_HEADERS, PLAN_ACHV_KEYS,
    ASSIGN_HEADERS, ASSIGN_KEYS,
    CONV_HEADERS, CONV_KEYS,
)
import config


def _parse_tm(s: str) -> datetime:
    return datetime.strptime(s[:14].ljust(14, "0"), "%Y%m%d%H%M%S")


@st.cache_resource(show_spinner="모델 로딩 중…")
def _load_model():
    if not Path(config.MODEL_PATH).exists():
        return None
    try:
        from sb3_contrib import MaskablePPO
        return MaskablePPO.load(config.MODEL_PATH)
    except Exception:
        return None


@st.cache_data(show_spinner="시뮬레이션 실행 중…")
def _load_and_eval(path_str: str):
    p = load_problem(path_str)
    res = evaluate_benchmark(p, model=_load_model())
    return p, res


def compute_total_move(hourly_stats: list[dict]) -> int:
    if not hourly_stats:
        return 0
    return sum(hourly_stats[-1]["cumulative_produced"].values())


ALGO_LABELS = ["휴리스틱", "RL", "최적해"]


def _algo_view(result: dict, algo: str):
    """algo별로 정규화된 결과 묶음. 데이터가 없으면 None."""
    if algo == "휴리스틱":
        return {
            "achievement": result["heuristic"],
            "per_task": result.get("heuristic_per_task", {}),
            "hourly_stats": result["hourly_stats"],
            "avg_utilization": result.get("avg_utilization", avg_utilization(result["hourly_stats"])),
            "plan_achv_rows": result.get("plan_achv_rows", []),
            "assign_rows": result.get("assign_rows", []),
            "conv_rows": result.get("conv_rows", []),
            "has_detail": True,
        }
    if algo == "RL":
        if result.get("rl") is None:
            return None
        return {
            "achievement": result["rl"],
            "per_task": result.get("rl_per_task", {}),
            "hourly_stats": result.get("rl_hourly_stats", []),
            "avg_utilization": result.get("rl_avg_utilization"),
            "plan_achv_rows": result.get("rl_plan_achv_rows", []),
            "assign_rows": result.get("rl_assign_rows", []),
            "conv_rows": result.get("rl_conv_rows", []),
            "has_detail": True,
        }
    if algo == "최적해":
        if result.get("optimal") is None:
            return None
        return {
            "achievement": result["optimal"],
            "per_task": None,
            "hourly_stats": None,
            "avg_utilization": None,
            "plan_achv_rows": None,
            "assign_rows": None,
            "conv_rows": None,
            "has_detail": False,
        }
    return None


def render_kpi_row(result, view, algo: str) -> None:
    optimal = result.get("optimal")
    achievement = view["achievement"]

    c1, c2, c3 = st.columns(3)
    delta = None
    if optimal is not None and algo != "최적해":
        delta = f"{achievement - optimal:+.1%} (vs 최적)"
    c1.metric(f"{algo} 계획달성률", f"{achievement:.1%}", delta=delta)
    c2.metric(
        f"{algo} 장비 가동률",
        f"{view['avg_utilization']:.1%}" if view["avg_utilization"] is not None else "N/A",
    )
    c3.metric(
        f"{algo} move량 (총 생산)",
        f"{compute_total_move(view['hourly_stats']):,}" if view["hourly_stats"] else "N/A",
    )


def render_charts(bm_name: str, algo: str, view) -> None:
    if not _HAS_PLOTLY:
        st.warning("`pip install plotly pandas` 설치 후 재시작하면 차트가 표시됩니다.")
        return

    hourly_stats = view["hourly_stats"]
    per_task = view["per_task"]
    assign_rows = view["assign_rows"]
    assign_merged = merge_assign_rows(assign_rows) if assign_rows else []
    key_prefix = f"{bm_name}_{algo}"

    col_l, col_r = st.columns(2)

    with col_l:
        if hourly_stats:
            hourly_data = [{
                "Hour": stat["hour"],
                "시간대 생산량": sum(stat["hourly_produce"].values()),
                "누적 생산량": sum(stat["cumulative_produced"].values()),
                "가동률": stat["util_rate"],
            } for stat in hourly_stats]
            df_h = pd.DataFrame(hourly_data)
            fig_h = px.bar(
                df_h, x="Hour", y="시간대 생산량", title=f"{algo} — 시간별 생산량",
                text="시간대 생산량", color="가동률", color_continuous_scale="Blues",
            )
            fig_h.update_layout(height=300, margin=dict(l=10, r=10, t=50, b=10))
            st.plotly_chart(fig_h, use_container_width=True, key=f"hourly_{key_prefix}")
        else:
            st.info("시간별 통계 데이터 없음")

    with col_r:
        if per_task:
            rows_pt = [{
                "Task": k, "계획(plan_qty)": v["plan"], "생산(produced)": v["produced"], "달성률": v["rate"],
            } for k, v in per_task.items()]
            df_pt = pd.DataFrame(rows_pt)
            fig_bar = px.bar(
                df_pt, x="Task", y="달성률", color="달성률", color_continuous_scale="RdYlGn",
                range_color=[0, 1], text=df_pt["달성률"].apply(lambda x: f"{x:.1%}"),
                title=f"{algo} — Task별 계획달성률", hover_data=["계획(plan_qty)", "생산(produced)"],
            )
            fig_bar.update_yaxes(range=[0, 1.05], tickformat=".0%")
            fig_bar.update_layout(height=300, margin=dict(l=10, r=10, t=50, b=10))
            st.plotly_chart(fig_bar, use_container_width=True, key=f"per_task_{key_prefix}")
        else:
            st.info("Task별 달성률 데이터 없음")

    st.subheader(f"{algo} — 장비 배치 간트차트")
    if not assign_merged:
        st.info("ASSIGN 데이터가 없습니다.")
        return

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
            "장비ID": r["EQP_ID"], "작업": task_label, "시작": start, "종료": end,
            "생산량": r["PRODUCE_QTY"], "모델": r["EQP_MODEL_CD"],
        })

    if not gantt_data:
        st.info("간트 표시 데이터가 없습니다.")
        return

    df_g = pd.DataFrame(gantt_data)
    n_eqp = df_g["장비ID"].nunique()
    fig = px.timeline(
        df_g, x_start="시작", x_end="종료", y="장비ID", color="작업",
        hover_data=["생산량", "모델"], title=f"{bm_name} · {algo} — 장비 배치 타임라인",
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
    st.plotly_chart(fig, use_container_width=True, key=f"gantt_{key_prefix}")


def render_tables(bm_name: str, algo: str, view) -> None:
    plan_achv_rows = view["plan_achv_rows"]
    assign_rows = view["assign_rows"]
    assign_merged = merge_assign_rows(assign_rows) if assign_rows else []
    conv_rows = view["conv_rows"]
    key_prefix = f"{bm_name}_{algo}"

    with st.expander(f"📋 {algo} — PLAN_ACHV_INF ({len(plan_achv_rows)}행)", expanded=False):
        if plan_achv_rows and _HAS_PLOTLY:
            df_pa = pd.DataFrame(plan_achv_rows)[PLAN_ACHV_KEYS].copy()
            df_pa.columns = PLAN_ACHV_HEADERS
            df_pa["ACHIEVE_RATE"] = df_pa["ACHIEVE_RATE"].map(lambda x: f"{float(x):.1%}")
            df_pa["EQP_UTIL_RATE"] = df_pa["EQP_UTIL_RATE"].map(lambda x: f"{float(x):.1%}")
            st.dataframe(df_pa, use_container_width=True, hide_index=True, key=f"tbl_pa_{key_prefix}")
        elif plan_achv_rows:
            st.json(plan_achv_rows[:10])
        else:
            st.info("데이터 없음")

    orig_n = len(assign_rows)
    mrgd_n = len(assign_merged)
    with st.expander(
        f"🔧 {algo} — ASSIGN_INF — 병합 후 {mrgd_n}행 (원래 {orig_n}행, {orig_n - mrgd_n}행 절감)",
        expanded=False,
    ):
        if assign_merged and _HAS_PLOTLY:
            df_as = pd.DataFrame(assign_merged)[ASSIGN_KEYS].copy()
            df_as.columns = ASSIGN_HEADERS
            st.dataframe(df_as, use_container_width=True, hide_index=True, key=f"tbl_as_{key_prefix}")
        elif assign_merged:
            st.json(assign_merged[:10])
        else:
            st.info("데이터 없음")

    with st.expander(f"🔄 {algo} — EQPCONVPLAN_INF ({len(conv_rows)}행)", expanded=False):
        if conv_rows and _HAS_PLOTLY:
            df_cv = pd.DataFrame(conv_rows)[CONV_KEYS].copy()
            df_cv.columns = CONV_HEADERS
            st.dataframe(df_cv, use_container_width=True, hide_index=True, key=f"tbl_cv_{key_prefix}")
        elif conv_rows:
            st.json(conv_rows)
        else:
            st.info("전환(Conversion) 이벤트 없음")


def _guide_source_label() -> str:
    alloc_path = config.SAVED_MODELS_DIR / "ppo_alloc.zip"
    if config.USE_ALLOC_MODEL and alloc_path.exists():
        return "AllocationEnv RL (ppo_alloc.zip)"
    return "해석식 (plan_target_allocation)"


def render_guide_section(bm_name: str, problem, result: dict) -> None:
    guide_allocation = result.get("guide_allocation", {})
    if not guide_allocation and not guide_allocation_rows(problem, {}):
        st.info("가이드 배분 데이터 없음")
        return

    st.subheader("가이드 수량 (재공 무한 기준 목표 배치)")
    st.caption(f"출처: **{_guide_source_label()}**")

    rows = guide_allocation_rows(problem, guide_allocation)
    col_table, col_chart = st.columns(2)

    with col_table:
        if _HAS_PLOTLY:
            df_guide = pd.DataFrame(rows)
            df_guide = df_guide.rename(columns={
                "task": "공정(PLAN_PROD_KEY/OPER)",
                "model": "모델",
                "target_count": "목표 대수",
            })
            df_guide["목표 대수"] = df_guide["목표 대수"].map(lambda x: f"{int(x)}")
            st.dataframe(
                df_guide,
                use_container_width=True,
                hide_index=True,
                key=f"guide_tbl_{bm_name}",
            )
        else:
            for row in rows:
                st.write(f"{row['task']} · {row['model']}: **{int(row['target_count'])}**대")

    with col_chart:
        if not _HAS_PLOTLY:
            st.caption("차트는 plotly/pandas 설치 후 표시됩니다.")
            return
        pivot = pd.DataFrame(rows).pivot(index="task", columns="model", values="target_count").fillna(0)
        if pivot.empty:
            st.info("차트 데이터 없음")
            return
        fig = px.imshow(
            pivot,
            text_auto=".1f",
            color_continuous_scale="Blues",
            aspect="auto",
            title="모델×공정 목표 대수",
            labels={"x": "모델", "y": "공정", "color": "목표 대수"},
        )
        fig.update_layout(height=max(260, 60 * len(pivot) + 120), margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig, use_container_width=True, key=f"guide_heat_{bm_name}")


def render_algo_section(bm_name: str, algo: str, result: dict, problem) -> None:
    view = _algo_view(result, algo)
    if view is None:
        if algo == "RL":
            st.info("ℹ️ 학습된 모델(saved_models/ppo_dispatch.zip)이 없거나 현재 벤치마크와 관측·액션 공간이 맞지 않아 RL 결과가 없습니다.")
        else:
            st.info("ℹ️ 최적해 데이터가 없습니다.")
        return

    render_kpi_row(result, view, algo)
    st.divider()

    if view["has_detail"]:
        render_charts(bm_name, algo, view)
        st.divider()
        render_tables(bm_name, algo, view)
    else:
        st.info("ℹ️ 최적해는 시간대별 장비배치 trace 없이 계획달성률 수치(정답)만 보유하고 있어 차트·테이블은 표시되지 않습니다.")


# ────────────────────────────────────────────────────────────────
# Benchmark 파일 탐색
# ────────────────────────────────────────────────────────────────
benchmark_files = sorted(config.TEST_DATA_DIR.glob("*.json"))
if not benchmark_files:
    st.error("data/test/ 폴더에 JSON 파일이 없습니다.")
    st.stop()

benchmark_names = [f.stem for f in benchmark_files]
tab_labels = [f"BM-{i+1:02d}" for i in range(len(benchmark_names))] + ["📊 전체 비교"]

# ────────────────────────────────────────────────────────────────
# 메인 타이틀
# ────────────────────────────────────────────────────────────────
st.title("🏭 RTS 장비 스케줄링 대시보드")

all_tabs = st.tabs(tab_labels)

# ────────────────────────────────────────────────────────────────
# 벤치마크별 탭 (BM-01 ~ BM-09): 휴리스틱/RL/최적해 알고리즘별 서브탭
# ────────────────────────────────────────────────────────────────
for i, (tab, bm_name) in enumerate(zip(all_tabs[:-1], benchmark_names)):
    with tab:
        bm_path = config.TEST_DATA_DIR / f"{bm_name}.json"
        problem, result = _load_and_eval(str(bm_path))

        st.caption(
            f"RULE_TIMEKEY: **{problem.rule_timekey}** │ "
            f"Horizon: **{problem.horizon_hours}h** │ "
            f"Tasks: **{len(problem.tasks)}** │ "
            f"장비 합계: **{sum(problem.eqp_qty.values())}대**"
        )
        note = problem.ground_truth.get("note", "")
        if note:
            st.info(f"ℹ️ {note}")

        render_guide_section(tab_labels[i], problem, result)
        st.divider()

        algo_tabs = st.tabs(ALGO_LABELS)
        for algo, atab in zip(ALGO_LABELS, algo_tabs):
            with atab:
                render_algo_section(tab_labels[i], algo, result, problem)


# ────────────────────────────────────────────────────────────────
# 전체 비교 탭
# ────────────────────────────────────────────────────────────────
with all_tabs[-1]:
    st.subheader("전체 벤치마크 비교")

    has_rl = False
    summary_rows = []
    for i, bm_name in enumerate(benchmark_names):
        bm_path = config.TEST_DATA_DIR / f"{bm_name}.json"
        p, r = _load_and_eval(str(bm_path))
        util_avg = r.get("avg_utilization", avg_utilization(r["hourly_stats"]))
        rl_util_avg = r.get("rl_avg_utilization")
        heuristic = r["heuristic"]
        rl = r.get("rl")
        optimal = r.get("optimal")
        if rl is not None:
            has_rl = True
        total_move = compute_total_move(r["hourly_stats"])
        gap = (rl if rl is not None else heuristic) - optimal if optimal is not None else None
        summary_rows.append({
            "벤치마크": tab_labels[i],
            "휴리스틱달성률": heuristic,
            "RL달성률": rl,
            "최적달성률": optimal,
            "Gap": gap,
            "휴리스틱가동률": util_avg,
            "RL가동률": rl_util_avg,
            "move량": total_move,
            "horizon(h)": p.horizon_hours,
            "tasks": len(p.tasks),
        })

    if not has_rl:
        st.info("ℹ️ 학습된 모델(saved_models/ppo_dispatch.zip)이 없거나 현재 벤치마크와 관측·액션 공간이 맞지 않아 RL 결과 없이 휴리스틱·최적 기준으로만 비교합니다.")

    # 상단 요약 KPI
    valid_heuristics = [r["휴리스틱달성률"] for r in summary_rows]
    valid_rls = [r["RL달성률"] for r in summary_rows if r["RL달성률"] is not None]
    valid_gaps = [r["Gap"] for r in summary_rows if r["Gap"] is not None]
    valid_utils = [r["휴리스틱가동률"] for r in summary_rows]

    km1, km2, km3, km4 = st.columns(4)
    km1.metric("평균 휴리스틱 달성률", f"{sum(valid_heuristics)/len(valid_heuristics):.1%}")
    km2.metric(
        "평균 RL 달성률",
        f"{sum(valid_rls)/len(valid_rls):.1%}" if valid_rls else "N/A",
    )
    km3.metric("평균 장비가동률 (휴리스틱)", f"{sum(valid_utils)/len(valid_utils):.1%}")
    if valid_gaps:
        gap_label = "평균 Gap (RL−최적)" if has_rl else "평균 Gap (휴리스틱−최적)"
        km4.metric(gap_label, f"{sum(valid_gaps)/len(valid_gaps):+.1%}")
    else:
        km4.metric("평균 Gap (−최적)", "N/A")

    st.divider()

    if _HAS_PLOTLY:
        # 비교 차트 2열
        cc_l, cc_r = st.columns(2)

        with cc_l:
            bar_rows = []
            for row in summary_rows:
                bar_rows.append({"벤치마크": row["벤치마크"], "구분": "휴리스틱", "달성률": row["휴리스틱달성률"]})
                if row["RL달성률"] is not None:
                    bar_rows.append({"벤치마크": row["벤치마크"], "구분": "RL", "달성률": row["RL달성률"]})
                if row["최적달성률"] is not None:
                    bar_rows.append({"벤치마크": row["벤치마크"], "구분": "최적", "달성률": row["최적달성률"]})
            df_bar = pd.DataFrame(bar_rows)
            fig_cmp = px.bar(
                df_bar,
                x="벤치마크",
                y="달성률",
                color="구분",
                barmode="group",
                title="계획달성률 비교 (휴리스틱 vs RL vs 최적)",
                color_discrete_map={"휴리스틱": "#636EFA", "RL": "#00CC96", "최적": "#EF553B"},
            )
            fig_cmp.update_yaxes(range=[0, 1.05], tickformat=".0%")
            fig_cmp.update_layout(height=320, margin=dict(l=10, r=10, t=50, b=10))
            st.plotly_chart(fig_cmp, use_container_width=True, key="cmp_achievement")

        with cc_r:
            util_rows = []
            for row in summary_rows:
                util_rows.append({"벤치마크": row["벤치마크"], "구분": "휴리스틱", "가동률": row["휴리스틱가동률"]})
                if row["RL가동률"] is not None:
                    util_rows.append({"벤치마크": row["벤치마크"], "구분": "RL", "가동률": row["RL가동률"]})
            df_util = pd.DataFrame(util_rows)
            fig_util = px.bar(
                df_util,
                x="벤치마크",
                y="가동률",
                color="구분",
                barmode="group",
                title="벤치마크별 평균 장비가동률 (휴리스틱 vs RL)",
                color_discrete_map={"휴리스틱": "#636EFA", "RL": "#00CC96"},
            )
            fig_util.update_yaxes(range=[0, 1.05], tickformat=".0%")
            fig_util.update_layout(height=320, margin=dict(l=10, r=10, t=50, b=10))
            st.plotly_chart(fig_util, use_container_width=True, key="cmp_utilization")

        st.divider()

        # 요약 테이블
        st.subheader("벤치마크 요약 테이블")
        df_summary = pd.DataFrame(summary_rows)
        df_display = df_summary.copy()
        df_display["휴리스틱달성률"] = df_display["휴리스틱달성률"].map(lambda x: f"{x:.1%}")
        df_display["RL달성률"] = df_display["RL달성률"].map(
            lambda x: f"{x:.1%}" if x is not None else "N/A"
        )
        df_display["최적달성률"] = df_display["최적달성률"].map(
            lambda x: f"{x:.1%}" if x is not None else "N/A"
        )
        df_display["Gap"] = df_display["Gap"].map(
            lambda x: f"{x:+.1%}" if x is not None else "N/A"
        )
        df_display["휴리스틱가동률"] = df_display["휴리스틱가동률"].map(lambda x: f"{x:.1%}")
        df_display["RL가동률"] = df_display["RL가동률"].map(
            lambda x: f"{x:.1%}" if x is not None else "N/A"
        )
        df_display["move량"] = df_display["move량"].map(lambda x: f"{x:,}")
        st.dataframe(df_display, use_container_width=True, hide_index=True)

    else:
        st.warning("`pip install plotly pandas` 설치 후 재시작하면 차트가 표시됩니다.")
        for row in summary_rows:
            rl_str = f", RL {row['RL달성률']:.1%}" if row["RL달성률"] is not None else ""
            st.write(
                f"**{row['벤치마크']}**: 휴리스틱 {row['휴리스틱달성률']:.1%}{rl_str}, "
                f"가동률 {row['휴리스틱가동률']:.1%}, move {row['move량']:,}"
            )
