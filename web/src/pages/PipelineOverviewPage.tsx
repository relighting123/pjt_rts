import { useEffect, useState } from "react";
import { fetchMlPipeline } from "../api";
import { pct } from "../api";
import type { PipelineStatus } from "../types";

const steps = [
  { key: "parameters", label: "1. 파라미터" },
  { key: "training", label: "2. 학습" },
  { key: "evaluation", label: "3. 검증·테스트" },
  { key: "compare", label: "4. 모델 비교" },
  { key: "registry", label: "5. 모델 등록" },
  { key: "ops", label: "6. 추론 배포" },
];

export default function PipelineOverviewPage() {
  const [data, setData] = useState<PipelineStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchMlPipeline()
      .then(setData)
      .catch((e) => setError(String(e)));
  }, []);

  if (error) return <div className="error">⚠ {error}</div>;
  if (!data) return <div className="empty">파이프라인 상태 불러오는 중…</div>;

  return (
    <div className="page">
      <header className="page-header">
        <h1>ML 파이프라인 개요</h1>
        <p className="page-sub">학습 → 검증/테스트 평가 → 모델 비교 → 최종 등록 → 추론</p>
      </header>

      <div className="pipeline-flow">
        {steps.map((s, i) => (
          <div key={s.key} className="pipeline-step">
            <span className="pipeline-step-num">{i + 1}</span>
            <span>{s.label}</span>
          </div>
        ))}
      </div>

      <div className="overview-cards cols-4">
        <div className="kpi-card">
          <div className="label">학습 데이터 (검증)</div>
          <div className="value">{data.train_json_count}</div>
          <div className="sub">data/raw/train</div>
        </div>
        <div className="kpi-card">
          <div className="label">테스트 데이터</div>
          <div className="value">{data.test_json_count}</div>
          <div className="sub">data/raw/test</div>
        </div>
        <div className="kpi-card">
          <div className="label">등록/체크포인트 모델</div>
          <div className="value">{data.models_count}</div>
          <div className="sub">{data.active_model_exists ? "활성 모델 있음" : "활성 모델 없음"}</div>
        </div>
        <div className="kpi-card">
          <div className="label">학습 로그 포인트</div>
          <div className="value">{data.training_points}</div>
          <div className="sub">PPO 수렴 곡선</div>
        </div>
      </div>

      <div className="ml-grid-2">
        <section className="panel-card">
          <h2>검증 셋 (Validation) KPI</h2>
          <p className="panel-sub">학습에 사용한 train JSON 기준 RL vs 휴리스틱</p>
          <table className="ml-table">
            <thead>
              <tr>
                <th>지표</th>
                <th>휴리스틱</th>
                <th>RL</th>
                <th>Optimal</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>계획달성률</td>
                <td>{pct(data.validation?.heuristic_plan_achievement)}</td>
                <td>{pct(data.validation?.rl_plan_achievement)}</td>
                <td>{pct(data.validation?.optimal)}</td>
              </tr>
              <tr>
                <td>가동률</td>
                <td>{pct(data.validation?.heuristic_utilization)}</td>
                <td>{pct(data.validation?.rl_utilization)}</td>
                <td>—</td>
              </tr>
              <tr>
                <td>에피소드 Reward</td>
                <td colSpan={3}>{data.validation?.rl_episode_reward?.toFixed(4) ?? "N/A"}</td>
              </tr>
            </tbody>
          </table>
        </section>

        <section className="panel-card">
          <h2>테스트 셋 KPI</h2>
          <p className="panel-sub">미학습 벤치마크 일반화 성능</p>
          <table className="ml-table">
            <thead>
              <tr>
                <th>지표</th>
                <th>휴리스틱</th>
                <th>RL</th>
                <th>Optimal</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>계획달성률</td>
                <td>{pct(data.test?.heuristic_plan_achievement)}</td>
                <td>{pct(data.test?.rl_plan_achievement)}</td>
                <td>{pct(data.test?.optimal)}</td>
              </tr>
              <tr>
                <td>가동률</td>
                <td>{pct(data.test?.heuristic_utilization)}</td>
                <td>{pct(data.test?.rl_utilization)}</td>
                <td>—</td>
              </tr>
              <tr>
                <td>에피소드 Reward</td>
                <td colSpan={3}>{data.test?.rl_episode_reward?.toFixed(4) ?? "N/A"}</td>
              </tr>
            </tbody>
          </table>
        </section>
      </div>

      <section className="panel-card">
        <h2>현재 파라미터 요약</h2>
        <div className="param-chips">
          <span className="param-chip">PPO steps: {data.config.ppo_steps.toLocaleString()}</span>
          <span className="param-chip">BC epochs: {data.config.bc_epochs}</span>
          <span className="param-chip">dwell λ: {data.config.dwell_lambda}</span>
          <span className="param-chip">alloc λ: {data.config.alloc_lambda}</span>
          <span className="param-chip">max tasks: {data.config.max_tasks}</span>
        </div>
      </section>
    </div>
  );
}
