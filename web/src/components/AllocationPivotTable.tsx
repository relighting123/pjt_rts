import type { AllocationPivot } from "../types";
import { num, pct } from "../api";

interface Props {
  pivot: AllocationPivot;
}

function cell(v: number | null | undefined, digits = 0) {
  if (v == null) return <span className="na">—</span>;
  return digits > 0 ? v.toFixed(digits) : num(v);
}

/** 제품/공정 × 모델 피벗 — 댓수 · UPD · 계획 · 달성률. */
export default function AllocationPivotTable({ pivot }: Props) {
  const { models, rows } = pivot;
  if (rows.length === 0) return <div className="empty">배분 데이터가 없습니다.</div>;

  const maxCount = Math.max(
    ...rows.flatMap((r) => models.map((m) => r.counts[m] ?? 0)),
    1,
  );

  return (
    <div className="alloc-pivot-wrap">
      <table className="data alloc-pivot">
        <thead>
          <tr>
            <th rowSpan={2}>제품/공정</th>
            <th colSpan={models.length} className="group-head count-head">장비 댓수</th>
            <th colSpan={models.length} className="group-head upd-head">UPD</th>
            <th rowSpan={2} className="num">계획</th>
            <th rowSpan={2} className="num">정적 달성률</th>
          </tr>
          <tr>
            {models.map((m) => <th key={`c-${m}`} className="num sub">{m}</th>)}
            {models.map((m) => <th key={`u-${m}`} className="num sub">{m}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.task}>
              <td className="task-cell">{r.task}</td>
              {models.map((m) => {
                const v = r.counts[m];
                const alpha = v != null && v > 0 ? v / maxCount : 0;
                return (
                  <td key={`c-${r.task}-${m}`} className="num"
                      style={{ background: v != null && v > 0 ? `rgba(59,111,224,${0.06 + alpha * 0.22})` : undefined }}>
                    {cell(v)}
                  </td>
                );
              })}
              {models.map((m) => (
                <td key={`u-${r.task}-${m}`} className="num upd-cell">
                  {cell(r.uphs[m], 0)}
                </td>
              ))}
              <td className="num">{num(r.plan)}</td>
              <td className="num rate-cell" style={{ color: r.rate >= 1 ? "var(--good)" : undefined }}>
                {pct(r.rate)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
