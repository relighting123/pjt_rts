import type { DatasetDetail, DatasetInfo, Summary, TrainingMetrics } from "./types";

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${url} → HTTP ${res.status}`);
  return res.json() as Promise<T>;
}

export const fetchDatasets = () => getJson<DatasetInfo[]>("/api/datasets");
export const fetchDetail = (name: string, envType = "dispatch") =>
  getJson<DatasetDetail>(`/api/datasets/${encodeURIComponent(name)}?env_type=${envType}`);
export const fetchSummary = (envType = "dispatch") =>
  getJson<Summary>(`/api/summary?env_type=${envType}`);
export const fetchTrainingMetrics = (stage: "dispatch" | "alloc" = "dispatch") =>
  getJson<TrainingMetrics>(`/api/training/metrics?stage=${stage}`);

export const pct = (v: number | null | undefined, digits = 1) =>
  v == null ? "N/A" : `${(v * 100).toFixed(digits)}%`;

/** ground_truth 최적해가 100%면 비교 가치가 없어 UI에서 숨김. */
export const isMeaningfulOptimal = (v: number | null | undefined) =>
  v != null && v < 0.9999;

export const num = (v: number | null | undefined) =>
  v == null ? "N/A" : v.toLocaleString();

// task 키 → 고정 색상 팔레트
const PALETTE = [
  "#5B8FF9", "#5AD8A6", "#F6BD16", "#E8684A", "#6DC8EC",
  "#9270CA", "#FF9D4D", "#269A99", "#FF99C3", "#BDD2FD",
];

export function colorScale(keys: string[]): (k: string) => string {
  const sorted = [...new Set(keys)].sort();
  const map = new Map(sorted.map((k, i) => [k, PALETTE[i % PALETTE.length]]));
  return (k: string) => map.get(k) ?? "#888";
}

export const fmtTime = (iso: string) => {
  const d = new Date(iso);
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  const hh = String(d.getHours()).padStart(2, "0");
  const mi = String(d.getMinutes()).padStart(2, "0");
  return `${mm}/${dd} ${hh}:${mi}`;
};

export const fmtTm12 = (tm: string) => {
  // "202605292350" → "05/29 23:50"
  if (tm.length < 12) return tm;
  return `${tm.slice(4, 6)}/${tm.slice(6, 8)} ${tm.slice(8, 10)}:${tm.slice(10, 12)}`;
};
