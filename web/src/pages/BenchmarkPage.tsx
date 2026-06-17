import { useEffect, useState } from "react";
import { fetchDetail, fetchSummary } from "../api";
import type { DatasetDetail, Summary } from "../types";
import OverviewCards from "../components/OverviewCards";
import BenchmarkPerformanceChart from "../components/BenchmarkPerformanceChart";
import AlgoComparePanel from "../components/AlgoComparePanel";
import ConvergenceChart from "../components/ConvergenceChart";

type EnvType = "dispatch" | "alloc";

export default function BenchmarkPage() {
  const [envType, setEnvType] = useState<EnvType>("dispatch");
  const [summary, setSummary] = useState<Summary | null>(null);
  const [selected, setSelected] = useState("");
  const [detail, setDetail] = useState<DatasetDetail | null>(null);
  const [loadingSummary, setLoadingSummary] = useState(false);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
    onSelect: setSelected,
    compact: true,
  };

  return (
    <div className="page">
      <header className="page-header row">
        <div>
          <h1>벤치마크 분석</h1>
          <p className="page-sub">휴리스틱 vs RL 상세 비교 · 간트/배분 시각화</p>
        </div>
        <div className="seg">
          <button
            type="button"
            className={envType === "dispatch" ? "active" : ""}
            onClick={() => setEnvType("dispatch")}
          >
            DispatchEnv
          </button>
          <button
            type="button"
            className={envType === "alloc" ? "active" : ""}
            onClick={() => setEnvType("alloc")}
          >
            AllocEnv
          </button>
        </div>
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
                    onClick={() => setSelected(r.name)}
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
                  subtitle={
                    envType === "alloc"
                      ? "시간한계 또는 배분밀도 / 계획"
                      : "시뮬레이션 생산 / 계획"
                  }
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
                </div>
                <h2 className="section-title">
                  {envType === "alloc" ? "휴리스틱 vs RL · 장비 배분" : "휴리스틱 vs RL · 간트차트"}
                </h2>
                <AlgoComparePanel detail={detail} envType={envType} rlAvailable={rlAvailable} />
              </>
            )}
          </section>

          <section className="convergence-panel panel-card">
            <h2>학습 수렴</h2>
            <ConvergenceChart stage="dispatch" />
          </section>
        </div>
      )}
    </div>
  );
}
