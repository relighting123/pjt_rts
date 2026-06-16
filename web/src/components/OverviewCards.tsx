import type { Summary } from "../types";
import { pct } from "../api";

interface Props {
  summary: Summary;
  envType: "dispatch" | "alloc";
}

export default function OverviewCards({ summary, envType }: Props) {
  const avg = summary.averages;
  const isAlloc = envType === "alloc";
  const cards = [
    {
      label: isAlloc ? "평균 계획달성률 (정적)" : "평균 계획달성률 (동적)",
      value: pct(avg.heuristic),
      sub: avg.rl != null ? `RL: ${pct(avg.rl)}` : "RL 모델 없음",
      hint: isAlloc
        ? "시간한계(댓수×UPD×H) 또는 배분밀도(댓수×UPD) / 계획"
        : "시뮬레이션 종료 시 실제 생산량 / 계획",
    },
    {
      label: "평균 가동률 (동적)",
      value: pct(avg.avg_utilization),
      sub: `${summary.rows.length}개 벤치마크 평균`,
      hint: "시뮬레이션 기준 장비 가동률",
    },
    {
      label: "평균 장비 전환 횟수 (동적)",
      value: avg.avg_conversion_count != null
        ? avg.avg_conversion_count.toFixed(1) + "회"
        : "N/A",
      sub: "전환(CONV) 세그먼트 수",
      hint: "시뮬레이션 기준 전환 건수",
    },
  ];

  return (
    <div className="overview-cards">
      {cards.map((c) => (
        <div className="kpi-card" key={c.label} title={c.hint}>
          <div className="label">{c.label}</div>
          <div className="value">{c.value}</div>
          <div className="sub">{c.sub}</div>
        </div>
      ))}
    </div>
  );
}
