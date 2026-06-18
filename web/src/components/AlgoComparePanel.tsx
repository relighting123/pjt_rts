import type { AlgoView, DatasetDetail, EquipmentInfo } from "../types";
import { isMeaningfulOptimal } from "../api";
import AllocationPivotTable from "./AllocationPivotTable";
import DispatchContextPanel from "./DispatchContextPanel";
import GanttChart from "./GanttChart";
import HourlyPlanChart from "./HourlyPlanChart";

interface Props {
  detail: DatasetDetail;
  envType: "dispatch" | "alloc";
  rlAvailable: boolean;
}

function initialAssignMap(equipments: EquipmentInfo[]): Record<string, string> {
  const map: Record<string, string> = {};
  for (const e of equipments) {
    if (e.plan_prod_key && e.oper_id) {
      map[e.eqp_id] = `${e.plan_prod_key}/${e.oper_id}`;
    }
  }
  return map;
}

function avgStaticRate(view: AlgoView | null | undefined): number | null {
  const rows = view?.allocation_pivot?.rows;
  if (!rows?.length) return null;
  return rows.reduce((s, r) => s + r.rate, 0) / rows.length;
}

function AlgoColumn({
  title,
  color,
  view,
  envType,
  optimal,
  initialAssign,
  tasks,
  horizonHours,
}: {
  title: string;
  color: string;
  view: AlgoView | null;
  envType: "dispatch" | "alloc";
  optimal: number | null;
  initialAssign: Record<string, string>;
  tasks: DatasetDetail["tasks"];
  horizonHours: number;
}) {
  if (!view) {
    return (
      <div className="algo-compare-col empty-col">
        <div className="algo-compare-head" style={{ borderColor: color }}>
          <span className="swatch" style={{ background: color }} />
          {title}
        </div>
        <div className="empty">데이터 없음</div>
      </div>
    );
  }

  const staticRate = view.kpis.static_plan_achievement ?? avgStaticRate(view);
  const dynamicRate = view.kpis.plan_achievement;

  return (
    <div className="algo-compare-col">
      <div className="algo-compare-head" style={{ borderColor: color }}>
        <span className="swatch" style={{ background: color }} />
        {title}
      </div>
      <div className="algo-compare-kpis">
        {envType === "alloc" ? (
          <>
            <span>정적 <b>{((staticRate ?? 0) * 100).toFixed(1)}%</b></span>
            <span>동적 <b>{(dynamicRate * 100).toFixed(1)}%</b></span>
          </>
        ) : (
          <span>달성률 <b>{(dynamicRate * 100).toFixed(1)}%</b></span>
        )}
        <span>가동률 <b>{(view.kpis.avg_utilization * 100).toFixed(1)}%</b></span>
        <span>생산 <b>{view.kpis.total_move.toLocaleString()}</b></span>
        <span>전환 <b>{view.kpis.conversion_count}건</b></span>
        {isMeaningfulOptimal(optimal) && (
          <span>최적 <b className="good">{(optimal! * 100).toFixed(1)}%</b></span>
        )}
      </div>
      {envType === "alloc" ? (
        <AllocationPivotTable pivot={view.allocation_pivot} />
      ) : (
        <div className="dispatch-algo-body">
          <HourlyPlanChart hourly={view.hourly} tasks={tasks} horizonHours={horizonHours} />
          <GanttChart segments={view.gantt} initialAssign={initialAssign} />
        </div>
      )}
    </div>
  );
}

/** 휴리스틱 vs RL 나란히 비교. */
export default function AlgoComparePanel({ detail, envType, rlAvailable }: Props) {
  const h = detail.algorithms.heuristic;
  const rl = detail.algorithms.rl;
  const initialAssign = initialAssignMap(detail.equipments);

  return (
    <div className={`algo-compare${envType === "dispatch" ? " dispatch" : ""}`}>
      {envType === "dispatch" && (
        <DispatchContextPanel
          tasks={detail.tasks}
          initAssign={detail.init_assign ?? []}
          equipments={detail.equipments}
        />
      )}
      <AlgoColumn
        title="휴리스틱"
        color="#3b6fe0"
        view={h}
        envType={envType}
        optimal={detail.optimal}
        initialAssign={initialAssign}
        tasks={detail.tasks}
        horizonHours={detail.meta.horizon_hours}
      />
      <AlgoColumn
        title="RL"
        color="#9270ca"
        view={rlAvailable ? rl : null}
        envType={envType}
        optimal={detail.optimal}
        initialAssign={initialAssign}
        tasks={detail.tasks}
        horizonHours={detail.meta.horizon_hours}
      />
      {!rlAvailable && (
        <div className="algo-compare-note">
          RL 결과 없음 — 학습된 모델이 없거나 shape가 맞지 않습니다.
        </div>
      )}
    </div>
  );
}
