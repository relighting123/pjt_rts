import OpsPanel from "../components/OpsPanel";
import ConvergenceChart from "../components/ConvergenceChart";

export default function TrainingPage() {
  return (
    <div className="page">
      <header className="page-header">
        <h1>학습</h1>
        <p className="page-sub">PPO 학습 실행 및 수렴 모니터링</p>
      </header>

      <section className="panel-card">
        <h2>학습 수렴 (Dispatch)</h2>
        <ConvergenceChart stage="dispatch" />
      </section>

      <section className="panel-card">
        <h2>학습 수렴 (Alloc)</h2>
        <ConvergenceChart stage="alloc" />
      </section>

      <OpsPanel focus="train" />
    </div>
  );
}
