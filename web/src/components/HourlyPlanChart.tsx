import type { HourlyStat, TaskInfo } from "../types";
import { fmtTime, num } from "../api";

const W = 520;
const H = 160;
const PAD = { l: 48, r: 16, t: 20, b: 32 };

interface Props {
  hourly: HourlyStat[];
  tasks: TaskInfo[];
  horizonHours: number;
}

/** 시간대별 계획 대비 누적 생산량(Move) 차트. */
export default function HourlyPlanChart({ hourly, tasks, horizonHours }: Props) {
  if (hourly.length === 0) return <div className="empty">시간대별 생산 데이터가 없습니다.</div>;

  const totalPlan = tasks.reduce((s, t) => s + t.plan_qty, 0);
  const points = hourly.map((h, i) => ({
    hour: h.hour,
    time: h.time,
    produce: h.produce,
    cumulative: h.cumulative,
    planCumulative: totalPlan * ((i + 1) / Math.max(horizonHours, 1)),
  }));

  const maxY = Math.max(totalPlan, ...points.map((p) => p.cumulative), 1);
  const innerW = W - PAD.l - PAD.r;
  const innerH = H - PAD.t - PAD.b;
  const n = points.length;
  const px = (i: number) => PAD.l + (i / Math.max(n - 1, 1)) * innerW;
  const py = (v: number) => PAD.t + innerH - (v / maxY) * innerH;

  const planPath = points.map((p, i) => `${i === 0 ? "M" : "L"}${px(i)},${py(p.planCumulative)}`).join(" ");
  const actualPath = points.map((p, i) => `${i === 0 ? "M" : "L"}${px(i)},${py(p.cumulative)}`).join(" ");

  const last = points[points.length - 1];
  const achievement = totalPlan > 0 ? last.cumulative / totalPlan : 0;

  return (
    <div className="hourly-plan-chart">
      <div className="hourly-plan-head">
        <span className="hourly-plan-title">시간대별 계획 대비 생산량</span>
        <span className="hourly-plan-meta">
          계획 <b>{num(totalPlan)}</b> · 실적 <b>{num(last.cumulative)}</b> · 달성 <b>{(achievement * 100).toFixed(1)}%</b>
        </span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="hourly-plan-svg" role="img">
        {[0, 0.5, 1].map((t) => {
          const yv = maxY * t;
          const y = py(yv);
          return (
            <g key={t}>
              <line x1={PAD.l} y1={y} x2={W - PAD.r} y2={y} stroke="#e1e6ef" />
              <text x={PAD.l - 6} y={y + 4} textAnchor="end" fill="#6b7689" fontSize={9}>
                {num(Math.round(yv))}
              </text>
            </g>
          );
        })}
        <path d={planPath} fill="none" stroke="#c98a00" strokeWidth={2} strokeDasharray="6 4" />
        <path d={actualPath} fill="none" stroke="#3b6fe0" strokeWidth={2} />
        {points.map((p, i) => (
          <g key={p.hour}>
            <circle cx={px(i)} cy={py(p.cumulative)} r={3} fill="#3b6fe0">
              <title>{`${fmtTime(p.time)} (+${p.hour + 1}h)\n시간 생산: ${num(p.produce)}\n누적: ${num(p.cumulative)} / 계획 ${num(Math.round(p.planCumulative))}`}</title>
            </circle>
            {(n <= 12 || i % Math.ceil(n / 8) === 0 || i === n - 1) && (
              <text x={px(i)} y={H - 8} textAnchor="middle" fill="#6b7689" fontSize={9}>
                {p.hour + 1}h
              </text>
            )}
          </g>
        ))}
      </svg>
      <div className="hourly-plan-legend">
        <span><span className="line-swatch plan" /> 계획 (선형)</span>
        <span><span className="line-swatch actual" /> 누적 생산</span>
      </div>
    </div>
  );
}
