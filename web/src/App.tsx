import { useEffect, useState } from "react";
import { fetchDetail, fetchSummary } from "./api";
import type { DatasetDetail, Summary } from "./types";
import OverviewCards from "./components/OverviewCards";
import BenchmarkTable from "./components/BenchmarkTable";
import GanttChart from "./components/GanttChart";
import "./styles.css";

type EnvType = "dispatch" | "alloc";
type Algo = "heuristic" | "rl";

export default function App() {
  const [envType, setEnvType] = useState<EnvType>("dispatch");
  const [summary, setSummary] = useState<Summary | null>(null);
  const [selected, setSelected] = useState<string>("");
  const [detail, setDetail] = useState<DatasetDetail | null>(null);
  const [algo, setAlgo] = useState<Algo>("heuristic");
  const [loadingSummary, setLoadingSummary] = useState(false);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load summary when envType changes
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

  // Load detail when selected changes
  useEffect(() => {
    if (!selected) return;
    setLoadingDetail(true);
    setError(null);
    fetchDetail(selected, envType)
      .then((d) => {
        setDetail(d);
        // fallback to heuristic if rl not available
        if (d.algorithms.rl == null) setAlgo("heuristic");
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoadingDetail(false));
  }, [selected, envType]);

  const algoView = detail?.algorithms[algo] ?? detail?.algorithms.heuristic ?? null;
  const rlAvailable = detail?.algorithms.rl != null;

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

      {/* Overview KPI cards */}
      {summary && !loadingSummary && (
        <OverviewCards summary={summary} />
      )}
      {loadingSummary && <div className="empty">데이터 불러오는 중…</div>}

      {/* Split: benchmark list + detail */}
      {summary && !loadingSummary && (
        <div className="split-panel">
          {/* Left: benchmark list */}
          <div className="bench-list-panel">
            <h2>벤치마크 목록 ({summary.rows.length})</h2>
            <BenchmarkTable
              rows={summary.rows}
              selected={selected}
              onSelect={(name) => { setSelected(name); setAlgo("heuristic"); }}
            />
          </div>

          {/* Right: detail + gantt */}
          <div className="detail-panel">
            {!selected && (
              <div className="placeholder">벤치마크를 선택하면 간트차트가 표시됩니다.</div>
            )}
            {selected && loadingDetail && (
              <div className="placeholder">불러오는 중…</div>
            )}
            {selected && !loadingDetail && detail && algoView && (
              <>
                {/* Meta */}
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

                {/* Algo toggle */}
                <div className="algo-row">
                  <h2>간트차트</h2>
                  <div className="seg">
                    <button className={algo === "heuristic" ? "active" : ""}
                            onClick={() => setAlgo("heuristic")}>
                      휴리스틱
                    </button>
                    <button className={algo === "rl" ? "active" : ""}
                            disabled={!rlAvailable}
                            title={rlAvailable ? "" : "학습된 RL 모델 없음"}
                            onClick={() => setAlgo("rl")}>
                      RL
                    </button>
                  </div>
                  {/* KPIs inline */}
                  <span style={{ fontSize: 13, color: "#6b7689", marginLeft: 8 }}>
                    달성률 <b style={{ color: "#3b6fe0" }}>
                      {(algoView.kpis.plan_achievement * 100).toFixed(1)}%
                    </b>
                    {" · "}가동률 <b>{(algoView.kpis.avg_utilization * 100).toFixed(1)}%</b>
                    {" · "}전환 <b>{algoView.kpis.conversion_count}건</b>
                    {detail.optimal != null && (
                      <> · 최적 <b style={{ color: "#18a06c" }}>
                        {(detail.optimal * 100).toFixed(1)}%
                      </b></>
                    )}
                  </span>
                </div>

                {/* Gantt */}
                <GanttChart segments={algoView.gantt} />
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
