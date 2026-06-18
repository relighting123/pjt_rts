import { useEffect, useState } from "react";
import Sidebar from "./components/Sidebar";
import type { PageId } from "./navigation";
import { fetchMlConfig } from "./api";
import PipelineOverviewPage from "./pages/PipelineOverviewPage";
import ParametersPage from "./pages/ParametersPage";
import TrainingPage from "./pages/TrainingPage";
import EvaluationPage from "./pages/EvaluationPage";
import ModelComparePage from "./pages/ModelComparePage";
import ModelRegistryPage from "./pages/ModelRegistryPage";
import OpsPage from "./pages/OpsPage";
import BenchmarkPage from "./pages/BenchmarkPage";
import "./styles.css";

const SIDEBAR_KEY = "rts-sidebar-hidden";

function PageContent({ page }: { page: PageId }) {
  switch (page) {
    case "pipeline":
      return <PipelineOverviewPage />;
    case "parameters":
      return <ParametersPage />;
    case "training":
      return <TrainingPage />;
    case "evaluation":
      return <EvaluationPage />;
    case "compare":
      return <ModelComparePage />;
    case "registry":
      return <ModelRegistryPage />;
    case "ops":
      return <OpsPage />;
    case "benchmarks":
      return <BenchmarkPage />;
    default:
      return <PipelineOverviewPage />;
  }
}

export default function App() {
  const [page, setPage] = useState<PageId>("pipeline");
  const [sidebarHidden, setSidebarHidden] = useState(
    () => localStorage.getItem(SIDEBAR_KEY) === "1",
  );

  useEffect(() => {
    fetchMlConfig().catch(() => {
      /* UI_METRIC_DIGITS 기본값 사용 */
    });
  }, []);

  useEffect(() => {
    localStorage.setItem(SIDEBAR_KEY, sidebarHidden ? "1" : "0");
  }, [sidebarHidden]);

  return (
    <div className={`app-shell${sidebarHidden ? " sidebar-hidden" : ""}`}>
      <Sidebar active={page} onSelect={setPage} />
      <main className="main-content">
        <div className="app-topbar">
          <button
            type="button"
            className="app-topbar-btn"
            onClick={() => setSidebarHidden((v) => !v)}
            title={sidebarHidden ? "네비게이션 표시" : "네비게이션 숨김"}
          >
            {sidebarHidden ? "☰ 메뉴" : "◀ 네비 숨김"}
          </button>
          <span className="app-topbar-hint">간트 차트는 확대·줌 버튼 사용 · Esc로 닫기</span>
        </div>
        <PageContent page={page} />
      </main>
    </div>
  );
}
