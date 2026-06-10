import type { AlgoView } from "../types";
import { num, pct } from "../api";

interface Props {
  view: AlgoView;
  optimal: number | null;
  algoLabel: string;
}

export default function KpiCards({ view, optimal, algoLabel }: Props) {
  const k = view.kpis;
  const gap = optimal != null ? k.plan_achievement - optimal : null;
  return (
    <div className="kpi-grid">
      <div className="kpi">
        <div className="label">{algoLabel} 계획달성률</div>
        <div className="value">{pct(k.plan_achievement)}</div>
        {gap != null && (
          <div className={`delta ${gap >= 0 ? "pos" : "neg"}`}>
            {gap >= 0 ? "▲" : "▼"} {pct(Math.abs(gap))} vs 최적({pct(optimal)})
          </div>
        )}
      </div>
      <div className="kpi">
        <div className="label">평균 장비 가동률</div>
        <div className="value">{pct(k.avg_utilization)}</div>
      </div>
      <div className="kpi">
        <div className="label">move량 (총 생산)</div>
        <div className="value">{num(k.total_move)}</div>
      </div>
      <div className="kpi">
        <div className="label">전환 횟수</div>
        <div className="value">{num(k.conversion_count)}</div>
        <div className="delta muted">tool 교체(batch 변경) 기준</div>
      </div>
      <div className="kpi">
        <div className="label">전환 예정 장비 수</div>
        <div className="value">{num(k.converting_eqp_count)}</div>
        <div className="delta muted">전환이 1회 이상 걸린 호기</div>
      </div>
    </div>
  );
}
