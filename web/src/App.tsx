import { useEffect, useMemo, useState } from "react";
import { fetchDatasets, fetchDetail, fetchSummary, num, pct } from "./api";
import type { DatasetDetail, DatasetInfo, Summary } from "./types";
import KpiCards from "./components/KpiCards";
import GanttChart from "./components/GanttChart";
import HourlyChart from "./components/HourlyChart";
import TaskAchievement from "./components/TaskAchievement";
import ConversionTable from "./components/ConversionTable";
import GuideTable from "./components/GuideTable";
import SummaryView from "./components/SummaryView";

type Algo = "heuristic" | "rl";
type View = "detail" | "summary";

export default function App() {
  const [datasets, setDatasets] = useState<DatasetInfo[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [detail, setDetail] = useState<DatasetDetail | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [algo, setAlgo] = useState<Algo>("heuristic");
  const [view, setView] = useState<View>("detail");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchDatasets()
      .then((ds) => {
        setDatasets(ds);
        if (ds.length > 0) setSelected((cur) => cur || ds[0].name);
      })
      .catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    if (!selected || view !== "detail") return;
    setLoading(true);
    setError(null);
    fetchDetail(selected)
      .then(setDetail)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [selected, view]);

  useEffect(() => {
    if (view !== "summary" || summary) return;
    setLoading(true);
    setError(null);
    fetchSummary()
      .then(setSummary)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [view, summary]);

  const algoView = useMemo(() => {
    if (!detail) return null;
    const v = detail.algorithms[algo];
    return v ?? detail.algorithms.heuristic;
  }, [detail, algo]);

  const rlAvailable = detail?.algorithms.rl != null;
  const effectiveAlgo: Algo = algo === "rl" && !rlAvailable ? "heuristic" : algo;
  const algoLabel = effectiveAlgo === "rl" ? "RL" : "휴리스틱";

  return (
    <div className="app">
      <header className="header">
        <h1>🏭 RTS 장비 스케줄링 대시보드</h1>
        <div className="seg">
          <button className={view === "detail" ? "active" : ""} onClick={() => setView("detail")}>
            상세 분석
          </button>
          <button className={view === "summary" ? "active" : ""} onClick={() => setView("summary")}>
            전체 비교
          </button>
        </div>
        <div className="spacer" />
        {view === "detail" && (
          <>
            <select value={selected} onChange={(e) => setSelected(e.target.value)}>
              {datasets.map((d) => (
                <option key={d.name} value={d.name}>
                  [{d.kind === "benchmark" ? "벤치마크" : "추론"}] {d.name}
                </option>
              ))}
            </select>
            <div className="seg">
              <button className={effectiveAlgo === "heuristic" ? "active" : ""}
                      onClick={() => setAlgo("heuristic")}>
                휴리스틱
              </button>
              <button className={effectiveAlgo === "rl" ? "active" : ""} disabled={!rlAvailable}
                      onClick={() => setAlgo("rl")}
                      title={rlAvailable ? "" : "학습된 RL 모델 결과 없음"}>
                RL
              </button>
            </div>
          </>
        )}
      </header>

      {error && <div className="error">⚠️ {error}</div>}
      {loading && <div className="empty">불러오는 중…</div>}

      {view === "summary" && summary && !loading && (
        <SummaryView summary={summary} onSelect={(name) => { setSelected(name); setView("detail"); }} />
      )}

      {view === "detail" && detail && algoView && !loading && (
        <>
          <div className="meta-line">
            RULE_TIMEKEY <b>{detail.meta.rule_timekey}</b>
            {detail.meta.facid && <> · FAC <b>{detail.meta.facid}</b></>}
            {" · "}Horizon <b>{detail.meta.horizon_hours}h</b>
            {" · "}Tasks <b>{detail.meta.task_count}</b>
            {" · "}장비 <b>{detail.meta.total_eqp}대</b> ({detail.meta.model_count}개 모델)
            {detail.meta.has_real_equipments
              ? <span className="badge real">실제 장비 호기 매핑</span>
              : <span className="badge virtual">가상 호기 (명단 미제공)</span>}
            {detail.meta.note && <div>ℹ️ {detail.meta.note}</div>}
          </div>

          <KpiCards view={algoView} optimal={detail.optimal} algoLabel={algoLabel} />

          <div className="panel">
            <h2>
              장비 배치 간트차트
              <span className="sub">
                {algoLabel} · 호기(EQP_ID)별 타임라인 · 빗금 = tool 전환
              </span>
            </h2>
            <GanttChart segments={algoView.gantt} />
          </div>

          <div className="grid-2">
            <div className="panel">
              <h2>시간별 생산량 · 가동률 <span className="sub">막대=생산량 · 선=가동률</span></h2>
              <HourlyChart hourly={algoView.hourly} />
            </div>
            <div className="panel">
              <h2>Task별 계획달성률</h2>
              <TaskAchievement perTask={algoView.per_task} />
            </div>
          </div>

          <div className="panel">
            <h2>
              전환 예정 장비 정보
              <span className="sub">RTS_EQPCONVPLAN · {num(algoView.conversions.length)}건</span>
            </h2>
            <ConversionTable conversions={algoView.conversions} />
          </div>

          <div className="grid-2">
            <div className="panel">
              <h2>가이드 수량 <span className="sub">공정×모델 목표 대수 (Mode 1)</span></h2>
              <GuideTable guide={detail.guide} />
            </div>
            <div className="panel">
              <h2>
                장비 호기 명단
                <span className="sub">
                  {detail.equipments.length > 0
                    ? `입력 제공 ${detail.equipments.length}대`
                    : "입력 미제공 — 가상 호기 사용"}
                </span>
              </h2>
              {detail.equipments.length > 0 ? (
                <table className="data">
                  <thead>
                    <tr>
                      <th>EQP_ID</th><th>모델</th><th>BATCH_ID</th><th>PLAN_PROD_KEY</th><th>OPER</th>
                    </tr>
                  </thead>
                  <tbody>
                    {detail.equipments.map((e) => (
                      <tr key={e.eqp_id}>
                        <td><b>{e.eqp_id}</b></td>
                        <td>{e.eqp_model}</td>
                        <td>{e.batch_id}</td>
                        <td>{e.plan_prod_key}</td>
                        <td>{e.oper_id}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div className="empty">
                  입력 JSON/DB에 장비 호기 명단(EQP_ID)을 제공하면<br />
                  간트차트·전환계획이 실제 호기로 매핑됩니다.
                </div>
              )}
            </div>
          </div>

          {detail.optimal != null && (
            <div className="meta-line">
              최적해 기준 달성률: <b>{pct(detail.optimal)}</b> (벤치마크 ground truth)
            </div>
          )}
        </>
      )}
    </div>
  );
}
