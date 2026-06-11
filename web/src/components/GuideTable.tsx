import type { GuideRow } from "../types";

interface Props {
  guide: GuideRow[];
}

/** 가이드 수량 (Mode 1) — 공정×모델 목표 대수 매트릭스. */
export default function GuideTable({ guide }: Props) {
  if (guide.length === 0) return <div className="empty">가이드 배분 데이터가 없습니다.</div>;

  const tasks = [...new Set(guide.map((g) => g.task))];
  const models = [...new Set(guide.map((g) => g.model))].sort();
  const lookup = new Map(guide.map((g) => [`${g.task}|${g.model}`, g.target_count]));
  const max = Math.max(...guide.map((g) => g.target_count), 1);

  return (
    <table className="data">
      <thead>
        <tr>
          <th>공정(PLAN_PROD_KEY/OPER)</th>
          {models.map((m) => <th key={m} className="num">{m}</th>)}
        </tr>
      </thead>
      <tbody>
        {tasks.map((t) => (
          <tr key={t}>
            <td>{t}</td>
            {models.map((m) => {
              const v = lookup.get(`${t}|${m}`) ?? 0;
              const alpha = v / max;
              return (
                <td key={m} className="num"
                    style={{ background: v > 0 ? `rgba(59,111,224,${0.08 + alpha * 0.25})` : undefined }}>
                  {v}
                </td>
              );
            })}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
