import { useEffect, useMemo, useState } from "react";
import { fetchDatasets, fetchDetail } from "../api";
import type { DatasetDetail, OpsJob } from "../types";
import AlgoComparePanel from "./AlgoComparePanel";

function datasetNameFromJob(job: OpsJob): string | null {
  const r = job.result;
  if (!r) return null;
  const path = r.input_json;
  if (typeof path === "string") {
    const base = path.split(/[/\\]/).pop();
    if (base?.endsWith(".json")) return base.slice(0, -5);
  }
  const rk = r.rule_timekey;
  const fac = r.facid;
  if (typeof rk === "string" && rk) {
    if (typeof fac === "string" && fac) return `${rk}_${fac}`;
    return rk;
  }
  return null;
}

interface Props {
  /** infer 작업 완료 시 자동 선택용 */
  jobs?: OpsJob[];
}

/** 추론 입력 JSON 기준 간트차트·KPI 시각화. */
export default function InferResultPanel({ jobs = [] }: Props) {
  const [names, setNames] = useState<string[]>([]);
  const [selected, setSelected] = useState("");
  const [detail, setDetail] = useState<DatasetDetail | null>(null);
  const [loadingList, setLoadingList] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastInferPolicy, setLastInferPolicy] = useState<string | null>(null);

  const loadList = () => {
    setLoadingList(true);
    fetchDatasets()
      .then((rows) => {
        const infer = rows.filter((d) => d.kind === "inference").map((d) => d.name);
        setNames(infer);
        setSelected((prev) => (prev && infer.includes(prev) ? prev : infer[0] ?? ""));
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoadingList(false));
  };

  useEffect(() => {
    loadList();
  }, []);

  const latestDoneInfer = useMemo(
    () => jobs.find((j) => j.kind === "infer" && j.status === "done"),
    [jobs],
  );

  useEffect(() => {
    if (!latestDoneInfer) return;
    const key = datasetNameFromJob(latestDoneInfer);
    if (key) {
      setSelected(key);
      loadList();
      const policy = latestDoneInfer.result?.policy;
      if (typeof policy === "string") setLastInferPolicy(policy);
    }
  }, [latestDoneInfer?.id, latestDoneInfer?.status, latestDoneInfer?.finished_at]);

  useEffect(() => {
    if (!selected) {
      setDetail(null);
      return;
    }
    setLoadingDetail(true);
    setError(null);
    fetchDetail(selected, "dispatch")
      .then(setDetail)
      .catch((e) => setError(String(e)))
      .finally(() => setLoadingDetail(false));
  }, [selected]);

  const rlAvailable = detail?.rl_status.available ?? false;
  const activePolicy = lastInferPolicy ?? (rlAvailable ? "RL" : "HEURISTIC");

  return (
    <section className="infer-result-panel panel-card">
      <div className="infer-result-head">
        <div>
          <h2>추론 결과 — 간트차트 & KPI</h2>
          <p className="panel-sub">
            Infer 실행 후 data/raw/inference/ 입력 JSON 기준으로 dispatch 시뮬 결과를 표시합니다.
            {lastInferPolicy && (
              <> 최근 추론 정책: <b>{activePolicy}</b></>
            )}
          </p>
        </div>
        <button type="button" className="ops-btn small" onClick={loadList} disabled={loadingList}>
          새로고침
        </button>
      </div>

      {error && <div className="error">⚠ {error}</div>}
      {loadingList && <div className="empty">추론 데이터 목록 불러오는 중…</div>}

      {!loadingList && names.length === 0 && (
        <div className="empty">
          추론 입력 JSON이 없습니다. Infer를 실행하거나 Export로 data/raw/inference/에 JSON을 생성하세요.
        </div>
      )}

      {names.length > 0 && (
        <div className="infer-result-chips">
          {names.map((n) => (
            <button
              key={n}
              type="button"
              className={`bench-chip${selected === n ? " active" : ""}`}
              onClick={() => setSelected(n)}
            >
              {n}
            </button>
          ))}
        </div>
      )}

      {selected && loadingDetail && <div className="empty">결과 불러오는 중…</div>}

      {selected && !loadingDetail && detail && (
        <>
          <div className="meta-line">
            <b>{detail.name}</b>
            {" · "}RULE_TIMEKEY <b>{detail.meta.rule_timekey}</b>
            {" · "}Horizon <b>{detail.meta.horizon_hours}h</b>
            {detail.meta.facid && (
              <> · FAC <b>{detail.meta.facid}</b></>
            )}
          </div>
          <AlgoComparePanel detail={detail} envType="dispatch" rlAvailable={rlAvailable} />
        </>
      )}
    </section>
  );
}
