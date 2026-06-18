import type { GanttSegment, WipProduct } from "../types";
import { colorScale, fmtTime, num } from "../api";

interface Props {
  segments: GanttSegment[];
  title?: string;
  wipProducts?: WipProduct[];
}

const ROW_H = 36;
const BAR_H = 24;
const LABEL_W = 120;
const GROUP_H = 22;
const AXIS_H = 28;

function comboKey(s: Pick<GanttSegment, "batch_id" | "plan_prod_key" | "oper_id">) {
  return `${s.batch_id}/${s.plan_prod_key}/${s.oper_id}`;
}

function barLabel(s: Pick<GanttSegment, "batch_id" | "plan_prod_key" | "oper_id">, w: number) {
  const full = comboKey(s);
  if (w >= 140) return full;
  if (w >= 88) return `${s.batch_id}·${s.plan_prod_key}`;
  if (w >= 52) return s.batch_id || s.plan_prod_key;
  return "";
}

function WipStrip({ products, title }: { products: WipProduct[]; title?: string }) {
  if (!products.length) return null;
  return (
    <div className="gantt-wip-strip">
      <span className="gantt-wip-title">{title ? `${title} · ` : ""}가용 재공 (제품별)</span>
      <div className="gantt-wip-chips">
        {products.map((p) => (
          <div
            key={p.plan_prod_key}
            className={`gantt-wip-chip${p.remaining_wip <= 0 ? " done" : ""}`}
          >
            <span className="gantt-wip-product">{p.plan_prod_key}</span>
            <span className="gantt-wip-values">
              가용 <b>{num(p.init_wip)}</b>
              {" · "}소진 <b>{num(p.consumed_wip)}</b>
              {" · "}잔여 <b>{num(p.remaining_wip)}</b>
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function GanttChart({ segments, title, wipProducts }: Props) {
  if (segments.length === 0) return <div className="empty">배치 데이터가 없습니다.</div>;

  const t0 = Math.min(...segments.map((s) => +new Date(s.start)));
  const t1 = Math.max(...segments.map((s) => +new Date(s.end)));
  const span = Math.max(t1 - t0, 1);
  const spanHours = span / 3.6e6;
  const chartW = Math.max(480, Math.min(1200, Math.round(spanHours * 96)));
  const x = (ms: number) => LABEL_W + ((ms - t0) / span) * chartW;

  // group: model → sorted eqp_ids
  const modelOrder: string[] = [];
  const modelEqps: Record<string, string[]> = {};
  for (const s of segments) {
    if (!modelEqps[s.model]) { modelEqps[s.model] = []; modelOrder.push(s.model); }
    if (!modelEqps[s.model].includes(s.eqp_id)) modelEqps[s.model].push(s.eqp_id);
  }
  const uniqueModels = [...new Set(modelOrder)];
  uniqueModels.forEach((m) => modelEqps[m].sort());

  // Build ordered list: [(eqp_id, yOffset, modelGroupStart)]
  type Row = { eqp_id: string; y: number; model: string };
  const rows: Row[] = [];
  const groupHeaders: { model: string; y: number }[] = [];
  let curY = AXIS_H;
  for (const model of uniqueModels) {
    groupHeaders.push({ model, y: curY });
    curY += GROUP_H;
    for (const eqp of modelEqps[model]) {
      rows.push({ eqp_id: eqp, y: curY, model });
      curY += ROW_H;
    }
  }

  const totalHeight = curY + 8;
  const totalWidth = LABEL_W + chartW + 16;
  const eqpYMap = new Map(rows.map((r) => [r.eqp_id, r.y]));

  // color by batch + product + process
  const combos = [...new Set(segments.filter((s) => s.kind === "RUN").map(comboKey))];
  const color = colorScale(combos);

  // time ticks
  const hourMs = 3.6e6;
  const hours = Math.ceil(span / hourMs);
  const tickStep = hours > 18 ? Math.ceil(hours / 18) : 1;
  const ticks: number[] = [];
  for (let t = t0; t <= t1 + 1; t += hourMs * tickStep) ticks.push(t);

  return (
    <div className="gantt-embedded">
      {wipProducts && wipProducts.length > 0 && (
        <WipStrip products={wipProducts} title={title} />
      )}
      <div className="gantt-wrap">
      <svg viewBox={`0 0 ${totalWidth} ${totalHeight}`} className="gantt-svg" role="img">
        <defs>
          <pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <line x1="0" y1="0" x2="0" y2="6" stroke="#d6492a" strokeWidth="2" strokeOpacity="0.5" />
          </pattern>
        </defs>

        {/* X-axis ticks */}
        {ticks.map((t) => (
          <g key={t}>
            <line x1={x(t)} y1={AXIS_H - 4} x2={x(t)} y2={totalHeight - 6} stroke="#e1e6ef" />
            <text x={x(t) + 3} y={AXIS_H - 10} fill="#6b7689" fontSize={11}>
              {fmtTime(new Date(t).toISOString())}
            </text>
          </g>
        ))}

        {/* Model group headers */}
        {groupHeaders.map(({ model, y }) => (
          <g key={`grp-${model}`}>
            <rect x={0} y={y} width={totalWidth} height={GROUP_H} fill="#eef1f8" />
            <text x={8} y={y + GROUP_H / 2 + 4} fill="#3b6fe0" fontSize={12} fontWeight={700}>
              {model}
            </text>
          </g>
        ))}

        {/* EQP rows */}
        {rows.map(({ eqp_id, y }, i) => (
          <g key={eqp_id}>
            <rect x={0} y={y} width={totalWidth} height={ROW_H} fill={i % 2 ? "#f3f6fb" : "none"} />
            <text x={8} y={y + ROW_H / 2 + 4} fill="#1f2733" fontSize={12} fontWeight={500}>
              {eqp_id}
            </text>
          </g>
        ))}

        {/* RUN bars */}
        {segments.filter((s) => s.kind === "RUN").map((s, idx) => {
          const rowY = eqpYMap.get(s.eqp_id);
          if (rowY == null) return null;
          const by = rowY + (ROW_H - BAR_H) / 2;
          const x0 = x(+new Date(s.start));
          const w = Math.max(x(+new Date(s.end)) - x0, 2);
          const key = comboKey(s);
          const label = barLabel(s, w);
          return (
            <g key={`run-${idx}`}>
              <rect x={x0} y={by} width={w} height={BAR_H} rx={4} fill={color(key)}>
                <title>{`${s.eqp_id} (${s.model})\nBatch: ${s.batch_id} · 제품: ${s.plan_prod_key} · 공정: ${s.oper_id}\n${fmtTime(s.start)} ~ ${fmtTime(s.end)}\n생산량: ${num(s.qty)}`}</title>
              </rect>
              {label && (
                <text x={x0 + w / 2} y={by + BAR_H / 2 + 4} fill="#fff" fontSize={10}
                      fontWeight={700} textAnchor="middle" pointerEvents="none">
                  {label}
                </text>
              )}
            </g>
          );
        })}

        {/* CONV bars */}
        {segments.filter((s) => s.kind === "CONV").map((s, idx) => {
          const rowY = eqpYMap.get(s.eqp_id);
          if (rowY == null) return null;
          const by = rowY + (ROW_H - BAR_H) / 2;
          const x0 = x(+new Date(s.start));
          const w = Math.max(x(+new Date(s.end)) - x0, 2);
          return (
            <g key={`conv-${idx}`}>
              <rect x={x0} y={by} width={w} height={BAR_H} rx={4} fill="url(#hatch)"
                    stroke="#d6492a" strokeWidth={1.5} strokeDasharray="4 3">
                <title>{`[전환] ${s.eqp_id} (${s.model})\n${s.from_batch} → ${s.to_batch}\n${fmtTime(s.start)} ~ ${fmtTime(s.end)}`}</title>
              </rect>
              {w > 52 && (
                <text x={x0 + w / 2} y={by + BAR_H / 2 + 4} fill="#d6492a" fontSize={10}
                      fontWeight={700} textAnchor="middle" pointerEvents="none">
                  {s.from_batch}→{s.to_batch}
                </text>
              )}
            </g>
          );
        })}
      </svg>

      <div className="legend">
        {combos.sort().map((k) => (
          <span className="item" key={k}>
            <span className="swatch" style={{ background: color(k) }} /> {k}
          </span>
        ))}
        <span className="item">
          <span className="swatch" style={{ background: "url(#hatch)", border: "1.5px dashed #d6492a", borderRadius: 3 }} />
          <span style={{ borderLeft: "3px solid #d6492a", paddingLeft: 4 }}>전환(CONV)</span>
        </span>
      </div>
      </div>
    </div>
  );
}
