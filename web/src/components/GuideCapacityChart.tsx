import type { GuideRow } from "../types";
import { num, pct } from "../api";

interface Props {
  guide: GuideRow[];
}

const W = 580;
const H = 240;
const PAD = { l: 56, r: 16, t: 14, b: 52 };

/** 공정별 계획수량 vs 합산 Capa 비교 + 달성률 차트 (Mode 1 가이드). */
export default function GuideCapacityChart({ guide }: Props) {
  if (guide.length === 0) return <div className="empty">가이드 배분 데이터가 없습니다.</div>;

  // 공정별 집계
  const summaryMap = new Map<string, { plan_qty: number; total_capacity: number }>();
  for (const g of guide) {
    const cur = summaryMap.get(g.task) ?? { plan_qty: g.plan_qty, total_capacity: 0 };
    cur.total_capacity += g.capacity;
    summaryMap.set(g.task, cur);
  }
  const tasks = [...summaryMap.entries()].map(([task, s]) => ({
    task,
    plan_qty: s.plan_qty,
    total_capacity: s.total_capacity,
    rate: s.plan_qty > 0 ? Math.min(s.total_capacity, s.plan_qty) / s.plan_qty : 1.0,
  }));

  const innerW = W - PAD.l - PAD.r;
  const innerH = H - PAD.t - PAD.b;
  const maxVal = Math.max(...tasks.flatMap((t) => [t.plan_qty, t.total_capacity]), 1);
  const n = tasks.length;
  const groupW = innerW / n;
  const barW = Math.min(groupW * 0.35, 24);

  const yV = (v: number) => PAD.t + innerH * (1 - v / maxVal);
  const yR = (r: number) => PAD.t + innerH * (1 - r);
  const xCenter = (i: number) => PAD.l + i * groupW + groupW / 2;

  // 달성률 line path
  const ratePath = tasks
    .map((t, i) => `${i === 0 ? "M" : "L"}${xCenter(i)},${yR(Math.min(t.rate, 1))}`)
    .join(" ");

  // y축 눈금
  const gridLines = [0, 0.25, 0.5, 0.75, 1.0];

  return (
    <svg width={W} height={H} role="img" style={{ overflow: "visible" }}>
      {/* 그리드 */}
      {gridLines.map((f) => (
        <g key={f}>
          <line x1={PAD.l} y1={yV(maxVal * f)} x2={W - PAD.r} y2={yV(maxVal * f)}
                stroke="#e1e6ef" strokeDasharray={f === 0 ? "none" : "3,3"} />
          <text x={PAD.l - 6} y={yV(maxVal * f) + 4} fill="#6b7689" fontSize={10} textAnchor="end">
            {num(Math.round(maxVal * f))}
          </text>
          {/* 달성률 오른쪽 축 */}
          <text x={W - PAD.r + 6} y={yR(f) + 4} fill="#6b7689" fontSize={10}>
            {Math.round(f * 100)}%
          </text>
        </g>
      ))}

      {/* 100% 달성 기준선 */}
      <line x1={PAD.l} y1={yR(1)} x2={W - PAD.r} y2={yR(1)}
            stroke="#1a8a45" strokeWidth={1} strokeDasharray="5,3" opacity={0.5} />

      {/* 막대 */}
      {tasks.map((t, i) => {
        const cx = xCenter(i);
        return (
          <g key={t.task}>
            {/* 계획수량 (파랑) */}
            <rect x={cx - barW - 2} y={yV(t.plan_qty)}
                  width={barW} height={Math.max(1, yV(0) - yV(t.plan_qty))}
                  rx={2} fill="#3b6fe0" opacity={0.85}>
              <title>{`${t.task}\n계획수량: ${num(t.plan_qty)}`}</title>
            </rect>
            {/* 합산 Capa (주황) */}
            <rect x={cx + 2} y={yV(t.total_capacity)}
                  width={barW} height={Math.max(1, yV(0) - yV(t.total_capacity))}
                  rx={2} fill="#e0a400" opacity={0.85}>
              <title>{`${t.task}\n합산Capa: ${num(Math.round(t.total_capacity))}\n달성률: ${pct(t.rate)}`}</title>
            </rect>
          </g>
        );
      })}

      {/* 달성률 라인 */}
      <path d={ratePath} fill="none" stroke="#1a8a45" strokeWidth={2} />
      {tasks.map((t, i) => {
        const r = Math.min(t.rate, 1);
        const color = t.rate >= 1.0 ? "#1a8a45" : t.rate >= 0.8 ? "#e0a400" : "#c0392b";
        return (
          <circle key={t.task} cx={xCenter(i)} cy={yR(r)} r={4} fill={color} stroke="#fff" strokeWidth={1.5}>
            <title>{`${t.task}\n달성률: ${pct(t.rate)}`}</title>
          </circle>
        );
      })}

      {/* x 레이블 */}
      {tasks.map((t, i) => {
        const cx = xCenter(i);
        const label = t.task.length > 14 ? t.task.slice(0, 13) + "…" : t.task;
        return (
          <text key={t.task} x={cx} y={H - PAD.b + 14} fill="#6b7689" fontSize={10}
                textAnchor="middle" transform={`rotate(-30, ${cx}, ${H - PAD.b + 14})`}>
            {label}
          </text>
        );
      })}

      {/* 범례 */}
      <rect x={PAD.l} y={PAD.t - 10} width={10} height={10} rx={2} fill="#3b6fe0" opacity={0.85} />
      <text x={PAD.l + 14} y={PAD.t} fill="#444" fontSize={11}>계획수량</text>
      <rect x={PAD.l + 64} y={PAD.t - 10} width={10} height={10} rx={2} fill="#e0a400" opacity={0.85} />
      <text x={PAD.l + 78} y={PAD.t} fill="#444" fontSize={11}>합산Capa</text>
      <line x1={PAD.l + 134} y1={PAD.t - 5} x2={PAD.l + 144} y2={PAD.t - 5}
            stroke="#1a8a45" strokeWidth={2} />
      <circle cx={PAD.l + 139} cy={PAD.t - 5} r={3} fill="#1a8a45" />
      <text x={PAD.l + 148} y={PAD.t} fill="#444" fontSize={11}>달성률</text>
    </svg>
  );
}
