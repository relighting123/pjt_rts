"""장비 전환 스케줄링 도메인 모델 + 1시간 step 시뮬레이터.

gym/sb3/DB에 의존하지 않는 순수 코어.
"""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple


class Move(NamedTuple):
    model: str
    from_index: int
    to_index: int


@dataclass(frozen=True)
class Equipment:
    """실제 장비 호기 1대 — 모델/호기ID/현재 BATCH_ID/PLAN_PROD_KEY(/OPER_ID)."""
    eqp_id: str
    eqp_model: str
    batch_id: str = ""
    plan_prod_key: str = ""
    oper_id: str = ""


def largest_remainder(fracs: list[float], total: int) -> list[int]:
    """비례 실수 배분 → 정수. 합계 = total (최대잉여법). 장비 1대 단위 이동과 맞춤."""
    floors = [int(f) for f in fracs]
    remainders = [(fracs[i] - floors[i], i) for i in range(len(fracs))]
    deficit = total - sum(floors)
    remainders.sort(reverse=True)
    for k in range(max(0, deficit)):
        floors[remainders[k][1]] += 1
    return floors


@dataclass(frozen=True)
class Task:
    plan_prod_key: str
    oper_id: str
    oper_seq: int
    batch_id: str
    plan_qty: int
    init_wip: int

    @property
    def wip_qty(self) -> int:
        """DB GBN_CD=AVAIL_WIP_QTY와 동일 의미. init_wip 별칭."""
        return self.init_wip


@dataclass
class ProblemInstance:
    rule_timekey: str
    horizon_hours: int
    switch_time_hours: int
    tasks: list[Task]
    _uph: dict[tuple[str, int], float]          # (model, task_index) -> uph
    eqp_qty: dict[str, int]                      # model -> total units
    init_assign: dict[tuple[str, int], int]      # (model, task_index) -> count
    tool_qty: dict[tuple[str, str], int]         # (batch_id, model) -> tools
    conv_groups: dict[str, list[str]]            # group_id -> [batch_id, ...]
    facid: str | None = None
    equipments: list[Equipment] = field(default_factory=list)  # 실제 호기 명단 (없으면 가상)
    ground_truth: dict = field(default_factory=dict)

    def uph_of(self, model: str, task_index: int) -> float | None:
        return self._uph.get((model, task_index))

    def batch_of(self, task_index: int) -> str:
        return self.tasks[task_index].batch_id

    def conv_group_of(self, batch_id: str) -> str | None:
        for gid, batches in self.conv_groups.items():
            if batch_id in batches:
                return gid
        return None

    def can_convert(self, from_batch: str, to_batch: str) -> bool:
        """conversion 그룹이 같아야 batch 전환 가능."""
        g = self.conv_group_of(from_batch)
        return g is not None and g == self.conv_group_of(to_batch)

    def next_task_index(self, task_index: int) -> int | None:
        """같은 plan_prod_key의 oper_seq+1 태스크 인덱스(없으면 None)."""
        t = self.tasks[task_index]
        for i, o in enumerate(self.tasks):
            if o.plan_prod_key == t.plan_prod_key and o.oper_seq == t.oper_seq + 1:
                return i
        return None

    def prev_task_index(self, task_index: int) -> int | None:
        """같은 plan_prod_key의 oper_seq-1 태스크 인덱스(없으면 None)."""
        t = self.tasks[task_index]
        for i, o in enumerate(self.tasks):
            if o.plan_prod_key == t.plan_prod_key and o.oper_seq == t.oper_seq - 1:
                return i
        return None

    def complete_guide_allocation(
        self, guide: dict[tuple[str, int], float | int],
    ) -> dict[tuple[str, int], int]:
        """UPH 가능한 모든 (model, task) 슬롯을 포함. 미배분은 0 (정수 대수)."""
        result: dict[tuple[str, int], int] = {}
        for model in self.models():
            for ti in range(len(self.tasks)):
                if self.uph_of(model, ti) is not None:
                    result[(model, ti)] = int(guide.get((model, ti), 0))
        return result

    def plan_target_allocation(self) -> dict[tuple[str, int], float]:
        """계획달성율 극대화를 위한 공정별 목표 장비 수(실수 · 내부용).

        weight[m,t] = plan_qty[t] / UPH[m,t]  →  eqp_qty[m]에 비례 배분.
        표시/가이드용은 plan_target_allocation_int() 사용.
        """
        result: dict[tuple[str, int], float] = {}
        for model in self.models():
            weights = {
                ti: t.plan_qty / uph
                for ti, t in enumerate(self.tasks)
                if (uph := self.uph_of(model, ti)) and uph > 0
            }
            total_w = sum(weights.values())
            if total_w <= 0:
                continue
            eqp = float(self.eqp_qty[model])
            for ti, w in weights.items():
                result[(model, ti)] = w / total_w * eqp
        return result

    def plan_target_allocation_int(self) -> dict[tuple[str, int], int]:
        """해석식 가이드 — 모델별 합계가 eqp_qty와 일치하는 정수 배분."""
        raw = self.plan_target_allocation()
        result: dict[tuple[str, int], int] = {}
        for model in self.models():
            tasks = [ti for ti in range(len(self.tasks)) if self.uph_of(model, ti) is not None]
            if not tasks:
                continue
            fracs = [raw.get((model, ti), 0.0) for ti in tasks]
            counts = largest_remainder(fracs, self.eqp_qty[model])
            for ti, cnt in zip(tasks, counts):
                result[(model, ti)] = cnt
        return result

    def models(self) -> list[str]:
        return sorted(self.eqp_qty)


@dataclass
class SimState:
    hour: int
    produced: dict[int, int]                  # task_index -> 누적 생산
    wip: dict[int, int]                        # task_index -> 현재 가용 유입재공
    assign: dict[tuple[str, int], int]         # (model, task_index) -> 배치 대수
    switching: dict[tuple[str, int], int]       # (model, task_index) -> 전환중 잔여 대수
    tool_used: dict[tuple[str, str], int]      # (batch_id, model) -> 사용중 tool


class Simulator:
    """1시간 단위로 전이하는 결정론적 시뮬레이터."""

    def __init__(self, problem: ProblemInstance):
        self.p = problem

    def reset(self) -> SimState:
        p = self.p
        wip = {i: t.init_wip for i, t in enumerate(p.tasks)}
        produced = {i: 0 for i in range(len(p.tasks))}
        assign = dict(p.init_assign)
        switching: dict[tuple[str, int], int] = {}
        tool_used: dict[tuple[str, str], int] = {}
        for (model, ti), cnt in assign.items():
            key = (p.batch_of(ti), model)
            tool_used[key] = tool_used.get(key, 0) + cnt
        return SimState(0, produced, wip, assign, switching, tool_used)

    def advance_hour(self, s: SimState) -> None:
        """배치된(Idle 아닌) 장비로 1시간 생산 후 WIP를 다음 공정으로 흘린다."""
        p = self.p
        inflow: dict[int, int] = {}
        for ti in range(len(p.tasks)):
            capacity = self.task_capacity(s, ti)
            q = int(min(capacity, s.wip[ti]))
            if q <= 0:
                continue
            s.produced[ti] += q
            s.wip[ti] -= q
            nxt = p.next_task_index(ti)
            if nxt is not None:
                inflow[nxt] = inflow.get(nxt, 0) + q
        # 생산분은 다음 시간에 가용 (지금 더해두면 다음 advance에서 읽힘)
        for ti, v in inflow.items():
            s.wip[ti] += v
        # 전환중 잔여 차감: 배치된 장비 대수만큼 소진 (N대 동시 전환 시 N배 누적 해소)
        for key in list(s.switching):
            model, ti = key
            machines_here = s.assign.get((model, ti), 0)
            s.switching[key] = max(0, s.switching[key] - machines_here)
            if s.switching[key] == 0:
                del s.switching[key]
        s.hour += 1

    def is_done(self, s: SimState) -> bool:
        return s.hour >= self.p.horizon_hours

    def metrics(self, s: SimState) -> dict:
        p = self.p
        rates = []
        per_task = {}
        for i, t in enumerate(p.tasks):
            rate = min(s.produced[i] / t.plan_qty, 1.0) if t.plan_qty > 0 else 1.0
            rates.append(rate)
            per_task[f"{t.plan_prod_key}/{t.oper_id}"] = {
                "produced": s.produced[i], "plan": t.plan_qty, "rate": round(rate, 4)
            }
        return {
            "plan_achievement": round(sum(rates) / len(rates), 4) if rates else 0.0,
            "per_task": per_task,
        }

    def valid_moves(self, s: SimState) -> list[Move]:
        """현재 상태에서 둘 수 있는 (model, from, to) 이동 목록."""
        p = self.p
        out: list[Move] = []
        n = len(p.tasks)
        for model in p.models():
            for fi in range(n):
                # 옮길 수 있는 (Idle 아닌) 대수가 있어야 함
                movable = s.assign.get((model, fi), 0) - s.switching.get((model, fi), 0)
                if movable <= 0:
                    continue
                for ti in range(n):
                    if ti == fi:
                        continue
                    if p.uph_of(model, ti) is None:        # 적격(UPH 존재)해야
                        continue
                    fb, tb = p.batch_of(fi), p.batch_of(ti)
                    if fb != tb:
                        if not p.can_convert(fb, tb):       # 그룹 외 전환 불가
                            continue
                        used = s.tool_used.get((tb, model), 0)
                        cap = p.tool_qty.get((tb, model), 0)
                        if used >= cap:                     # tool 부족
                            continue
                    out.append(Move(model, fi, ti))
        return out

    def apply_move(self, s: SimState, mv: Move) -> None:
        """장비 1대를 from→to로 이동. batch 변경이면 Idle + tool 교체."""
        p = self.p
        model, fi, ti = mv
        fb, tb = p.batch_of(fi), p.batch_of(ti)
        s.assign[(model, fi)] = s.assign.get((model, fi), 0) - 1
        if s.assign[(model, fi)] == 0:
            del s.assign[(model, fi)]
        s.assign[(model, ti)] = s.assign.get((model, ti), 0) + 1
        if fb != tb:
            s.switching[(model, ti)] = s.switching.get((model, ti), 0) + p.switch_time_hours
            s.tool_used[(fb, model)] = max(0, s.tool_used.get((fb, model), 0) - 1)
            s.tool_used[(tb, model)] = s.tool_used.get((tb, model), 0) + 1

    def task_capacity(self, s: SimState, task_index: int) -> float:
        """task_index에 배치된 활성(Idle 제외) 장비의 총 UPH 합."""
        cap = 0.0
        for model in self.p.models():
            active = s.assign.get((model, task_index), 0) - s.switching.get((model, task_index), 0)
            if active > 0 and (uph := self.p.uph_of(model, task_index)):
                cap += active * uph
        return cap

    def wip_dwell_time(self, s: SimState, task_index: int) -> float | None:
        """현재 배치 기준 task_index의 WIP 소진 예상 시간(시간 단위).

        반환:
          float  — 소진까지 남은 시간 (0.0 이상, horizon_hours로 클리핑)
          None   — 전 공정이 더 빠르거나(WIP 누적 중), 장비 없음, 개념 미적용
        """
        p = self.p
        wip = s.wip[task_index]
        H = float(p.horizon_hours)
        if wip == 0:
            return 0.0
        cap_cur = self.task_capacity(s, task_index)
        if cap_cur <= 0:
            return None                         # 장비 없음 → 보너스 0 (해킹 방지)
        prev_ti = p.prev_task_index(task_index)
        if prev_ti is None:                     # 첫 공정
            return min(wip / cap_cur, H)
        cap_prev = self.task_capacity(s, prev_ti)
        denom = min(cap_cur, float(wip)) - min(cap_prev, float(wip))
        if denom <= 0:
            return None                         # 전 공정 공급 ≥ 소비 → 누적 중
        return min(wip / denom, H)


def _remaining(p: ProblemInstance, s: SimState, ti: int) -> int:
    return max(0, p.tasks[ti].plan_qty - s.produced[ti])


def heuristic_actions(sim: "Simulator", s: SimState) -> list[Move]:
    """이번 1시간에 둘 이동들을 그리디로 결정.

    원칙:
    1) 잔여계획이 0인 task에서 잔여계획이 큰 task로 장비를 옮긴다.
    2) batch 전환은 from-task가 더 이상 기여 못할 때만(잔여=0 또는 WIP=0).
    3) 한 시간의 남은 잔여계획을 가장 많이 줄이는 이동을 우선.
    """
    p = sim.p
    moves: list[Move] = []
    # 반복적으로 최선 이동 1개씩 선택 (substep)
    for _ in range(sum(p.eqp_qty.values()) + 1):
        candidates = sim.valid_moves(s)
        best, best_gain = None, 0.0
        for mv in candidates:
            from_rem = _remaining(p, s, mv.from_index)
            from_wip = s.wip[mv.from_index]
            to_rem = _remaining(p, s, mv.to_index)
            uph_to = p.uph_of(mv.model, mv.to_index) or 0.0
            uph_from = p.uph_of(mv.model, mv.from_index) or 0.0
            same_batch = p.batch_of(mv.from_index) == p.batch_of(mv.to_index)
            to_has_eqp = any(s.assign.get((m, mv.to_index), 0) > 0 for m in p.models())
            # from이 여전히 유효 생산 중이면 기본 유지하되, 무비용(같은 batch) 이동만 예외 허용:
            # (a) to의 UPH가 더 높아 총 생산이 늘거나
            # (b) to가 잔여>0인데 장비가 없어 무비용 충원이 가능할 때
            #     (단, UPH 저하 이동은 제외 — 고UPH 장비가 저UPH 태스크로 역배치되는 thrashing 방지)
            if from_rem > 0 and from_wip > 0:
                better_here = same_batch and uph_to > uph_from
                fill_empty_free = same_batch and to_rem > 0 and not to_has_eqp and uph_to >= uph_from
                if not (better_here or fill_empty_free):
                    continue
            hours_left = p.horizon_hours - s.hour - (0 if same_batch else p.switch_time_hours)
            gain = min(to_rem, s.wip[mv.to_index], uph_to * max(0, hours_left))
            if gain > best_gain:
                best, best_gain = mv, gain
        if best is None:
            break
        sim.apply_move(s, best)
        moves.append(best)
    return moves


def _active_eqp_count(p: ProblemInstance, s: SimState) -> int:
    """Idle 제외, 처리할 WIP가 남아 실제로 생산에 기여 중인 장비 대수 합."""
    return sum(
        max(0, s.assign.get((m, ti), 0) - s.switching.get((m, ti), 0))
        for m in p.models()
        for ti in range(len(p.tasks))
        if s.wip[ti] > 0 and p.uph_of(m, ti)
    )


def run_policy(sim: "Simulator", policy_fn) -> tuple[SimState, list, list[dict]]:
    """policy_fn(sim, state)->list[Move]를 매 시간 적용하며 horizon까지 시뮬레이션.

    반환 trace 항목: (hour, applied_moves, assign_snapshot)
    hourly_stats 항목: hour, hourly_produce, cumulative_produced, util_rate, assign_snapshot
    """
    p = sim.p
    s = sim.reset()
    trace: list = []
    hourly_stats: list[dict] = []
    total_eqp = sum(p.eqp_qty.values()) or 1
    n_tasks = len(p.tasks)
    while not sim.is_done(s):
        hour = s.hour
        applied = policy_fn(sim, s)
        snapshot = {(m, ti): c for (m, ti), c in s.assign.items()}
        before = dict(s.produced)
        util_rate = round(_active_eqp_count(p, s) / total_eqp, 4)
        sim.advance_hour(s)
        hourly_produce = {ti: s.produced[ti] - before.get(ti, 0) for ti in range(n_tasks)}
        stat = {
            "hour": hour,
            "hourly_produce": hourly_produce,
            "cumulative_produced": dict(s.produced),
            "util_rate": util_rate,
            "assign_snapshot": snapshot,
        }
        hourly_stats.append(stat)
        trace.append((hour, applied, snapshot))
    return s, trace, hourly_stats


def evaluate(problem: ProblemInstance) -> dict:
    """휴리스틱 vs ground_truth 비교."""
    sim = Simulator(problem)
    final, trace, hourly_stats = run_policy(sim, heuristic_actions)
    m = sim.metrics(final)
    return {
        "heuristic": m["plan_achievement"],
        "optimal": problem.ground_truth.get("plan_achievement"),
        "per_task": m["per_task"],
        "trace": trace,
        "hourly_stats": hourly_stats,
    }


def _task_wip_qty(task_data: dict) -> int:
    """JSON task dict → 초기 WIP. wip_qty 우선, 없으면 init_wip."""
    if "wip_qty" in task_data:
        return int(task_data["wip_qty"])
    return int(task_data.get("init_wip", 0))


def load_problem(path: str | Path) -> ProblemInstance:
    import config

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    tasks = [
        Task(t["plan_prod_key"], t["oper_id"], int(t["oper_seq"]),
             t["batch_id"], int(t["plan_qty"]), _task_wip_qty(t))
        for t in data["tasks"]
    ]

    def task_index(ppk: str, oper: str) -> int:
        for i, t in enumerate(tasks):
            if t.plan_prod_key == ppk and t.oper_id == oper:
                return i
        raise KeyError(f"task not found: {ppk}/{oper}")

    uph = {
        (u["eqp_model"], task_index(u["plan_prod_key"], u["oper_id"])): float(u["uph"])
        for u in data["uph"] if float(u["uph"]) > 0
    }
    init_assign = {
        (a["eqp_model"], task_index(a["plan_prod_key"], a["oper_id"])): int(a["count"])
        for a in data["init_assign"]
    }
    tool_qty = {(t["batch_id"], t["eqp_model"]): int(t["tool_qty"]) for t in data["tool_qty"]}
    equipments = [
        Equipment(
            eqp_id=str(e["eqp_id"]),
            eqp_model=str(e["eqp_model"]),
            batch_id=str(e.get("batch_id", "")),
            plan_prod_key=str(e.get("plan_prod_key", "")),
            oper_id=str(e.get("oper_id", "")),
        )
        for e in data.get("equipments", [])
    ]
    return ProblemInstance(
        rule_timekey=data["rule_timekey"],
        horizon_hours=int(data["horizon_hours"]),
        switch_time_hours=int(data.get("switch_time_hours", 1)),
        tasks=tasks,
        _uph=uph,
        eqp_qty={k: int(v) for k, v in data["eqp_qty"].items()},
        init_assign=init_assign,
        tool_qty=tool_qty,
        conv_groups=config.load_conv_groups(),
        facid=data.get("facid") or data.get("fac_id"),
        equipments=equipments,
        ground_truth=data.get("ground_truth", {}),
    )


def problem_to_dict(problem: ProblemInstance, include_ground_truth: bool = True) -> dict:
    """ProblemInstance → benchmark/inference JSON dict."""
    tasks = [
        {
            "plan_prod_key": t.plan_prod_key,
            "oper_id": t.oper_id,
            "oper_seq": t.oper_seq,
            "batch_id": t.batch_id,
            "plan_qty": t.plan_qty,
            "wip_qty": t.wip_qty,
            "init_wip": t.init_wip,
        }
        for t in problem.tasks
    ]
    uph = []
    for (model, ti), val in sorted(problem._uph.items()):
        t = problem.tasks[ti]
        uph.append({
            "plan_prod_key": t.plan_prod_key,
            "oper_id": t.oper_id,
            "eqp_model": model,
            "uph": val,
        })
    init_assign = []
    for (model, ti), cnt in sorted(problem.init_assign.items()):
        t = problem.tasks[ti]
        init_assign.append({
            "eqp_model": model,
            "plan_prod_key": t.plan_prod_key,
            "oper_id": t.oper_id,
            "count": cnt,
        })
    tool_qty = [
        {"batch_id": b, "eqp_model": m, "tool_qty": q}
        for (b, m), q in sorted(problem.tool_qty.items())
    ]
    data = {
        "rule_timekey": problem.rule_timekey,
        "horizon_hours": problem.horizon_hours,
        "switch_time_hours": problem.switch_time_hours,
        "tasks": tasks,
        "uph": uph,
        "eqp_qty": dict(problem.eqp_qty),
        "init_assign": init_assign,
        "tool_qty": tool_qty,
    }
    if problem.facid:
        data["facid"] = problem.facid
    if problem.equipments:
        data["equipments"] = [
            {
                "eqp_id": e.eqp_id,
                "eqp_model": e.eqp_model,
                "batch_id": e.batch_id,
                "plan_prod_key": e.plan_prod_key,
                "oper_id": e.oper_id,
            }
            for e in problem.equipments
        ]
    if include_ground_truth and problem.ground_truth:
        data["ground_truth"] = problem.ground_truth
    return data


def save_problem(problem: ProblemInstance, path: str | Path,
                 include_ground_truth: bool = True) -> Path:
    """ProblemInstance를 JSON 파일로 저장 (data/inference · data/train 형식)."""
    import config

    path = config.replace_file(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(problem_to_dict(problem, include_ground_truth), indent=2, ensure_ascii=False)
    path.write_text(text + "\n", encoding="utf-8")
    return path
