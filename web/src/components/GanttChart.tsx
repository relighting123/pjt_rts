import type { GanttAllocRow, GanttSegment, GanttWipRow } from "../types";
import { colorScale, fmtTime, num } from "../api";

interface Props {
  segments: GanttSegment[];
  wipSummary?: GanttWipRow[];
  allocSummary?: GanttAllocRow[];
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

function idleLabel(s: GanttSegment) {
  if (s.kind === "UNALLOC") return "미할당";
  if (s.idle_reason === "WIP_ZERO") return "재공0";
  return "대기";
}

export default function GanttChart({ segments, wipSummary = [], allocSummary = [] }: Props) {
  if (segments.length === 0) return <div className="empty">배치 데이터가 없습니다.</div>;

  const t0 = Math.min(...segments.map((s) => +new Date(s.start)));
  const t1 = Math.max(...segments.map((s) => +new Date(s.end)));
  const span = Math.max(t1 - t0, 1);
  const spanHours = span / 3.6e6;
  const chartW = Math.max(480, Math.min(1200, Math.round(spanHours * 96)));
  const x = (ms: number) => LABEL_W + ((ms - t0) / span) * chartW;

  const modelOrder: string[] = [];
  const modelEqps: Record<string, string[]> = {};
  for (const s of segments) {
    if (!modelEqps[s.model]) { modelEqps[s.model] = []; modelOrder.push(s.model); }
    if (!modelEqps[s.model].includes(s.eqp_id)) modelEqps[s.model].push(s.eqp_id);
  }
  const uniqueModels = [...new Set(modelOrder)];
  uniqueModels.forEach((m) => modelEqps[m].sort());

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
  const allocByEqp = new Map(allocSummary.map((a) => [a.eqp_id, a]));

  const combos = [...new Set(segments.filter((s) => s.kind === "RUN").map(comboKey))];
  const color = colorScale(combos);

  const hourMs = 3.6e6;
  const hours = Math.ceil(span / hourMs);
  const tickStep = hours > 18 ? Math.ceil(hours / 18) : 1;
  const ticks: number[] = [];
  for (let t = t0; t <= t1 + 1; t += hourMs * tickStep) ticks.push(t);

  return (
    <div className="gantt-wrap">
      {(wipSummary.length > 0 || allocSummary.length > 0) && (
        <div className="gantt-meta">
          {wipSummary.length > 0 && (
            <div className="gantt-meta-block">
              <div className="gantt-meta-title">기존 재공</div>
              <div className="gantt-meta-items">
                {wipSummary.map((w) => (
                  <span key={w.task} className="gantt-meta-chip">
                    {w.task}: 재공 <b>{num(w.init_wip)}</b> / 계획 {num(w.plan_qty)}
                  </span>
                ))}
              </div>
            </div>
          )}
          {allocSummary.length > 0 && (
            <div className="gantt-meta-block">
              <div className="gantt-meta-title">초기 할당</div>
              <div className="gantt-meta-items">
                {allocSummary.map((a) => (
                  <span
                    key={a.eqp_id}
                    className={`gantt-meta-chip${a.allocated ? "" : " unalloc"}`}
                  >
                    {a.eqp_id}: {a.allocated ? a.task || a.batch_id : "미할당"}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      <svg viewBox={`0 0 ${totalWidth} ${totalHeight}`} className="gantt-svg" role="img">
        <defs>
          <pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <line x1="0" y1="0" x2="0" y2="6" stroke="#d6492a" strokeWidth="2" strokeOpacity="0.5" />
          </pattern>
          <pattern id="wip-hatch" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <line x1="0" y1="0" x2="0" y2="5" stroke="#c98a00" strokeWidth="1.5" strokeOpacity="0.55" />
          </pattern>
          <pattern id="unalloc-hatch" width="5" height="5" patternUnits="userSpaceOnUse">
            <line x1="0" y1="0" x2="5" y2="5" stroke="#9aa5b5" strokeWidth="1" strokeOpacity="0.6" />
          </pattern>
        </defs>

        {ticks.map((t) => (
          <g key={t}>
            <line x1={x(t)} y1={AXIS_H - 4} x2={x(t)} y2={totalHeight - 6} stroke="#e1e6ef" />
            <text x={x(t) + 3} y={AXIS_H - 10} fill="#6b7689" fontSize={11}>
              {fmtTime(new Date(t).toISOString())}
            </text>
          </g>
        ))}

        {groupHeaders.map(({ model, y }) => (
          <g key={`grp-${model}`}>
            <rect x={0} y={y} width={totalWidth} height={GROUP_H} fill="#eef1f8" />
            <text x={8} y={y + GROUP_H / 2 + 4} fill="#3b6fe0" fontSize={12} fontWeight={700}>
              {model}
            </text>
          </g>
        ))}

        {rows.map(({ eqp_id, y }, i) => {
          const alloc = allocByEqp.get(eqp_id);
          return (
            <g key={eqp_id}>
              <rect x={0} y={y} width={totalWidth} height={ROW_H} fill={i % 2 ? "#f3f6fb" : "none"} />
              <text x={8} y={y + ROW_H / 2 + 4} fill="#1f2733" fontSize={12} fontWeight={500}>
                {eqp_id}
              </text>
              {alloc && (
                <text x={LABEL_W - 6} y={y + ROW_H / 2 + 4} textAnchor="end" fill="#6b7689" fontSize={9}>
                  {alloc.allocated ? "할당" : "미할당"}
                </text>
              )}
            </g>
          );
        })}

        {segments.filter((s) => s.kind === "UNALLOC").map((s, idx) => {
          const rowY = eqpYMap.get(s.eqp_id);
          if (rowY == null) return null;
          const by = rowY + (ROW_H - BAR_H) / 2;
          const x0 = x(+new Date(s.start));
          const w = Math.max(x(+new Date(s.end)) - x0, 2);
          return (
            <g key={`unalloc-${idx}`}>
              <rect x={x0} y={by} width={w} height={BAR_H} rx={4} fill="url(#unalloc-hatch)" stroke="#9aa5b5" strokeWidth={1}>
                <title>{`${s.eqp_id} (${s.model})\n미할당 · ${fmtTime(s.start)} ~ ${fmtTime(s.end)}`}</title>
              </rect>
              {w > 40 && (
                <text x={x0 + w / 2} y={by + BAR_H / 2 + 4} fill="#6b7689" fontSize={9} fontWeight={600} textAnchor="middle" pointerEvents="none">
                  미할당
                </text>
              )}
            </g>
          );
        })}

        {segments.filter((s) => s.kind === "IDLE").map((s, idx) => {
          const rowY = eqpYMap.get(s.eqp_id);
          if (rowY == null) return null;
          const by = rowY + (ROW_H - BAR_H) / 2;
          const x0 = x(+new Date(s.start));
          const w = Math.max(x(+new Date(s.end)) - x0, 2);
          const label = idleLabel(s);
          return (
            <g key={`idle-${idx}`}>
              <rect x={x0} y={by} width={w} height={BAR_H} rx={4} fill="url(#wip-hatch)" stroke="#c98a00" strokeWidth={1.2} strokeDasharray="3 2">
                <title>{`${s.eqp_id} (${s.model})\n할당: ${s.task}\n재공: ${num(s.wip ?? 0)}\n${s.idle_reason === "WIP_ZERO" ? "재공 없음" : "생산 없음"}\n${fmtTime(s.start)} ~ ${fmtTime(s.end)}`}</title>
              </rect>
              {w > 36 && (
                <text x={x0 + w / 2} y={by + BAR_H / 2 + 4} fill="#a06a00" fontSize={9} fontWeight={700} textAnchor="middle" pointerEvents="none">
                  {label}
                </text>
              )}
            </g>
          );
        })}

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
          <span className="swatch" style={{ background: "url(#wip-hatch)", border: "1.2px dashed #c98a00", borderRadius: 3 }} />
          재공 없음(IDLE)
        </span>
        <span className="item">
          <span className="swatch" style={{ background: "url(#unalloc-hatch)", border: "1px solid #9aa5b5", borderRadius: 3 }} />
          미할당
        </span>
        <span className="item">
          <span className="swatch" style={{ background: "url(#hatch)", border: "1.5px dashed #d6492a", borderRadius: 3 }} />
          <span style={{ borderLeft: "3px solid #d6492a", paddingLeft: 4 }}>전환(CONV)</span>
        </span>
      </div>
    </div>
  );
}
