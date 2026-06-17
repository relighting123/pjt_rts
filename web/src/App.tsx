import { useState } from "react";
import Sidebar from "./components/Sidebar";
import type { PageId } from "./navigation";
import PipelineOverviewPage from "./pages/PipelineOverviewPage";
import ParametersPage from "./pages/ParametersPage";
import TrainingPage from "./pages/TrainingPage";
import EvaluationPage from "./pages/EvaluationPage";
import ModelComparePage from "./pages/ModelComparePage";
import ModelRegistryPage from "./pages/ModelRegistryPage";
import OpsPage from "./pages/OpsPage";
import BenchmarkPage from "./pages/BenchmarkPage";
import "./styles.css";

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

  return (
    <div className="app-shell">
      <Sidebar active={page} onSelect={setPage} />
      <main className="main-content">
        <PageContent page={page} />
      </main>
    </div>
  );
}
