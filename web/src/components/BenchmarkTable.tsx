import type { SummaryRow } from "../types";
import { pct } from "../api";

interface Props {
  rows: SummaryRow[];
  selected: string;
  onSelect: (name: string) => void;
}

function MiniBar({ value, color }: { value: number | null; color: string }) {
  if (value == null) return <span style={{ color: "#aaa", fontSize: 11 }}>N/A</span>;
  const pct = Math.round(value * 100);
  return (
    <div className="bench-bar-row">
      <div className="bench-bar-track">
        <div className="bench-bar-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span style={{ minWidth: 36, textAlign: "right" }}>{pct}%</span>
    </div>
  );
}

export default function BenchmarkTable({ rows, selected, onSelect }: Props) {
  if (rows.length === 0) return <div className="empty">벤치마크가 없습니다.</div>;

  return (
    <ul className="bench-list">
      {rows.map((r) => (
        <li
          key={r.name}
          className={r.name === selected ? "active" : ""}
          onClick={() => onSelect(r.name)}
        >
          <div className="name">{r.name}</div>
          <div className="meta">
            Tasks {r.task_count} · EQP {r.total_eqp} · {r.horizon_hours}h
            {r.has_real_equipments
              ? <span style={{ color: "#18a06c", marginLeft: 4 }}>●실제호기</span>
              : <span style={{ color: "#c98a00", marginLeft: 4 }}>●가상호기</span>}
          </div>
          <div className="bench-bars">
            {r.optimal != null && (
              <MiniBar value={r.optimal} color="#18a06c" />
            )}
            <MiniBar value={r.heuristic} color="#3b6fe0" />
            {r.rl != null && <MiniBar value={r.rl} color="#9270ca" />}
          </div>
          <div style={{ display: "flex", gap: 8, marginTop: 4, fontSize: 10, color: "#6b7689" }}>
            {r.optimal != null && <span style={{ color: "#18a06c" }}>■최적 {pct(r.optimal)}</span>}
            <span style={{ color: "#3b6fe0" }}>■H {pct(r.heuristic)}</span>
            {r.rl != null && <span style={{ color: "#9270ca" }}>■RL {pct(r.rl)}</span>}
          </div>
        </li>
      ))}
    </ul>
  );
}
