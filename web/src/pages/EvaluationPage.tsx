import { useCallback, useEffect, useState } from "react";
import { fetchMlEvaluate } from "../api";
import { pct } from "../api";
import type { EvalResult } from "../types";

export default function EvaluationPage() {
  const [validation, setValidation] = useState<EvalResult | null>(null);
  const [test, setTest] = useState<EvalResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [envType, setEnvType] = useState<"dispatch" | "alloc">("dispatch");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [v, t] = await Promise.all([
        fetchMlEvaluate("validation", undefined, envType),
        fetchMlEvaluate("test", undefined, envType),
      ]);
      setValidation(v);
      setTest(t);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [envType]);

  useEffect(() => {
    load();
  }, [load]);

  const renderTable = (data: EvalResult | null, title: string) => (
    <section className="panel-card">
      <h2>{title}</h2>
      <p className="panel-sub">
        {data?.count ?? 0}건 · 모델 {data?.model_loaded ? "로드됨" : "없음 (휴리스틱만)"}
      </p>
      {data && (
        <>
          <div className="eval-summary-row">
            <div className="kpi-card compact">
              <div className="label">RL 계획달성률 (평균)</div>
              <div className="value">{pct(data.averages.rl_plan_achievement)}</div>
            </div>
            <div className="kpi-card compact">
              <div className="label">RL Reward (평균)</div>
              <div className="value">
                {data.averages.rl_episode_reward?.toFixed(4) ?? "N/A"}
              </div>
            </div>
            <div className="kpi-card compact">
              <div className="label">휴리스틱 달성률</div>
              <div className="value">{pct(data.averages.heuristic_plan_achievement)}</div>
            </div>
          </div>
          <div className="table-wrap">
            <table className="ml-table">
              <thead>
                <tr>
                  <th>데이터셋</th>
                  <th>Optimal</th>
                  <th>휴리스틱</th>
                  <th>RL KPI</th>
                  <th>RL Reward</th>
                </tr>
              </thead>
              <tbody>
                {data.rows.map((r) => (
                  <tr key={r.dataset}>
                    <td>{r.dataset}</td>
                    <td>{pct(r.optimal)}</td>
                    <td>{pct(r.heuristic?.plan_achievement)}</td>
                    <td>{pct(r.rl?.plan_achievement)}</td>
                    <td>{r.rl_episode_reward?.toFixed(4) ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );

  return (
    <div className="page">
      <header className="page-header row">
        <div>
          <h1>검증·테스트 평가</h1>
          <p className="page-sub">Validation(train) vs Test 벤치마크 — Reward 및 실제 KPI 비교</p>
        </div>
        <div className="seg">
          <button
            type="button"
            className={envType === "dispatch" ? "active" : ""}
            onClick={() => setEnvType("dispatch")}
          >
            Dispatch
          </button>
          <button
            type="button"
            className={envType === "alloc" ? "active" : ""}
            onClick={() => setEnvType("alloc")}
          >
            Alloc
          </button>
        </div>
      </header>

      {error && <div className="error">⚠ {error}</div>}
      <button type="button" className="ops-btn" disabled={loading} onClick={load}>
        {loading ? "평가 중…" : "재평가"}
      </button>

      <div className="ml-grid-2" style={{ marginTop: 16 }}>
        {renderTable(validation, "검증 셋 (Validation — train JSON)")}
        {renderTable(test, "테스트 셋 (Test — benchmark JSON)")}
      </div>
    </div>
  );
}
