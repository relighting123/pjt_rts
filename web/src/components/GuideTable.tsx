import type { GuideRow } from "../types";
import { num } from "../api";

interface Props {
  guide: GuideRow[];
}

/** 가이드 수량 (Mode 1) — 공정×모델 목표 대수 + Capa 매트릭스. */
export default function GuideTable({ guide }: Props) {
  if (guide.length === 0) return <div className="empty">가이드 배분 데이터가 없습니다.</div>;

  const tasks = [...new Set(guide.map((g) => g.task))];
  const models = [...new Set(guide.map((g) => g.model))].sort();
  const lookup = new Map(guide.map((g) => [`${g.task}|${g.model}`, g]));
  const maxCount = Math.max(...guide.map((g) => g.target_count), 1);

  // 공정별 합산 capa & 달성률
  const taskSummary = new Map<string, { plan_qty: number; total_capacity: number }>();
  for (const g of guide) {
    const cur = taskSummary.get(g.task) ?? { plan_qty: g.plan_qty, total_capacity: 0 };
    cur.total_capacity += g.capacity;
    taskSummary.set(g.task, cur);
  }

  return (
    <table className="data" style={{ fontSize: 12 }}>
      <thead>
        <tr>
          <th>공정(PLAN_PROD_KEY/OPER)</th>
          {models.map((m) => (
            <th key={m} className="num" colSpan={2}>{m}</th>
          ))}
          <th className="num">계획수량</th>
          <th className="num">합산Capa</th>
          <th className="num">달성률</th>
        </tr>
        <tr style={{ background: "#f5f7fa", fontSize: 11, color: "#6b7689" }}>
          <th></th>
          {models.map((m) => (
            <>
              <th key={`${m}-cnt`} className="num">대수</th>
              <th key={`${m}-cap`} className="num">Capa</th>
            </>
          ))}
          <th></th><th></th><th></th>
        </tr>
      </thead>
      <tbody>
        {tasks.map((t) => {
          const summary = taskSummary.get(t)!;
          const rate = summary.plan_qty > 0
            ? Math.min(summary.total_capacity, summary.plan_qty) / summary.plan_qty
            : 1.0;
          const ratePct = (rate * 100).toFixed(1) + "%";
          const rateColor = rate >= 1.0 ? "#1a8a45" : rate >= 0.8 ? "#e0a400" : "#c0392b";
          return (
            <tr key={t}>
              <td>{t}</td>
              {models.map((m) => {
                const row = lookup.get(`${t}|${m}`);
                const cnt = row?.target_count ?? 0;
                const cap = row?.capacity ?? 0;
                const alpha = cnt / maxCount;
                const bg = cnt > 0 ? `rgba(59,111,224,${0.08 + alpha * 0.25})` : undefined;
                return (
                  <>
                    <td key={`${m}-cnt`} className="num" style={{ background: bg }}>
                      {cnt > 0 ? cnt : "–"}
                    </td>
                    <td key={`${m}-cap`} className="num" style={{ background: bg, color: "#555" }}>
                      {cap > 0 ? num(Math.round(cap)) : "–"}
                    </td>
                  </>
                );
              })}
              <td className="num">{num(summary.plan_qty)}</td>
              <td className="num">{num(Math.round(summary.total_capacity))}</td>
              <td className="num" style={{ fontWeight: 600, color: rateColor }}>{ratePct}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
