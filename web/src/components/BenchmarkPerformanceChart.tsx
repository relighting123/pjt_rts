import type { SummaryRow } from "../types";
import { isMeaningfulOptimal } from "../api";

export type BenchmarkMetric = "plan_achievement" | "utilization" | "conversion";

interface Props {
  rows: SummaryRow[];
  selected: string;
  onSelect: (name: string) => void;
  metric: BenchmarkMetric;
  title: string;
  subtitle?: string;
  compact?: boolean;
}

const FULL_W = 920;
const COMPACT_W = 520;
const FULL_H = 200;
const COMPACT_H = 170;
const PAD = { l: 58, r: 24, t: 28, b: 72 };

const COLORS = {
  optimal: "#18a06c",
  heuristic: "#3b6fe0",
  rl: "#9270ca",
};

function seriesForMetric(metric: BenchmarkMetric, row: SummaryRow) {
  if (metric === "plan_achievement") {
    const series = [
      { key: "heuristic", label: "휴리스틱", value: row.heuristic, color: COLORS.heuristic },
      { key: "rl", label: "RL", value: row.rl, color: COLORS.rl },
    ];
    if (isMeaningfulOptimal(row.optimal)) {
      series.unshift({ key: "optimal", label: "최적", value: row.optimal, color: COLORS.optimal });
    }
    return series;
  }
  if (metric === "utilization") {
    return [
      { key: "heuristic", label: "휴리스틱", value: row.heuristic_utilization, color: COLORS.heuristic },
      { key: "rl", label: "RL", value: row.rl_utilization, color: COLORS.rl },
    ];
  }
  return [
    { key: "heuristic", label: "휴리스틱", value: row.heuristic_conversion_count, color: COLORS.heuristic },
    { key: "rl", label: "RL", value: row.rl_conversion_count, color: COLORS.rl },
  ];
}

function formatValue(metric: BenchmarkMetric, value: number) {
  if (metric === "conversion") return `${value.toFixed(1)}회`;
  return `${(value * 100).toFixed(1)}%`;
}

/** 벤치마크별 성능 지표 그룹 막대 차트. */
export default function BenchmarkPerformanceChart({
  rows,
  selected,
  onSelect,
  metric,
  title,
  subtitle,
  compact = false,
}: Props) {
  if (rows.length === 0) return <div className="empty">벤치마크가 없습니다.</div>;

  const W = compact ? COMPACT_W : FULL_W;
  const H = compact ? COMPACT_H : FULL_H;
  const innerW = W - PAD.l - PAD.r;
  const innerH = H - PAD.t - PAD.b;
  const groupW = innerW / rows.length;
  const maxY = metric === "conversion"
    ? Math.max(
        1,
        ...rows.flatMap((r) => [
          r.heuristic_conversion_count,
          r.rl_conversion_count,
        ]),
      )
    : 1;
  const y = (v: number) => PAD.t + innerH * (1 - Math.max(0, Math.min(maxY, v)) / maxY);
  const showOptimalLegend = metric === "plan_achievement"
    && rows.some((r) => isMeaningfulOptimal(r.optimal));

  return (
    <div className="bench-chart-wrap bench-chart-block">
      <div className="bench-chart-head">
        <div className="bench-chart-title">{title}</div>
        {subtitle && <div className="bench-chart-sub">{subtitle}</div>}
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="bench-chart" role="img">
        {metric === "conversion"
          ? [0, Math.ceil(maxY / 2), maxY].map((t, i) => (
              <g key={`${t}-${i}`}>
                <line x1={PAD.l} y1={y(t)} x2={W - PAD.r} y2={y(t)} stroke="#e1e6ef" />
                <text x={PAD.l - 8} y={y(t) + 4} textAnchor="end" fill="#6b7689" fontSize={11}>
                  {t.toFixed(0)}회
                </text>
              </g>
            ))
          : [0, 0.25, 0.5, 0.75, 1].map((t) => (
              <g key={t}>
                <line x1={PAD.l} y1={y(t)} x2={W - PAD.r} y2={y(t)} stroke="#e1e6ef" />
                <text x={PAD.l - 8} y={y(t) + 4} textAnchor="end" fill="#6b7689" fontSize={11}>
                  {Math.round(t * 100)}%
                </text>
              </g>
            ))}

        {rows.map((r, i) => {
          const cx = PAD.l + i * groupW;
          const series = seriesForMetric(metric, r).filter((s) => s.value != null);
          const barCount = series.length;
          const barW = Math.max(5, groupW * (barCount >= 3 ? 0.22 : 0.28));
          const gap = barW * 0.2;
          const isSelected = selected === r.name;
          const groupLeft = cx + (groupW - (barW * barCount + gap * Math.max(0, barCount - 1))) / 2;
          return (
            <g key={r.name}>
              {isSelected && (
                <rect
                  x={cx + 2}
                  y={PAD.t}
                  width={groupW - 4}
                  height={innerH}
                  fill="rgba(59,111,224,0.10)"
                  rx={6}
                />
              )}
              {series.map((s, j) => {
                const top = y(s.value!);
                return (
                  <rect
                    key={s.key}
                    x={groupLeft + j * (barW + gap)}
                    y={top}
                    width={barW}
                    height={PAD.t + innerH - top}
                    fill={s.color}
                    rx={4}
                    style={{ cursor: "pointer" }}
                    onClick={() => onSelect(r.name)}
                  >
                    <title>{`${r.name}\n${s.label}: ${formatValue(metric, s.value)}`}</title>
                  </rect>
                );
              })}
              <text
                x={cx + groupW / 2}
                y={H - PAD.b + 12}
                textAnchor="end"
                fill="#6b7689"
                fontSize={10}
                transform={`rotate(-35 ${cx + groupW / 2},${H - PAD.b + 12})`}
                style={{ cursor: "pointer" }}
                onClick={() => onSelect(r.name)}
              >
                {r.name}
              </text>
            </g>
          );
        })}
      </svg>
      <div className="bench-chart-legend">
        {showOptimalLegend && <span style={{ color: COLORS.optimal }}>■ 최적</span>}
        <span style={{ color: COLORS.heuristic }}>■ 휴리스틱</span>
        <span style={{ color: COLORS.rl }}>■ RL</span>
      </div>
    </div>
  );
}
