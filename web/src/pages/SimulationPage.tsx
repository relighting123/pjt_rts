import { useCallback, useEffect, useRef, useState } from "react";
import { fetchDatasets, pct, simAdvance, simDelete, simMove, simReset, simStart } from "../api";
import type { DatasetInfo, SimAssignRow, SimMove, SimState, SimWipRow } from "../types";
import GanttChart from "../components/GanttChart";

const AUTO_INTERVAL_MS = 800;

// ── WIP 테이블 ─────────────────────────────────────────────────────────
function WipTable({ rows }: { rows: SimWipRow[] }) {
  return (
    <table className="data-table" style={{ fontSize: 12 }}>
      <thead>
        <tr>
          <th>Task</th>
          <th style={{ textAlign: "right" }}>WIP</th>
          <th style={{ textAlign: "right" }}>생산</th>
          <th style={{ textAlign: "right" }}>계획</th>
          <th style={{ textAlign: "right" }}>달성</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.task_index}>
            <td style={{ fontFamily: "monospace", fontSize: 11 }}>{r.task}</td>
            <td style={{ textAlign: "right" }}>{r.wip.toLocaleString()}</td>
            <td style={{ textAlign: "right" }}>{r.produced.toLocaleString()}</td>
            <td style={{ textAlign: "right" }}>{r.plan.toLocaleString()}</td>
            <td style={{ textAlign: "right" }}>
              <span style={{ color: r.rate >= 1 ? "var(--good)" : r.rate >= 0.7 ? "var(--warn)" : "var(--bad)" }}>
                {pct(r.rate, 1)}
              </span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// ── 배치 테이블 ────────────────────────────────────────────────────────
function AssignTable({ rows }: { rows: SimAssignRow[] }) {
  return (
    <table className="data-table" style={{ fontSize: 12 }}>
      <thead>
        <tr>
          <th>모델</th>
          <th>Task</th>
          <th style={{ textAlign: "right" }}>대수</th>
          <th style={{ textAlign: "right" }}>전환중</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={i}>
            <td style={{ fontWeight: 600 }}>{r.model}</td>
            <td style={{ fontFamily: "monospace", fontSize: 11 }}>{r.task}</td>
            <td style={{ textAlign: "right" }}>{r.count}</td>
            <td style={{ textAlign: "right" }}>
              {r.switching > 0 ? (
                <span style={{ color: "var(--warn)" }}>{r.switching}h</span>
              ) : (
                <span style={{ color: "var(--muted)" }}>—</span>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// ── 이동 버튼 패널 ─────────────────────────────────────────────────────
function MovePanel({
  moves,
  onMove,
  disabled,
}: {
  moves: SimMove[];
  onMove: (mv: SimMove) => void;
  disabled: boolean;
}) {
  if (moves.length === 0) {
    return <div className="empty" style={{ padding: "12px 0" }}>가능한 이동 없음</div>;
  }

  // from_task 기준 그룹화
  const grouped: Record<string, SimMove[]> = {};
  for (const mv of moves) {
    (grouped[mv.from_task] ??= []).push(mv);
  }

  return (
    <div className="sim-moves">
      {Object.entries(grouped).map(([from, mvs]) => (
        <div key={from} className="sim-move-group">
          <div className="sim-move-from">{from}</div>
          <div className="sim-move-targets">
            {mvs.map((mv, i) => (
              <button
                key={i}
                type="button"
                className="sim-move-btn"
                disabled={disabled}
                onClick={() => onMove(mv)}
                title={`[${mv.model}] ${mv.from_task} → ${mv.to_task}`}
              >
                <span className="sim-move-model">{mv.model}</span>
                <span className="sim-move-arrow">→</span>
                <span className="sim-move-to">{mv.to_task}</span>
              </button>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

// ── 진행 바 ────────────────────────────────────────────────────────────
function ProgressBar({ hour, total }: { hour: number; total: number }) {
  const pct = total > 0 ? (hour / total) * 100 : 0;
  return (
    <div className="sim-progress-wrap">
      <div className="sim-progress-bar" style={{ width: `${pct}%` }} />
      <span className="sim-progress-label">
        {hour} / {total} h
      </span>
    </div>
  );
}

// ── 메인 페이지 ────────────────────────────────────────────────────────
export default function SimulationPage() {
  const [datasets, setDatasets] = useState<DatasetInfo[]>([]);
  const [selected, setSelected] = useState("");
  const [simState, setSimState] = useState<SimState | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [playing, setPlaying] = useState(false);
  const playRef = useRef(false);
  const sidRef = useRef<string | null>(null);

  useEffect(() => {
    fetchDatasets()
      .then((ds) => {
        setDatasets(ds);
        if (ds.length > 0) setSelected(ds[0].name);
      })
      .catch((e) => setError(String(e)));
  }, []);

  // 세션 정리
  useEffect(() => {
    return () => {
      if (sidRef.current) simDelete(sidRef.current);
    };
  }, []);

  const handleStart = useCallback(async () => {
    if (!selected) return;
    if (sidRef.current) await simDelete(sidRef.current);
    setLoading(true);
    setError(null);
    setPlaying(false);
    playRef.current = false;
    try {
      const s = await simStart(selected);
      setSimState(s);
      setSessionId(s.session_id ?? null);
      sidRef.current = s.session_id ?? null;
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [selected]);

  const handleAdvance = useCallback(async () => {
    if (!sidRef.current) return;
    setLoading(true);
    try {
      const s = await simAdvance(sidRef.current);
      setSimState(s);
      if (s.is_done) {
        setPlaying(false);
        playRef.current = false;
      }
    } catch (e) {
      setError(String(e));
      setPlaying(false);
      playRef.current = false;
    } finally {
      setLoading(false);
    }
  }, []);

  const handleReset = useCallback(async () => {
    if (!sidRef.current) return;
    setPlaying(false);
    playRef.current = false;
    setLoading(true);
    try {
      const s = await simReset(sidRef.current);
      setSimState(s);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  const handleMove = useCallback(async (mv: SimMove) => {
    if (!sidRef.current) return;
    setLoading(true);
    try {
      const s = await simMove(sidRef.current, mv.model, mv.from_index, mv.to_index);
      setSimState(s);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  // Auto play
  useEffect(() => {
    if (!playing) { playRef.current = false; return; }
    playRef.current = true;

    const tick = async () => {
      if (!playRef.current || !sidRef.current) return;
      if (simState?.is_done) { setPlaying(false); return; }
      await handleAdvance();
      if (playRef.current) setTimeout(tick, AUTO_INTERVAL_MS);
    };
    setTimeout(tick, AUTO_INTERVAL_MS);
  }, [playing, handleAdvance, simState?.is_done]);

  const togglePlay = () => {
    if (simState?.is_done) return;
    setPlaying((p) => !p);
  };

  const hasSession = !!simState && !!sessionId;

  return (
    <div className="page">
      <header className="page-header row">
        <div>
          <h1>시뮬레이션 뷰어</h1>
          <p className="page-sub">스텝별 간트차트 변화 · 배치 이동 인터랙션</p>
        </div>
      </header>

      {error && <div className="error">⚠ {error}</div>}

      {/* 데이터셋 선택 + 시작 */}
      <div className="panel" style={{ marginBottom: 16 }}>
        <div className="row" style={{ gap: 10, flexWrap: "wrap" }}>
          <select
            className="select"
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
            disabled={loading}
            style={{ minWidth: 220 }}
          >
            {datasets.map((d) => (
              <option key={d.name} value={d.name}>
                {d.name} ({d.kind})
              </option>
            ))}
          </select>
          <button
            type="button"
            className="btn primary"
            onClick={handleStart}
            disabled={loading || !selected}
          >
            {hasSession ? "재시작" : "시뮬레이션 시작"}
          </button>
        </div>
      </div>

      {hasSession && simState && (
        <>
          {/* 컨트롤 바 */}
          <div className="panel sim-control-panel">
            <ProgressBar hour={simState.hour} total={simState.total_hours} />
            <div className="sim-controls">
              <button
                type="button"
                className="btn"
                onClick={handleAdvance}
                disabled={loading || playing || simState.is_done}
                title="1시간 진행"
              >
                ▶ Next Step
              </button>
              <button
                type="button"
                className={`btn ${playing ? "warn" : "primary"}`}
                onClick={togglePlay}
                disabled={loading || simState.is_done}
              >
                {playing ? "⏸ 일시정지" : "▶▶ 자동재생"}
              </button>
              <button
                type="button"
                className="btn"
                onClick={handleReset}
                disabled={loading}
              >
                ↺ 초기화
              </button>
              {simState.is_done && (
                <span className="badge good" style={{ alignSelf: "center" }}>
                  시뮬레이션 완료
                </span>
              )}
              {loading && (
                <span className="muted" style={{ alignSelf: "center", fontSize: 12 }}>
                  처리 중…
                </span>
              )}
            </div>
          </div>

          {/* 간트차트 */}
          <div className="panel">
            <h3 className="section-title">간트차트 (Hour 0 → {simState.hour})</h3>
            {simState.gantt.length > 0 ? (
              <GanttChart segments={simState.gantt} />
            ) : (
              <div className="empty">아직 진행된 시간이 없습니다. Next Step을 눌러 진행하세요.</div>
            )}
          </div>

          {/* 상태 패널: 배치 + WIP */}
          <div className="sim-state-grid">
            <div className="panel">
              <h3 className="section-title">현재 장비 배치</h3>
              {simState.assign.length > 0 ? (
                <AssignTable rows={simState.assign} />
              ) : (
                <div className="empty">배치 없음</div>
              )}
            </div>
            <div className="panel">
              <h3 className="section-title">WIP · 생산 현황</h3>
              <WipTable rows={simState.wip} />
            </div>
          </div>

          {/* 이동 선택 */}
          {!simState.is_done && (
            <div className="panel">
              <h3 className="section-title">
                이동 선택{" "}
                <span className="muted" style={{ fontSize: 12, fontWeight: 400 }}>
                  — 클릭 후 Next Step으로 반영
                </span>
              </h3>
              <MovePanel
                moves={simState.valid_moves}
                onMove={handleMove}
                disabled={loading || playing}
              />
            </div>
          )}
        </>
      )}

      {!hasSession && !loading && (
        <div className="empty" style={{ marginTop: 48 }}>
          데이터셋을 선택하고 시뮬레이션을 시작하세요.
        </div>
      )}
    </div>
  );
}
