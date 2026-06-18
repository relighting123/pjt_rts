import OpsPanel from "../components/OpsPanel";

export default function OpsPage() {
  return (
    <div className="page">
      <header className="page-header">
        <h1>운영 — Export / Infer</h1>
        <p className="page-sub">DB 연동 export · 추론 파이프라인 · 추론 결과 간트/KPI 시각화</p>
      </header>
      <OpsPanel focus="ops" />
    </div>
  );
}
