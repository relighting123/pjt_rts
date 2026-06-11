import type { Summary } from "../types";
import { num, pct } from "../api";

interface Props {
  summary: Summary;
  onSelect: (name: string) => void;
}

/** 전체 데이터셋 비교 — 평균 KPI + 달성률 비교 테이블. */
export default function SummaryView({ summary, onSelect }: Props) {
  const a = summary.averages;
  return (
    <>
      <div className="summary-cards">
        <div className="kpi">
          <div className="label">평균 휴리스틱 달성률</div>
          <div className="value">{pct(a.heuristic)}</div>
        </div>
        <div className="kpi">
          <div className="label">평균 RL 달성률</div>
          <div className="value">{pct(a.rl)}</div>
        </div>
        <div className="kpi">
          <div className="label">평균 최적 달성률</div>
          <div className="value">{pct(a.optimal)}</div>
        </div>
        <div className="kpi">
          <div className="label">평균 Gap (−최적)</div>
          <div className="value">{a.gap == null ? "N/A" : `${a.gap >= 0 ? "+" : ""}${(a.gap * 100).toFixed(1)}%`}</div>
        </div>
        <div className="kpi">
          <div className="label">평균 장비 가동률</div>
          <div className="value">{pct(a.avg_utilization)}</div>
        </div>
      </div>

      <div className="panel">
        <h2>데이터셋별 비교 <span className="sub">행 클릭 시 상세 보기</span></h2>
        <table className="data">
          <thead>
            <tr>
              <th>데이터셋</th>
              <th style={{ width: "22%" }}>달성률 (휴리스틱 / RL / 최적)</th>
              <th className="num">휴리스틱</th>
              <th className="num">RL</th>
              <th className="num">최적</th>
              <th className="num">Gap</th>
              <th className="num">가동률</th>
              <th className="num">move량</th>
              <th className="num">전환</th>
              <th className="num">horizon</th>
              <th className="num">tasks</th>
              <th className="num">장비</th>
              <th>호기 매핑</th>
            </tr>
          </thead>
          <tbody>
            {summary.rows.map((r) => (
              <tr key={r.name} style={{ cursor: "pointer" }} onClick={() => onSelect(r.name)}>
                <td><b>{r.name}</b></td>
                <td>
                  <MiniBars heuristic={r.heuristic} rl={r.rl} optimal={r.optimal} />
                </td>
                <td className="num">{pct(r.heuristic)}</td>
                <td className="num">{pct(r.rl)}</td>
                <td className="num">{pct(r.optimal)}</td>
                <td className="num" style={{ color: r.gap == null ? undefined : r.gap >= 0 ? "var(--good)" : "var(--bad)" }}>
                  {r.gap == null ? "N/A" : `${r.gap >= 0 ? "+" : ""}${(r.gap * 100).toFixed(1)}%`}
                </td>
                <td className="num">{pct(r.avg_utilization)}</td>
                <td className="num">{num(r.total_move)}</td>
                <td className="num">{num(r.conversion_count)}</td>
                <td className="num">{r.horizon_hours}h</td>
                <td className="num">{r.task_count}</td>
                <td className="num">{r.total_eqp}</td>
                <td>
                  {r.has_real_equipments
                    ? <span className="badge real">실제 호기</span>
                    : <span className="badge virtual">가상 호기</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function MiniBars({ heuristic, rl, optimal }: { heuristic: number | null; rl: number | null; optimal: number | null }) {
  const rows: Array<[string, number | null, string]> = [
    ["H", heuristic, "#3b6fe0"],
    ["RL", rl, "#18a06c"],
    ["OPT", optimal, "#d6492a"],
  ];
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
      {rows.filter(([, v]) => v != null).map(([label, v, color]) => (
        <div key={label} style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ width: 26, fontSize: 10, color: "var(--muted)" }}>{label}</span>
          <div className="rate-bar" style={{ height: 6 }}>
            <div style={{ width: `${Math.min(v as number, 1) * 100}%`, background: color }} />
          </div>
        </div>
      ))}
    </div>
  );
}
