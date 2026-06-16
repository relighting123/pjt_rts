"""장비 호기(EQP_ID) 단위 추적 — trace 재생으로 실제 호기 매핑.

ProblemInstance.equipments(실제 호기 명단)가 있으면 실제 EQP_ID로,
없으면 가상 호기({model}-{seq:03d})로 시간대별 배치·전환을 추적한다.
시뮬레이터는 (model, task) 대수만 다루므로, 여기서 trace의 Move를
호기 단위로 재생해 간트차트·전환계획에 쓸 호기 식별자를 복원한다.
"""
from __future__ import annotations

from src.simulation.domain.problem import Equipment, Move, ProblemInstance


def virtual_roster(problem: ProblemInstance) -> list[Equipment]:
    """init_assign 기준 가상 호기 명단 ({model}-{seq:03d})."""
    roster: list[Equipment] = []
    seq: dict[str, int] = {}
    for (model, ti), cnt in sorted(problem.init_assign.items()):
        t = problem.tasks[ti]
        for _ in range(cnt):
            n = seq.get(model, 0) + 1
            seq[model] = n
            roster.append(Equipment(
                f"{model}-{n:03d}", model, t.batch_id, t.plan_prod_key, t.oper_id,
            ))
    return roster


def _match_rank(e: Equipment, task) -> int:
    """초기 배치 매칭 우선순위 — 낮을수록 우선."""
    same_ppk = e.plan_prod_key == task.plan_prod_key
    same_oper = not e.oper_id or e.oper_id == task.oper_id
    same_batch = not e.batch_id or e.batch_id == task.batch_id
    if same_ppk and same_oper and same_batch:
        return 0
    if same_ppk and same_oper:
        return 1
    if same_ppk:
        return 2
    if e.batch_id == task.batch_id:
        return 3
    return 4


def initial_positions(problem: ProblemInstance) -> dict[tuple[str, int], list[str]]:
    """(model, task_index) -> [eqp_id]. init_assign 대수에 호기를 매칭.

    실제 명단의 BATCH_ID/PLAN_PROD_KEY/OPER_ID와 task 속성이 일치하는
    호기를 우선 배정하고, 명단이 부족하면 가상 호기({model}-V{n:03d})로 보충.
    """
    roster = problem.equipments or virtual_roster(problem)
    free: dict[str, list[Equipment]] = {}
    for e in sorted(roster, key=lambda e: e.eqp_id):
        free.setdefault(e.eqp_model, []).append(e)
    pos: dict[tuple[str, int], list[str]] = {}
    vseq: dict[str, int] = {}
    for (model, ti), cnt in sorted(problem.init_assign.items(), key=lambda x: (x[0][1], x[0][0])):
        task = problem.tasks[ti]
        cands = sorted(free.get(model, []), key=lambda e: (_match_rank(e, task), e.eqp_id))
        picked = cands[:cnt]
        for e in picked:
            free[model].remove(e)
        ids = [e.eqp_id for e in picked]
        while len(ids) < cnt:
            n = vseq.get(model, 0) + 1
            vseq[model] = n
            ids.append(f"{model}-V{n:03d}")
        pos[(model, ti)] = ids
    return pos


def track_units(
    problem: ProblemInstance, trace: list,
) -> tuple[list[dict[tuple[str, int], list[str]]], list[dict]]:
    """trace를 호기 단위로 재생.

    반환:
      hourly_positions — trace 각 시점(이동 적용 후)의 (model, ti) -> [eqp_id]
      conversions      — batch 전환 이동 목록 (trace 순서):
                         {hour, eqp_id, model, from_index, to_index}
    """
    pos = initial_positions(problem)
    hourly: list[dict[tuple[str, int], list[str]]] = []
    conversions: list[dict] = []
    vseq: dict[str, int] = {}
    for hour, applied, _snapshot in trace:
        for mv in applied or []:
            if not isinstance(mv, Move):
                continue
            units = pos.get((mv.model, mv.from_index))
            if units:
                eqp_id = units.pop()
                if not units:
                    del pos[(mv.model, mv.from_index)]
            else:
                # 방어: 추적 불일치(임의 trace 등) 시 가상 호기로 보충
                n = vseq.get(mv.model, 0) + 1
                vseq[mv.model] = n
                eqp_id = f"{mv.model}-V{n:03d}"
            pos.setdefault((mv.model, mv.to_index), []).append(eqp_id)
            if problem.batch_of(mv.from_index) != problem.batch_of(mv.to_index):
                conversions.append({
                    "hour": hour,
                    "eqp_id": eqp_id,
                    "model": mv.model,
                    "from_index": mv.from_index,
                    "to_index": mv.to_index,
                })
        hourly.append({k: list(v) for k, v in pos.items()})
    return hourly, conversions
