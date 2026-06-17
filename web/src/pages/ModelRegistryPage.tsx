import { useEffect, useState } from "react";
import {
  fetchMlModels,
  postMlActivate,
  postMlRegister,
} from "../api";
import type { ModelInfo } from "../types";

export default function ModelRegistryPage() {
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [name, setName] = useState("");
  const [notes, setNotes] = useState("");
  const [sourcePath, setSourcePath] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const reload = () =>
    fetchMlModels()
      .then((r) => setModels(r.models))
      .catch((e) => setError(String(e)));

  useEffect(() => {
    reload();
  }, []);

  const register = async () => {
    setBusy(true);
    setError(null);
    setSuccess(null);
    try {
      const r = await postMlRegister({
        name: name.trim() || undefined,
        notes: notes.trim(),
        source_path: sourcePath.trim() || undefined,
      });
      setSuccess(`등록 완료: ${r.model.name} (활성 모델로 설정됨)`);
      setName("");
      setNotes("");
      await reload();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const activate = async (id: string) => {
    setBusy(true);
    setError(null);
    try {
      await postMlActivate(id);
      setSuccess("활성 모델이 변경되었습니다.");
      await reload();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const registered = models.filter((m) => m.registered);
  const checkpoints = models.filter((m) => !m.registered);

  return (
    <div className="page">
      <header className="page-header">
        <h1>최종 모델 등록</h1>
        <p className="page-sub">
          검증·테스트 통과 모델을 production(best/)에 등록하고 추론용 활성 모델로 설정
        </p>
      </header>

      {error && <div className="error">⚠ {error}</div>}
      {success && <div className="success-banner">{success}</div>}

      <section className="panel-card">
        <h2>새 모델 등록</h2>
        <p className="panel-sub">
          source 비우면 현재 체크포인트(models/checkpoints/ppo_dispatch.zip)를 등록합니다.
        </p>
        <div className="ops-field-row">
          <label>모델 이름</label>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="예: v2-dwell-0.3" />
        </div>
        <div className="ops-field-row">
          <label>소스 경로 (선택)</label>
          <input
            value={sourcePath}
            onChange={(e) => setSourcePath(e.target.value)}
            placeholder="비우면 현재 체크포인트"
          />
        </div>
        <div className="ops-field-row">
          <label>메모</label>
          <input value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="검증 결과 요약 등" />
        </div>
        <button type="button" className="ops-btn primary" disabled={busy} onClick={register}>
          {busy ? "등록 중…" : "최종 모델 등록"}
        </button>
      </section>

      <div className="ml-grid-2">
        <section className="panel-card">
          <h2>등록된 Production 모델</h2>
          {registered.length === 0 && <div className="empty">등록된 모델 없음</div>}
          <ul className="model-registry-list">
            {registered.map((m) => (
              <li key={m.id} className={m.is_active ? "active-model" : ""}>
                <div className="model-registry-head">
                  <b>{m.name}</b>
                  {m.is_active && <span className="badge real">활성</span>}
                </div>
                <div className="sub">{m.path}</div>
                {m.final_training_reward != null && (
                  <div className="sub">학습 reward: {m.final_training_reward.toFixed(4)}</div>
                )}
                {!m.is_active && (
                  <button type="button" className="ops-btn small" disabled={busy} onClick={() => activate(m.id)}>
                    활성화
                  </button>
                )}
              </li>
            ))}
          </ul>
        </section>

        <section className="panel-card">
          <h2>체크포인트</h2>
          {checkpoints.length === 0 && <div className="empty">체크포인트 없음</div>}
          <ul className="model-registry-list">
            {checkpoints.map((m) => (
              <li key={m.id}>
                <div className="model-registry-head">
                  <b>{m.name}</b>
                  {m.is_active && <span className="badge real">활성</span>}
                </div>
                <div className="sub">{m.modified_at}</div>
                <button type="button" className="ops-btn small" disabled={busy} onClick={() => activate(m.id)}>
                  활성화
                </button>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}
