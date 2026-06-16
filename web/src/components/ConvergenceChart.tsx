import { useEffect, useState } from "react";
import { fetchTrainingMetrics } from "../api";
import type { TrainingMetrics } from "../types";

const W = 640;
const H = 200;
const PAD = { l: 48, r: 16, t: 24, b: 36 };

interface Props {
  stage?: "dispatch" | "alloc";
}

export default function ConvergenceChart({ stage = "dispatch" }: Props) {
  const [data, setData] = useState<TrainingMetrics | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchTrainingMetrics(stage)
      .then(setData)
      .catch((e) => setError(String(e)));
  }, [stage]);

  if (error) return <div className="empty">수렴 로그 로드 실패</div>;
  if (!data) return <div className="empty">수렴 로그 불러오는 중…</div>;

  const points = data.points.filter((p) => p.mean_reward != null);
  if (points.length === 0) {
    return (
      <div className="empty">
        학습 로그 없음 — <code>python main.py train</code> 실행 후 표시됩니다.
      </div>
    );
  }

  const xs = points.map((p) => p.timesteps);
  const ys = points.map((p) => p.mean_reward as number);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const spanX = Math.max(maxX - minX, 1);
  const spanY = Math.max(maxY - minY, 1e-6);
  const innerW = W - PAD.l - PAD.r;
  const innerH = H - PAD.t - PAD.b;
  const px = (x: number) => PAD.l + ((x - minX) / spanX) * innerW;
  const py = (y: number) => PAD.t + innerH - ((y - minY) / spanY) * innerH;
  const path = points.map((p, i) => `${i === 0 ? "M" : "L"}${px(p.timesteps)},${py(p.mean_reward as number)}`).join(" ");

  const bcPoints = points.filter((p) => p.phase === "bc");
  const ppoPoints = points.filter((p) => p.phase === "ppo");

  return (
    <div className="convergence-wrap">
      <svg viewBox={`0 0 ${W} ${H}`} className="convergence-chart" role="img">
        {[0, 0.5, 1].map((t) => {
          const yv = minY + spanY * t;
          const y = py(yv);
          return (
            <g key={t}>
              <line x1={PAD.l} y1={y} x2={W - PAD.r} y2={y} stroke="#e1e6ef" />
              <text x={PAD.l - 6} y={y + 4} textAnchor="end" fill="#6b7689" fontSize={10}>
                {yv.toFixed(2)}
              </text>
            </g>
          );
        })}
        <path d={path} fill="none" stroke="#3b6fe0" strokeWidth={2} />
        {bcPoints.map((p) => (
          <circle key={`bc-${p.timesteps}`} cx={px(p.timesteps)} cy={py(p.mean_reward as number)}
                  r={3} fill="#c98a00" />
        ))}
        {ppoPoints.map((p) => (
          <circle key={`ppo-${p.timesteps}`} cx={px(p.timesteps)} cy={py(p.mean_reward as number)}
                  r={2.5} fill="#3b6fe0" />
        ))}
        <text x={PAD.l} y={H - 8} fill="#6b7689" fontSize={10}>{minX}</text>
        <text x={W - PAD.r} y={H - 8} textAnchor="end" fill="#6b7689" fontSize={10}>{maxX}</text>
      </svg>
      <div className="bench-chart-legend">
        <span style={{ color: "#3b6fe0" }}>● PPO 평균 보상</span>
        {bcPoints.length > 0 && <span style={{ color: "#c98a00" }}>● BC 단계</span>}
        <span>{points.length} 포인트</span>
      </div>
    </div>
  );
}
