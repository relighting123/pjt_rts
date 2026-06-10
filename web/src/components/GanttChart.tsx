import type { GanttSegment } from "../types";
import { colorScale, fmtTime, num } from "../api";

interface Props {
  segments: GanttSegment[];
}

const ROW_H = 34;
const BAR_H = 24;
const LABEL_W = 110;
const AXIS_H = 26;

/** 장비 호기(EQP_ID)별 배치 타임라인 + 전환(CONV) 구간 오버레이 SVG 간트. */
export default function GanttChart({ segments }: Props) {
  if (segments.length === 0) return <div className="empty">배치 데이터가 없습니다.</div>;

  const eqpIds = [...new Set(segments.map((s) => s.eqp_id))].sort();
  const t0 = Math.min(...segments.map((s) => +new Date(s.start)));
  const t1 = Math.max(...segments.map((s) => +new Date(s.end)));
  const span = Math.max(t1 - t0, 1);

  const chartW = Math.max(720, Math.min(1280, Math.round((span / 3.6e6) * 110)));
  const width = LABEL_W + chartW + 16;
  const height = AXIS_H + eqpIds.length * ROW_H + 8;
  const x = (ms: number) => LABEL_W + ((ms - t0) / span) * chartW;

  const runTasks = segments.filter((s) => s.kind === "RUN").map((s) => s.task);
  const color = colorScale(runTasks);

  // 시간 눈금: 1시간 간격 (너무 많으면 간격 확대)
  const hourMs = 3.6e6;
  const hours = Math.ceil(span / hourMs);
  const tickStep = hours > 18 ? Math.ceil(hours / 18) : 1;
  const ticks: number[] = [];
  for (let t = t0; t <= t1 + 1; t += hourMs * tickStep) ticks.push(t);

  return (
    <div>
      <svg width={width} height={height} role="img">
        {/* 눈금 + 그리드 */}
        {ticks.map((t) => (
          <g key={t}>
            <line x1={x(t)} y1={AXIS_H - 4} x2={x(t)} y2={height - 6} stroke="#2c3650" />
            <text x={x(t) + 3} y={AXIS_H - 9} fill="#8b96ad" fontSize={11}>
              {fmtTime(new Date(t).toISOString())}
            </text>
          </g>
        ))}
        {/* 호기 행 */}
        {eqpIds.map((eqp, i) => {
          const y = AXIS_H + i * ROW_H;
          return (
            <g key={eqp}>
              <rect x={0} y={y} width={width} height={ROW_H} fill={i % 2 ? "#1c2335" : "none"} />
              <text x={8} y={y + ROW_H / 2 + 4} fill="#e6eaf2" fontSize={12} fontWeight={600}>
                {eqp}
              </text>
            </g>
          );
        })}
        {/* RUN 바 */}
        {segments.filter((s) => s.kind === "RUN").map((s, idx) => {
          const y = AXIS_H + eqpIds.indexOf(s.eqp_id) * ROW_H + (ROW_H - BAR_H) / 2;
          const x0 = x(+new Date(s.start));
          const w = Math.max(x(+new Date(s.end)) - x0, 2);
          return (
            <g key={`run-${idx}`}>
              <rect x={x0} y={y} width={w} height={BAR_H} rx={4} fill={color(s.task)}>
                <title>
                  {`${s.eqp_id} (${s.model})\n작업: ${s.task} · BATCH ${s.batch_id}\n${fmtTime(s.start)} ~ ${fmtTime(s.end)}\n생산량: ${num(s.qty)}`}
                </title>
              </rect>
              {w > 56 && (
                <text x={x0 + w / 2} y={y + BAR_H / 2 + 4} fill="#0f1420" fontSize={11}
                      fontWeight={700} textAnchor="middle" pointerEvents="none">
                  {s.task}
                </text>
              )}
            </g>
          );
        })}
        {/* CONV(전환) 바 */}
        {segments.filter((s) => s.kind === "CONV").map((s, idx) => {
          const y = AXIS_H + eqpIds.indexOf(s.eqp_id) * ROW_H + (ROW_H - BAR_H) / 2;
          const x0 = x(+new Date(s.start));
          const w = Math.max(x(+new Date(s.end)) - x0, 2);
          return (
            <g key={`conv-${idx}`}>
              <rect x={x0} y={y} width={w} height={BAR_H} rx={4}
                    fill="rgba(232,104,74,0.25)" stroke="#e8684a" strokeDasharray="4 3">
                <title>
                  {`[전환] ${s.eqp_id} (${s.model})\n${s.from_batch} → ${s.to_batch} (${s.from_task} → ${s.to_task})\n${fmtTime(s.start)} ~ ${fmtTime(s.end)}`}
                </title>
              </rect>
              {w > 50 && (
                <text x={x0 + w / 2} y={y + BAR_H / 2 + 4} fill="#e8684a" fontSize={11}
                      fontWeight={700} textAnchor="middle" pointerEvents="none">
                  {s.from_batch}→{s.to_batch}
                </text>
              )}
            </g>
          );
        })}
      </svg>
      <div className="legend">
        {[...new Set(runTasks)].sort().map((t) => (
          <span className="item" key={t}>
            <span className="swatch" style={{ background: color(t) }} /> {t}
          </span>
        ))}
        <span className="item">
          <span className="swatch"
                style={{ background: "rgba(232,104,74,0.25)", border: "1px dashed #e8684a" }} />
          tool 전환 (batch 변경)
        </span>
      </div>
    </div>
  );
}
