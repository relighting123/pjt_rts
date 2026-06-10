import type { PerTask } from "../types";
import { num, pct } from "../api";

interface Props {
  perTask: PerTask[];
}

function barColor(rate: number) {
  if (rate >= 0.999) return "var(--good)";
  if (rate >= 0.7) return "var(--warn)";
  return "var(--bad)";
}

/** Task(PLAN_PROD_KEY/OPER)별 계획달성률 가로 바. */
export default function TaskAchievement({ perTask }: Props) {
  if (perTask.length === 0) return <div className="empty">Task 데이터가 없습니다.</div>;
  return (
    <table className="data">
      <thead>
        <tr>
          <th>PLAN_PROD_KEY/OPER</th>
          <th className="num">계획</th>
          <th className="num">생산</th>
          <th style={{ width: "40%" }}>달성률</th>
        </tr>
      </thead>
      <tbody>
        {perTask.map((t) => (
          <tr key={t.task}>
            <td>{t.task}</td>
            <td className="num">{num(t.plan)}</td>
            <td className="num">{num(t.produced)}</td>
            <td>
              <div className="rate-cell">
                <div className="rate-bar">
                  <div style={{ width: `${Math.min(t.rate, 1) * 100}%`, background: barColor(t.rate) }} />
                </div>
                <span style={{ minWidth: 52, textAlign: "right" }}>{pct(t.rate)}</span>
              </div>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
