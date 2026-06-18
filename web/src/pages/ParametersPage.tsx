import { useEffect, useState } from "react";
import { fetchMlConfig, patchMlConfig } from "../api";
import type { MlConfig } from "../types";

type PatchKey = keyof Pick<
  MlConfig,
  | "ppo_steps"
  | "bc_epochs"
  | "bc_lr"
  | "bc_loss_target"
  | "dwell_lambda"
  | "alloc_lambda"
  | "guide_util_threshold"
  | "guide_band_pct"
  | "horizon_hours"
  | "lookback_days"
>;

const PATCH_FIELDS: {
  key: PatchKey | "dwell_obs" | "use_alloc_model";
  label: string;
  type: "number" | "bool";
}[] = [
  { key: "ppo_steps", label: "PPO steps", type: "number" },
  { key: "bc_epochs", label: "BC epochs", type: "number" },
  { key: "bc_lr", label: "BC learning rate", type: "number" },
  { key: "bc_loss_target", label: "BC loss target", type: "number" },
  { key: "dwell_lambda", label: "Dwell shaping λ", type: "number" },
  { key: "alloc_lambda", label: "Alloc guide λ", type: "number" },
  { key: "guide_util_threshold", label: "Guide util threshold", type: "number" },
  { key: "guide_band_pct", label: "Guide band %", type: "number" },
  { key: "horizon_hours", label: "Horizon (hours)", type: "number" },
  { key: "lookback_days", label: "Train lookback (days)", type: "number" },
  { key: "dwell_obs", label: "Dwell observation", type: "bool" },
  { key: "use_alloc_model", label: "Use alloc model", type: "bool" },
];

const ENV_FIELDS: { key: keyof MlConfig; label: string; env: string }[] = [
  { key: "max_tasks", label: "Max tasks (모델 obs 패딩)", env: "MAX_TASKS" },
  { key: "max_models", label: "Max models (모델 obs 패딩)", env: "MAX_MODELS" },
  { key: "metric_digits", label: "KPI 표시 소수 자릿수", env: "UI_METRIC_DIGITS" },
];

export default function ParametersPage() {
  const [config, setConfig] = useState<MlConfig | null>(null);
  const [draft, setDraft] = useState<Partial<MlConfig>>({});
  const [convGroupsJson, setConvGroupsJson] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchMlConfig()
      .then((c) => {
        setConfig(c);
        setDraft(c);
        setConvGroupsJson(JSON.stringify(c.conv_groups, null, 2));
      })
      .catch((e) => setError(String(e)));
  }, []);

  const parseConvGroups = (): Record<string, string[]> => {
    try {
      const parsed = JSON.parse(convGroupsJson) as Record<string, string[]>;
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        throw new Error("conv_groups는 객체여야 합니다.");
      }
      return parsed;
    } catch {
      throw new Error("전환 그룹(conv_groups) JSON 형식이 올바르지 않습니다.");
    }
  };

  const save = async () => {
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const payload: Partial<MlConfig> = {};
      for (const f of PATCH_FIELDS) {
        const v = draft[f.key as keyof MlConfig];
        if (v !== undefined) (payload as Record<string, unknown>)[f.key] = v;
      }
      payload.conv_groups = parseConvGroups();
      const updated = await patchMlConfig(payload);
      setConfig(updated);
      setDraft(updated);
      setConvGroupsJson(JSON.stringify(updated.conv_groups, null, 2));
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
        <p className="page-sub">
          학습 하이퍼파라미터는 대시보드에서 저장 · 모델 크기/표시 정밀도는 <code>.env</code>에서 설정
        </p>
      </header>

      {error && <div className="error">⚠ {error}</div>}
      {saved && <div className="success-banner">저장되었습니다.</div>}

      <section className="panel-card">
        <h2>.env 전용 (읽기 전용)</h2>
        <p className="panel-sub">팀원마다 다른 값을 써도 git 충돌 없음 — 변경 후 uvicorn 재시작</p>
        <div className="env-readonly-grid">
          {ENV_FIELDS.map((f) => (
            <div key={f.env} className="env-readonly-field">
              <span className="label">{f.label}</span>
              <code className="env-var">{f.env}</code>
              <span className="value">{String(config[f.key] ?? "")}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="panel-card">
        <h2>런타임 파라미터</h2>
        <p className="panel-sub">저장 시 models/runtime_config.json (gitignore)</p>
        <div className="param-grid">
          {PATCH_FIELDS.map((f) => (
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
          {saving ? "저장 중…" : "런타임 파라미터 저장"}
        </button>
      </section>

      <section className="panel-card">
        <h2>전환 그룹 (conv_groups)</h2>
        <p className="panel-sub">
          동일 그룹 내 BATCH_ID는 설비 전환 시간이 공유됩니다. 학습·추론 시 이 설정이 적용됩니다.
        </p>
        <label className="param-field conv-groups-field">
          <span>그룹 → BATCH_ID 목록 (JSON)</span>
          <textarea
            className="ops-textarea"
            rows={6}
            value={convGroupsJson}
            onChange={(e) => setConvGroupsJson(e.target.value)}
            spellCheck={false}
          />
        </label>
        <button type="button" className="ops-btn primary" disabled={saving} onClick={save}>
          {saving ? "저장 중…" : "전환 그룹 저장"}
        </button>
      </section>

      <section className="panel-card">
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
