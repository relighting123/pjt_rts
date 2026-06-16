import { useEffect, useState } from "react";
import { fetchDetail, fetchSummary } from "./api";
import type { DatasetDetail, Summary } from "./types";
import OverviewCards from "./components/OverviewCards";
import BenchmarkPerformanceChart from "./components/BenchmarkPerformanceChart";
import AlgoComparePanel from "./components/AlgoComparePanel";
import ConvergenceChart from "./components/ConvergenceChart";
import "./styles.css";

type EnvType = "dispatch" | "alloc";

export default function App() {
  const [envType, setEnvType] = useState<EnvType>("dispatch");
  const [summary, setSummary] = useState<Summary | null>(null);
  const [selected, setSelected] = useState<string>("");
  const [detail, setDetail] = useState<DatasetDetail | null>(null);
  const [loadingSummary, setLoadingSummary] = useState(false);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectBenchmark = (name: string) => setSelected(name);

  useEffect(() => {
    setLoadingSummary(true);
    setError(null);
    setSummary(null);
    setDetail(null);
    setSelected("");
    fetchSummary(envType)
      .then((s) => {
        setSummary(s);
        if (s.rows.length > 0) setSelected(s.rows[0].name);
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoadingSummary(false));
  }, [envType]);

  useEffect(() => {
    if (!selected) return;
    setLoadingDetail(true);
    setError(null);
    fetchDetail(selected, envType)
      .then(setDetail)
      .catch((e) => setError(String(e)))
      .finally(() => setLoadingDetail(false));
  }, [selected, envType]);

  const rlAvailable = detail?.rl_status.available ?? false;
  const chartProps = {
    rows: summary?.rows ?? [],
    selected,
    onSelect: selectBenchmark,
    compact: true,
  };

  return (
    <div className="app">
      <header className="header">
        <h1>RTS 장비 스케줄링 대시보드</h1>
        <div className="seg">
          <button className={envType === "dispatch" ? "active" : ""} onClick={() => setEnvType("dispatch")}>
            DispatchEnv
          </button>
          <button className={envType === "alloc" ? "active" : ""} onClick={() => setEnvType("alloc")}>
            AllocEnv
          </button>
        </div>
        <div className="spacer" />
      </header>

      {error && <div className="error">⚠ {error}</div>}

      {summary && !loadingSummary && <OverviewCards summary={summary} envType={envType} />}
      {loadingSummary && <div className="empty">데이터 불러오는 중…</div>}

      {summary && !loadingSummary && (
        <div className="dashboard-body">
          <section className="bench-metrics-section">
            <div className="section-head">
              <h2>벤치마크별 지표 ({summary.rows.length})</h2>
              <div className="bench-chips">
                {summary.rows.map((r) => (
                  <button
                    key={r.name}
                    type="button"
                    className={`bench-chip${selected === r.name ? " active" : ""}`}
                    onClick={() => selectBenchmark(r.name)}
                  >
                    {r.name}
                  </button>
                ))}
              </div>
            </div>
            <div className={`bench-metrics-row${envType === "dispatch" ? " cols-3" : " cols-1"}`}>
              <div className="bench-chart-panel">
                <BenchmarkPerformanceChart
                  {...chartProps}
                  metric="plan_achievement"
                  title={envType === "alloc" ? "계획달성률 (정적)" : "계획달성률 (동적)"}
                  subtitle={envType === "alloc"
                    ? "시간한계 또는 배분밀도 / 계획"
                    : "시뮬레이션 생산 / 계획"}
                />
              </div>
              {envType === "dispatch" && (
                <>
                  <div className="bench-chart-panel">
                    <BenchmarkPerformanceChart
                      {...chartProps}
                      metric="utilization"
                      title="가동률 (동적)"
                      subtitle="시뮬레이션 장비 가동률"
                    />
                  </div>
                  <div className="bench-chart-panel">
                    <BenchmarkPerformanceChart
                      {...chartProps}
                      metric="conversion"
                      title="장비 전환 (동적)"
                      subtitle="CONV 세그먼트 수"
                    />
                  </div>
                </>
              )}
            </div>
          </section>

          <section className="detail-panel">
            {!selected && <div className="placeholder">벤치마크를 선택하세요.</div>}
            {selected && loadingDetail && <div className="placeholder">불러오는 중…</div>}
            {selected && !loadingDetail && detail && (
              <>
                <div className="meta-line">
                  <b>{detail.name}</b>
                  {" · "}RULE_TIMEKEY <b>{detail.meta.rule_timekey}</b>
                  {" · "}Horizon <b>{detail.meta.horizon_hours}h</b>
                  {" · "}Tasks <b>{detail.meta.task_count}</b>
                  {" · "}EQP <b>{detail.meta.total_eqp}대</b>
                  {detail.meta.has_real_equipments
                    ? <span className="badge real">실제호기</span>
                    : <span className="badge virtual">가상호기</span>}
                  {detail.meta.note && <span style={{ marginLeft: 8 }}>— {detail.meta.note}</span>}
                </div>
                <h2 className="section-title">
                  {envType === "alloc" ? "휴리스틱 vs RL · 장비 배분" : "휴리스틱 vs RL · 간트차트"}
                </h2>
                <AlgoComparePanel detail={detail} envType={envType} rlAvailable={rlAvailable} />
              </>
            )}
          </section>

          <section className="convergence-panel">
            <h2>학습 수렴 차트</h2>
            <p className="panel-sub">DispatchEnv PPO 학습 시 평균 에피소드 보상 (BC 단계 포함)</p>
            <ConvergenceChart stage="dispatch" />
          </section>
        </div>
      )}
    </div>
  );
}
