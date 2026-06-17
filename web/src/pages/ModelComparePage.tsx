import { useEffect, useState } from "react";
import { fetchMlModels, postMlCompare } from "../api";
import { pct } from "../api";
import type { ModelCompareRow, ModelInfo } from "../types";

export default function ModelComparePage() {
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [split, setSplit] = useState<"validation" | "test">("test");
  const [results, setResults] = useState<ModelCompareRow[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchMlModels()
      .then((r) => setModels(r.models))
      .catch((e) => setError(String(e)));
  }, []);

  const toggle = (id: string) => {
    setSelected((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id].slice(0, 5),
    );
  };

  const compare = async () => {
    if (selected.length < 1) return;
    setLoading(true);
    setError(null);
    try {
      const r = await postMlCompare({ model_ids: selected, split, env_type: "dispatch" });
      setResults(r.models);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <header className="page-header">
        <h1>모델 비교 분석</h1>
        <p className="page-sub">체크포인트·등록 모델 간 KPI / Reward 비교 (최대 5개)</p>
      </header>

      {error && <div className="error">⚠ {error}</div>}

      <section className="panel-card">
        <h2>비교 대상 선택</h2>
        <div className="seg small" style={{ marginBottom: 12 }}>
          <button
            type="button"
            className={split === "validation" ? "active" : ""}
            onClick={() => setSplit("validation")}
          >
            Validation
          </button>
          <button
            type="button"
            className={split === "test" ? "active" : ""}
            onClick={() => setSplit("test")}
          >
            Test
          </button>
        </div>
        <ul className="model-pick-list">
          {models.length === 0 && <li className="empty">모델 없음 — 학습 후 체크포인트가 생성됩니다.</li>}
          {models.map((m) => (
            <li key={m.id}>
              <label className="ops-check">
                <input
                  type="checkbox"
                  checked={selected.includes(m.id)}
                  onChange={() => toggle(m.id)}
                />
                <span>
                  <b>{m.name}</b>
                  {m.is_active && <span className="badge real">활성</span>}
                  {m.registered && <span className="badge virtual">등록</span>}
                  <span className="sub"> {m.filename}</span>
                </span>
              </label>
            </li>
          ))}
        </ul>
        <button
          type="button"
          className="ops-btn primary"
          disabled={loading || selected.length === 0}
          onClick={compare}
        >
          {loading ? "비교 중…" : "비교 실행"}
        </button>
      </section>

      {results && (
        <section className="panel-card">
          <h2>비교 결과 — {split}</h2>
          <div className="table-wrap">
            <table className="ml-table">
              <thead>
                <tr>
                  <th>모델</th>
                  <th>RL 달성률</th>
                  <th>RL 가동률</th>
                  <th>RL Reward</th>
                  <th>휴리스틱</th>
                  <th>Optimal</th>
                </tr>
              </thead>
              <tbody>
                {results.map((r) => (
                  <tr key={r.model_id}>
                    <td>
                      {r.error ? (
                        <span className="warn-text">{r.error}</span>
                      ) : (
                        <>
                          <b>{r.name}</b>
                          {r.is_active && <span className="badge real">활성</span>}
                        </>
                      )}
                    </td>
                    <td>{pct(r.averages?.rl_plan_achievement)}</td>
                    <td>{pct(r.averages?.rl_utilization)}</td>
                    <td>{r.averages?.rl_episode_reward?.toFixed(4) ?? "—"}</td>
                    <td>{pct(r.averages?.heuristic_plan_achievement)}</td>
                    <td>{pct(r.averages?.optimal)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
