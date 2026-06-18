import type { HourlyStat } from "../types";
import { fmtTime, num } from "../api";

interface Props {
  hourly: HourlyStat[];
  compact?: boolean;
}

const FULL_W = 520;
const FULL_H = 200;
const PAD = { l: 48, r: 16, t: 24, b: 48 };

/** 시간대별 계획 vs 실적(move) 막대 차트. */
export default function PlanVsMoveChart({ hourly, compact = true }: Props) {
  if (hourly.length === 0) return <div className="empty">시간대 데이터가 없습니다.</div>;

  const W = compact ? FULL_W : FULL_W + 200;
  const H = FULL_H;
  const innerW = W - PAD.l - PAD.r;
  const innerH = H - PAD.t - PAD.b;
  const maxY = Math.max(
    1,
    ...hourly.flatMap((h) => [h.plan_hourly, h.produce, h.plan_cumulative, h.cumulative]),
  );
  const y = (v: number) => PAD.t + innerH * (1 - v / maxY);
  const groupW = innerW / hourly.length;
  const barW = Math.max(8, groupW * 0.28);
  const gap = barW * 0.15;

  return (
    <div className="plan-move-wrap">
      <div className="plan-move-head">
        <div className="plan-move-title">시간대별 계획 vs Move</div>
        <div className="plan-move-sub">시간당 균등 배분 계획 대비 실적 생산량</div>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="plan-move-chart" role="img">
        {[0, maxY / 2, maxY].map((t, i) => (
          <g key={`${t}-${i}`}>
            <line x1={PAD.l} y1={y(t)} x2={W - PAD.r} y2={y(t)} stroke="#e1e6ef" />
            <text x={PAD.l - 6} y={y(t) + 4} textAnchor="end" fill="#6b7689" fontSize={10}>
              {num(t)}
            </text>
          </g>
        ))}

        {hourly.map((h, i) => {
          const cx = PAD.l + i * groupW + groupW / 2;
          const planTop = y(h.plan_hourly);
          const prodTop = y(h.produce);
          const left = cx - barW - gap / 2;
          return (
            <g key={h.hour}>
              <rect
                x={left}
                y={planTop}
                width={barW}
                height={PAD.t + innerH - planTop}
                fill="#a8b8d8"
                rx={3}
              >
                <title>{`H${h.hour} 계획: ${num(h.plan_hourly)}\n누적 계획: ${num(h.plan_cumulative)}`}</title>
              </rect>
              <rect
                x={left + barW + gap}
                y={prodTop}
                width={barW}
                height={PAD.t + innerH - prodTop}
                fill="#3b6fe0"
                rx={3}
              >
                <title>{`H${h.hour} 실적: ${num(h.produce)}\n누적 실적: ${num(h.cumulative)}`}</title>
              </rect>
              <text
                x={cx}
                y={H - PAD.b + 14}
                textAnchor="middle"
                fill="#6b7689"
                fontSize={10}
              >
                {fmtTime(h.time)}
              </text>
            </g>
          );
        })}
      </svg>
      <div className="legend">
        <span className="item">
          <span className="swatch" style={{ background: "#a8b8d8" }} /> 계획
        </span>
        <span className="item">
          <span className="swatch" style={{ background: "#3b6fe0" }} /> Move(실적)
        </span>
      </div>
    </div>
  );
}
