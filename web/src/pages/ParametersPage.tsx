import { useEffect, useState } from "react";
import { fetchMlConfig, patchMlConfig } from "../api";
import type { MlConfig } from "../types";

type NumKey = keyof Pick<
  MlConfig,
  | "ppo_steps"
  | "bc_epochs"
  | "bc_lr"
  | "bc_loss_target"
  | "max_tasks"
  | "max_models"
  | "dwell_lambda"
  | "alloc_lambda"
  | "guide_util_threshold"
  | "guide_band_pct"
  | "horizon_hours"
  | "lookback_days"
>;

const FIELDS: { key: NumKey | "dwell_obs" | "use_alloc_model"; label: string; type: "number" | "bool" }[] = [
  { key: "ppo_steps", label: "PPO steps", type: "number" },
  { key: "bc_epochs", label: "BC epochs", type: "number" },
  { key: "bc_lr", label: "BC learning rate", type: "number" },
  { key: "bc_loss_target", label: "BC loss target", type: "number" },
  { key: "max_tasks", label: "Max tasks", type: "number" },
  { key: "max_models", label: "Max models", type: "number" },
  { key: "dwell_lambda", label: "Dwell shaping λ", type: "number" },
  { key: "alloc_lambda", label: "Alloc guide λ", type: "number" },
  { key: "guide_util_threshold", label: "Guide util threshold", type: "number" },
  { key: "guide_band_pct", label: "Guide band %", type: "number" },
  { key: "horizon_hours", label: "Horizon (hours)", type: "number" },
  { key: "lookback_days", label: "Train lookback (days)", type: "number" },
  { key: "dwell_obs", label: "Dwell observation", type: "bool" },
  { key: "use_alloc_model", label: "Use alloc model", type: "bool" },
];

export default function ParametersPage() {
  const [config, setConfig] = useState<MlConfig | null>(null);
  const [draft, setDraft] = useState<Partial<MlConfig>>({});
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchMlConfig()
      .then((c) => {
        setConfig(c);
        setDraft(c);
      })
      .catch((e) => setError(String(e)));
  }, []);

  const save = async () => {
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const updated = await patchMlConfig(draft);
      setConfig(updated);
      setDraft(updated);
      setSaved(true);
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  };

  if (!config) return <div className="empty">파라미터 불러오는 중…</div>;

  return (
    <div className="page">
      <header className="page-header">
        <h1>파라미터 설정</h1>
        <p className="page-sub">학습·환경 하이퍼파라미터 (저장 시 다음 Train 실행에 반영)</p>
      </header>

      {error && <div className="error">⚠ {error}</div>}
      {saved && <div className="success-banner">저장되었습니다.</div>}

      <div className="param-grid">
        {FIELDS.map((f) => (
          <label key={f.key} className="param-field">
            <span>{f.label}</span>
            {f.type === "bool" ? (
              <input
                type="checkbox"
                checked={Boolean(draft[f.key as keyof MlConfig])}
                onChange={(e) => setDraft((d) => ({ ...d, [f.key]: e.target.checked }))}
              />
            ) : (
              <input
                type="number"
                step="any"
                value={Number(draft[f.key as keyof MlConfig] ?? 0)}
                onChange={(e) =>
                  setDraft((d) => ({ ...d, [f.key]: Number(e.target.value) }))
                }
              />
            )}
          </label>
        ))}
      </div>

      <button type="button" className="ops-btn primary" disabled={saving} onClick={save}>
        {saving ? "저장 중…" : "파라미터 저장"}
      </button>

      <section className="panel-card" style={{ marginTop: 20 }}>
        <h2>경로</h2>
        <ul className="path-list">
          {Object.entries(config.paths).map(([k, v]) => (
            <li key={k}>
              <code>{k}</code> → <span>{v}</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
