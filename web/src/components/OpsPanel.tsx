import { useCallback, useEffect, useState } from "react";
import {
  fetchOpsJobs,
  fetchOpsLogs,
  fetchOpsStatus,
  fetchTrainingMetrics,
  postOpsExport,
  postOpsInfer,
  postOpsTrain,
} from "../api";
import type { OpsJob, OpsLogEntry, OpsStatus, TrainingMetrics } from "../types";
import ConvergenceChart from "./ConvergenceChart";

type RangeMode = "lookback" | "explicit";

const empty = (v: string | null | undefined) => v ?? "";

export default function OpsPanel() {
  const [status, setStatus] = useState<OpsStatus | null>(null);
  const [jobs, setJobs] = useState<OpsJob[]>([]);
  const [logs, setLogs] = useState<OpsLogEntry[]>([]);
  const [trainMetrics, setTrainMetrics] = useState<TrainingMetrics | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState<string | null>(null);

  const [facid, setFacid] = useState("");
  const [batchid, setBatchid] = useState("");
  const [horizon, setHorizon] = useState("12");

  const [exportMode, setExportMode] = useState<"single" | "train_range">("single");
  const [exportTimekey, setExportTimekey] = useState("");
  const [exportRangeMode, setExportRangeMode] = useState<RangeMode>("lookback");
  const [exportFrom, setExportFrom] = useState("");
  const [exportTo, setExportTo] = useState("");
  const [exportLookback, setExportLookback] = useState("30");

  const [inferTimekey, setInferTimekey] = useState("");
  const [inferSkipExport, setInferSkipExport] = useState(false);
  const [inferWriteDb, setInferWriteDb] = useState(true);

  const [trainMode, setTrainMode] = useState<"local" | "db_range">("local");
  const [trainRangeMode, setTrainRangeMode] = useState<RangeMode>("lookback");
  const [trainFrom, setTrainFrom] = useState("");
  const [trainTo, setTrainTo] = useState("");
  const [trainLookback, setTrainLookback] = useState("30");
  const [trainSteps, setTrainSteps] = useState("50000");

  const refresh = useCallback(async () => {
    try {
      const [st, jb, lg, tm] = await Promise.all([
        fetchOpsStatus(),
        fetchOpsJobs(),
        fetchOpsLogs(),
        fetchTrainingMetrics("dispatch"),
      ]);
      setStatus(st);
      setJobs(jb.jobs);
      setLogs(lg.logs);
      setTrainMetrics(tm);
    } catch (e) {
      setError(String(e));
    }
  }, []);

  useEffect(() => {
    fetchOpsStatus()
      .then((st) => {
        if (st.defaults.facid) setFacid((v) => v || st.defaults.facid || "");
        if (st.defaults.batchid) setBatchid((v) => v || st.defaults.batchid || "");
        setExportLookback(String(st.defaults.lookback_days));
        setTrainLookback(String(st.defaults.lookback_days));
        setTrainSteps(String(st.defaults.default_ppo_steps));
      })
      .catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    refresh();
    const id = window.setInterval(refresh, 4000);
    return () => window.clearInterval(id);
  }, [refresh]);

  const baseParams = () => ({
    facid: facid.trim() || null,
    batchid: batchid.trim() || null,
    horizon_hours: Number(horizon) || 12,
  });

  const rangeParams = (mode: RangeMode, from: string, to: string, lookback: string) =>
    mode === "explicit"
      ? { from_timekey: from.trim() || null, to_timekey: to.trim() || null }
      : { lookback_days: Number(lookback) || 30, from_timekey: null, to_timekey: null };

  const runAction = async (label: string, fn: () => Promise<{ job_id: string }>) => {
    setError(null);
    setSubmitting(label);
    try {
      await fn();
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setSubmitting(null);
    }
  };

  const busy = status?.busy ?? false;

  return (
    <div className="ops-panel">
      {error && <div className="error">⚠ {error}</div>}

      {status && (
        <section className="ops-status-grid">
          <div className="kpi-card">
            <div className="label">Dispatch 모델</div>
            <div className={`value ${status.artifacts.dispatch_model_exists ? "good-text" : ""}`}>
              {status.artifacts.dispatch_model_exists ? "있음" : "없음"}
            </div>
            <div className="sub">{status.artifacts.dispatch_model}</div>
          </div>
          <div className="kpi-card">
            <div className="label">학습 JSON / 추론 입력</div>
            <div className="value">{status.artifacts.train_json_count}</div>
            <div className="sub">
              train · inference {status.artifacts.inference_input_count} · result{" "}
              {status.artifacts.inference_result_count}
            </div>
          </div>
          <div className="kpi-card">
            <div className="label">작업 상태</div>
            <div className={`value ${busy ? "warn-text" : "good-text"}`}>
              {busy ? "실행 중" : "대기"}
            </div>
            <div className="sub">
              {status.running_job
                ? `${status.running_job.kind} (${status.running_job.id})`
                : "동시 1건 실행"}
            </div>
          </div>
        </section>
      )}

      <div className="ops-grid">
        <section className="ops-forms">
          <div className="ops-form-card">
            <h2>Export — DB → JSON</h2>
            <p className="panel-sub">단건은 추론 입력, 범위는 학습용 data/raw/train/</p>
            <div className="ops-field-row">
              <label>FAC_ID</label>
              <input value={facid} onChange={(e) => setFacid(e.target.value)} placeholder="ICPRB" />
            </div>
            <div className="ops-field-row">
              <label>BATCH_ID</label>
              <input value={batchid} onChange={(e) => setBatchid(e.target.value)} placeholder="B1" />
            </div>
            <div className="ops-field-row">
              <label>Horizon (h)</label>
              <input type="number" min={1} value={horizon} onChange={(e) => setHorizon(e.target.value)} />
            </div>
            <div className="ops-seg">
              <button
                type="button"
                className={exportMode === "single" ? "active" : ""}
                onClick={() => setExportMode("single")}
              >
                단건
              </button>
              <button
                type="button"
                className={exportMode === "train_range" ? "active" : ""}
                onClick={() => setExportMode("train_range")}
              >
                학습 범위
              </button>
            </div>
            {exportMode === "single" ? (
              <div className="ops-field-row">
                <label>RULE_TIMEKEY</label>
                <input
                  value={exportTimekey}
                  onChange={(e) => setExportTimekey(e.target.value)}
                  placeholder="비우면 MAX(timekey)"
                />
              </div>
            ) : (
              <>
                <div className="ops-seg small">
                  <button
                    type="button"
                    className={exportRangeMode === "lookback" ? "active" : ""}
                    onClick={() => setExportRangeMode("lookback")}
                  >
                    lookback
                  </button>
                  <button
                    type="button"
                    className={exportRangeMode === "explicit" ? "active" : ""}
                    onClick={() => setExportRangeMode("explicit")}
                  >
                    from ~ to
                  </button>
                </div>
                {exportRangeMode === "lookback" ? (
                  <div className="ops-field-row">
                    <label>Lookback (days)</label>
                    <input
                      type="number"
                      min={1}
                      value={exportLookback}
                      onChange={(e) => setExportLookback(e.target.value)}
                    />
                  </div>
                ) : (
                  <>
                    <div className="ops-field-row">
                      <label>FROM</label>
                      <input value={exportFrom} onChange={(e) => setExportFrom(e.target.value)} />
                    </div>
                    <div className="ops-field-row">
                      <label>TO</label>
                      <input value={exportTo} onChange={(e) => setExportTo(e.target.value)} />
                    </div>
                  </>
                )}
              </>
            )}
            <button
              type="button"
              className="ops-btn primary"
              disabled={busy || submitting === "export"}
              onClick={() =>
                runAction("export", () =>
                  postOpsExport({
                    mode: exportMode,
                    timekey: exportTimekey.trim() || null,
                    ...baseParams(),
                    ...rangeParams(exportRangeMode, exportFrom, exportTo, exportLookback),
                    sample: false,
                  }),
                )
              }
            >
              {submitting === "export" ? "요청 중…" : "Export 실행"}
            </button>
          </div>

          <div className="ops-form-card">
            <h2>Infer — 추론</h2>
            <p className="panel-sub">DB export → RL/휴리스틱 평가 → result JSON → (선택) DB write</p>
            <div className="ops-field-row">
              <label>RULE_TIMEKEY</label>
              <input
                value={inferTimekey}
                onChange={(e) => setInferTimekey(e.target.value)}
                placeholder="비우면 최신"
              />
            </div>
            <label className="ops-check">
              <input
                type="checkbox"
                checked={inferSkipExport}
                onChange={(e) => setInferSkipExport(e.target.checked)}
              />
              기존 입력 JSON 사용 (skip export)
            </label>
            <label className="ops-check">
              <input
                type="checkbox"
                checked={inferWriteDb}
                onChange={(e) => setInferWriteDb(e.target.checked)}
              />
              결과 DB 기록
            </label>
            <button
              type="button"
              className="ops-btn primary"
              disabled={busy || submitting === "infer"}
              onClick={() =>
                runAction("infer", () =>
                  postOpsInfer({
                    timekey: inferTimekey.trim() || null,
                    ...baseParams(),
                    skip_input_export: inferSkipExport,
                    write_db: inferWriteDb,
                  }),
                )
              }
            >
              {submitting === "infer" ? "요청 중…" : "Infer 실행"}
            </button>
          </div>

          <div className="ops-form-card">
            <h2>Train — 학습</h2>
            <p className="panel-sub">data/raw/train/ JSON으로 PPO 학습 (선택: DB 범위 export 선행)</p>
            <div className="ops-seg">
              <button
                type="button"
                className={trainMode === "local" ? "active" : ""}
                onClick={() => setTrainMode("local")}
              >
                기존 JSON
              </button>
              <button
                type="button"
                className={trainMode === "db_range" ? "active" : ""}
                onClick={() => setTrainMode("db_range")}
              >
                DB 범위 export + 학습
              </button>
            </div>
            {trainMode === "db_range" && (
              <>
                <div className="ops-seg small">
                  <button
                    type="button"
                    className={trainRangeMode === "lookback" ? "active" : ""}
                    onClick={() => setTrainRangeMode("lookback")}
                  >
                    lookback
                  </button>
                  <button
                    type="button"
                    className={trainRangeMode === "explicit" ? "active" : ""}
                    onClick={() => setTrainRangeMode("explicit")}
                  >
                    from ~ to
                  </button>
                </div>
                {trainRangeMode === "lookback" ? (
                  <div className="ops-field-row">
                    <label>Lookback (days)</label>
                    <input
                      type="number"
                      min={1}
                      value={trainLookback}
                      onChange={(e) => setTrainLookback(e.target.value)}
                    />
                  </div>
                ) : (
                  <>
                    <div className="ops-field-row">
                      <label>FROM</label>
                      <input value={trainFrom} onChange={(e) => setTrainFrom(e.target.value)} />
                    </div>
                    <div className="ops-field-row">
                      <label>TO</label>
                      <input value={trainTo} onChange={(e) => setTrainTo(e.target.value)} />
                    </div>
                  </>
                )}
              </>
            )}
            <div className="ops-field-row">
              <label>PPO steps</label>
              <input type="number" min={100} value={trainSteps} onChange={(e) => setTrainSteps(e.target.value)} />
            </div>
            <button
              type="button"
              className="ops-btn primary"
              disabled={busy || submitting === "train"}
              onClick={() =>
                runAction("train", () =>
                  postOpsTrain({
                    mode: trainMode,
                    ...baseParams(),
                    ...rangeParams(trainRangeMode, trainFrom, trainTo, trainLookback),
                    steps: Number(trainSteps) || 50000,
                  }),
                )
              }
            >
              {submitting === "train" ? "요청 중…" : "Train 실행"}
            </button>
          </div>
        </section>

        <section className="ops-side">
          <div className="ops-form-card">
            <h2>작업 이력</h2>
            {jobs.length === 0 && <div className="empty">아직 작업 없음</div>}
            <ul className="ops-job-list">
              {jobs.map((j) => (
                <li key={j.id} className={`ops-job status-${j.status}`}>
                  <div className="ops-job-head">
                    <span className="kind">{j.kind}</span>
                    <span className={`badge-status ${j.status}`}>{j.status}</span>
                  </div>
                  <div className="ops-job-meta">{j.id} · {j.created_at}</div>
                  {j.result && (
                    <pre className="ops-job-result">{JSON.stringify(j.result, null, 2)}</pre>
                  )}
                  {j.error && <div className="ops-job-error">{j.error}</div>}
                </li>
              ))}
            </ul>
          </div>

          <div className="ops-form-card">
            <h2>Ops 로그</h2>
            <div className="ops-log-wrap">
              {logs.length === 0 && <div className="empty">ops.jsonl 비어 있음</div>}
              {logs
                .slice()
                .reverse()
                .map((row, i) => (
                  <div key={`${row.ts}-${i}`} className="ops-log-line">
                    <span className="ts">{empty(row.ts)}</span>
                    <span className="ev">{empty(row.event)}</span>
                    <span className="msg">
                      {Object.entries(row)
                        .filter(([k]) => k !== "ts" && k !== "event")
                        .map(([k, v]) => `${k}=${v}`)
                        .join(" ")}
                    </span>
                  </div>
                ))}
            </div>
          </div>

          <div className="ops-form-card">
            <h2>학습 수렴 (실시간)</h2>
            <p className="panel-sub">
              포인트 {trainMetrics?.points.length ?? 0} · Train 실행 중 자동 갱신
            </p>
            <ConvergenceChart stage="dispatch" />
          </div>
        </section>
      </div>
    </div>
  );
}
