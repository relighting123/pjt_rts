import { useCallback, useEffect, useMemo, useState } from "react";
import type { GanttSegment } from "../types";
import { colorScale, fmtTime, num } from "../api";

interface Props {
  segments: GanttSegment[];
  /** eqp_id → 초기 제품/공정 라벨 */
  initialAssign?: Record<string, string>;
  /** 외부에서 줌 배율 제어 (미지정 시 내부 상태) */
  zoom?: number;
  onZoomChange?: (z: number) => void;
  /** 툴바/확대 버튼 숨김 (모달 내부 재사용 시) */
  compact?: boolean;
}

const ROW_H = 36;
const BAR_H = 24;
const LABEL_W = 168;
const GROUP_H = 22;
const AXIS_H = 28;
const ZOOM_LEVELS = [0.75, 1, 1.5, 2, 3, 4];

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

function GanttSvg({
  segments,
  initialAssign,
  zoom,
}: {
  segments: GanttSegment[];
  initialAssign?: Record<string, string>;
  zoom: number;
}) {
  const t0 = Math.min(...segments.map((s) => +new Date(s.start)));
  const t1 = Math.max(...segments.map((s) => +new Date(s.end)));
  const span = Math.max(t1 - t0, 1);
  const spanHours = span / 3.6e6;
  const baseW = Math.max(480, Math.min(1200, Math.round(spanHours * 96)));
  const chartW = Math.round(baseW * zoom);
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

  const combos = [...new Set(segments.filter((s) => s.kind === "RUN").map(comboKey))];
  const color = colorScale(combos);

  const hourMs = 3.6e6;
  const hours = Math.ceil(span / hourMs);
  const tickStep = hours > 18 ? Math.ceil(hours / 18) : 1;
  const ticks: number[] = [];
  for (let t = t0; t <= t1 + 1; t += hourMs * tickStep) ticks.push(t);

  return (
    <svg viewBox={`0 0 ${totalWidth} ${totalHeight}`} className="gantt-svg" role="img">
      <defs>
        <pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <line x1="0" y1="0" x2="0" y2="6" stroke="#d6492a" strokeWidth="2" strokeOpacity="0.5" />
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
        const init = initialAssign?.[eqp_id];
        return (
          <g key={eqp_id}>
            <rect x={0} y={y} width={totalWidth} height={ROW_H} fill={i % 2 ? "#f3f6fb" : "none"} />
            <text x={8} y={y + (init ? 14 : ROW_H / 2 + 4)} fill="#1f2733" fontSize={12} fontWeight={500}>
              {eqp_id}
            </text>
            {init && (
              <text x={8} y={y + 28} fill="#6b7689" fontSize={9}>
                초기: {init}
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
  );
}

function GanttLegend({ segments }: { segments: GanttSegment[] }) {
  const combos = useMemo(
    () => [...new Set(segments.filter((s) => s.kind === "RUN").map(comboKey))].sort(),
    [segments],
  );
  const color = colorScale(combos);
  return (
    <div className="legend">
      {combos.map((k) => (
        <span className="item" key={k}>
          <span className="swatch" style={{ background: color(k) }} /> {k}
        </span>
      ))}
      <span className="item">
        <span className="swatch" style={{ background: "url(#hatch)", border: "1.5px dashed #d6492a", borderRadius: 3 }} />
        <span style={{ borderLeft: "3px solid #d6492a", paddingLeft: 4 }}>전환(CONV)</span>
      </span>
    </div>
  );
}

export default function GanttChart({
  segments,
  initialAssign,
  zoom: zoomProp,
  onZoomChange,
  compact = false,
}: Props) {
  const [internalZoom, setInternalZoom] = useState(1);
  const [expanded, setExpanded] = useState(false);
  const zoom = zoomProp ?? internalZoom;

  const setZoom = useCallback((z: number) => {
    const clamped = Math.max(ZOOM_LEVELS[0], Math.min(ZOOM_LEVELS[ZOOM_LEVELS.length - 1], z));
    if (onZoomChange) onZoomChange(clamped);
    else setInternalZoom(clamped);
  }, [onZoomChange]);

  const stepZoom = (dir: -1 | 1) => {
    const idx = ZOOM_LEVELS.findIndex((z) => z >= zoom - 1e-6);
    const cur = idx < 0 ? 1 : idx;
    const next = Math.max(0, Math.min(ZOOM_LEVELS.length - 1, cur + dir));
    setZoom(ZOOM_LEVELS[next]);
  };

  useEffect(() => {
    if (!expanded) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setExpanded(false); };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [expanded]);

  if (segments.length === 0) return <div className="empty">배치 데이터가 없습니다.</div>;

  const body = (
    <>
      <div className="gantt-wrap">
        <GanttSvg segments={segments} initialAssign={initialAssign} zoom={zoom} />
      </div>
      <GanttLegend segments={segments} />
    </>
  );

  if (compact) {
    return <div className="gantt-chart-inner">{body}</div>;
  }

  return (
    <div className="gantt-chart">
      <div className="gantt-toolbar">
        <span className="gantt-toolbar-label">간트차트</span>
        <div className="gantt-zoom-controls">
          <button type="button" className="gantt-btn" onClick={() => stepZoom(-1)} title="축소" aria-label="축소">−</button>
          <span className="gantt-zoom-pct">{Math.round(zoom * 100)}%</span>
          <button type="button" className="gantt-btn" onClick={() => stepZoom(1)} title="확대" aria-label="확대">+</button>
          <button type="button" className="gantt-btn" onClick={() => setZoom(1)} title="원본 크기">100%</button>
          <button type="button" className="gantt-btn primary" onClick={() => setExpanded(true)} title="확대 보기">
            ⛶ 확대
          </button>
        </div>
      </div>
      {body}
      {expanded && (
        <div className="gantt-modal-overlay" onClick={() => setExpanded(false)} role="presentation">
          <div className="gantt-modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true" aria-label="간트차트 확대 보기">
            <div className="gantt-modal-head">
              <h3>간트차트 확대 보기</h3>
              <div className="gantt-zoom-controls">
                <button type="button" className="gantt-btn" onClick={() => stepZoom(-1)}>−</button>
                <span className="gantt-zoom-pct">{Math.round(zoom * 100)}%</span>
                <button type="button" className="gantt-btn" onClick={() => stepZoom(1)}>+</button>
                <button type="button" className="gantt-btn" onClick={() => setZoom(1)}>100%</button>
                <button type="button" className="gantt-btn" onClick={() => setExpanded(false)}>닫기 ✕</button>
              </div>
            </div>
            <div className="gantt-modal-body">
              <div className="gantt-wrap gantt-wrap-modal">
                <GanttSvg segments={segments} initialAssign={initialAssign} zoom={zoom} />
              </div>
              <GanttLegend segments={segments} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
