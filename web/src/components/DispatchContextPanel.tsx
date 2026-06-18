import type { EquipmentInfo, InitAssignRow, TaskInfo } from "../types";
import { num } from "../api";

interface Props {
  tasks: TaskInfo[];
  initAssign: InitAssignRow[];
  equipments: EquipmentInfo[];
}

/** 기존 재공(WIP) 및 초기 장비 할당 현황. */
export default function DispatchContextPanel({ tasks, initAssign, equipments }: Props) {
  if (tasks.length === 0) return null;

  const eqpAssign = equipments.map((e) => ({
    eqp_id: e.eqp_id,
    model: e.eqp_model,
    task: `${e.plan_prod_key}/${e.oper_id}`,
    batch: e.batch_id,
  }));

  return (
    <div className="dispatch-context">
      <div className="dispatch-context-block">
        <h3 className="dispatch-context-title">기존 재공 (WIP)</h3>
        <div className="dispatch-context-scroll">
          <table className="data compact">
            <thead>
              <tr>
                <th>제품/공정</th>
                <th className="num">계획</th>
                <th className="num">재공</th>
                <th className="num">재공/계획</th>
              </tr>
            </thead>
            <tbody>
              {tasks.map((t) => {
                const task = `${t.plan_prod_key}/${t.oper_id}`;
                const ratio = t.plan_qty > 0 ? t.init_wip / t.plan_qty : null;
                return (
                  <tr key={task}>
                    <td>{task}</td>
                    <td className="num">{num(t.plan_qty)}</td>
                    <td className="num" style={{ color: t.init_wip === 0 ? "var(--warn)" : undefined }}>
                      {num(t.init_wip)}
                    </td>
                    <td className="num">
                      {ratio != null ? (ratio >= 1 ? "충분" : `${(ratio * 100).toFixed(0)}%`) : "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      <div className="dispatch-context-block">
        <h3 className="dispatch-context-title">기존 할당 (init_assign)</h3>
        <div className="dispatch-context-scroll">
          <table className="data compact">
            <thead>
              <tr>
                <th>모델</th>
                <th>제품/공정</th>
                <th className="num">댓수</th>
              </tr>
            </thead>
            <tbody>
              {initAssign.length === 0 ? (
                <tr>
                  <td colSpan={3} className="empty-cell">초기 할당 데이터 없음</td>
                </tr>
              ) : (
                initAssign.map((r) => (
                  <tr key={`${r.eqp_model}-${r.plan_prod_key}-${r.oper_id}`}>
                    <td>{r.eqp_model}</td>
                    <td>{r.plan_prod_key}/{r.oper_id}</td>
                    <td className="num">{num(r.count)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {eqpAssign.length > 0 && (
        <div className="dispatch-context-block wide">
          <h3 className="dispatch-context-title">호기별 초기 배치</h3>
          <div className="dispatch-context-scroll">
            <table className="data compact">
              <thead>
                <tr>
                  <th>호기</th>
                  <th>모델</th>
                  <th>제품/공정</th>
                  <th>배치</th>
                </tr>
              </thead>
              <tbody>
                {eqpAssign.map((e) => (
                  <tr key={e.eqp_id}>
                    <td><b>{e.eqp_id}</b></td>
                    <td>{e.model}</td>
                    <td>{e.task}</td>
                    <td>{e.batch || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
