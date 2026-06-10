import type { HourlyStat } from "../types";
import { fmtTime, num, pct } from "../api";

interface Props {
  hourly: HourlyStat[];
}

const W = 560;
const H = 220;
const PAD = { l: 46, r: 40, t: 12, b: 28 };

/** 시간별 생산량(bar) + 가동률(line) SVG 차트. */
export default function HourlyChart({ hourly }: Props) {
  if (hourly.length === 0) return <div className="empty">시간별 데이터가 없습니다.</div>;

  const innerW = W - PAD.l - PAD.r;
  const innerH = H - PAD.t - PAD.b;
  const maxProduce = Math.max(...hourly.map((h) => h.produce), 1);
  const bw = innerW / hourly.length;

  const xc = (i: number) => PAD.l + i * bw + bw / 2;
  const yProd = (v: number) => PAD.t + innerH * (1 - v / maxProduce);
  const yUtil = (v: number) => PAD.t + innerH * (1 - v);

  const utilPath = hourly
    .map((h, i) => `${i === 0 ? "M" : "L"}${xc(i)},${yUtil(h.util_rate)}`)
    .join(" ");

  return (
    <svg width={W} height={H} role="img">
      {/* y축 (생산량) */}
      {[0, 0.5, 1].map((f) => (
        <g key={f}>
          <line x1={PAD.l} y1={yProd(maxProduce * f)} x2={W - PAD.r} y2={yProd(maxProduce * f)}
                stroke="#2c3650" />
          <text x={PAD.l - 6} y={yProd(maxProduce * f) + 4} fill="#8b96ad" fontSize={10}
                textAnchor="end">
            {num(Math.round(maxProduce * f))}
          </text>
          <text x={W - PAD.r + 6} y={yUtil(f) + 4} fill="#8b96ad" fontSize={10}>
            {Math.round(f * 100)}%
          </text>
        </g>
      ))}
      {/* bars */}
      {hourly.map((h, i) => (
        <rect key={h.hour} x={PAD.l + i * bw + bw * 0.15} y={yProd(h.produce)}
              width={bw * 0.7} height={PAD.t + innerH - yProd(h.produce)}
              rx={3} fill="#5b8ff9">
          <title>{`${fmtTime(h.time)} (H${h.hour})\n생산량: ${num(h.produce)}\n누적: ${num(h.cumulative)}\n가동률: ${pct(h.util_rate)}`}</title>
        </rect>
      ))}
      {/* 가동률 line */}
      <path d={utilPath} fill="none" stroke="#f6bd16" strokeWidth={2} />
      {hourly.map((h, i) => (
        <circle key={h.hour} cx={xc(i)} cy={yUtil(h.util_rate)} r={3} fill="#f6bd16">
          <title>{`H${h.hour} 가동률 ${pct(h.util_rate)}`}</title>
        </circle>
      ))}
      {/* x labels */}
      {hourly.map((h, i) => (
        <text key={h.hour} x={xc(i)} y={H - 8} fill="#8b96ad" fontSize={10} textAnchor="middle">
          H{h.hour}
        </text>
      ))}
    </svg>
  );
}
