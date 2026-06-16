"""휴리스틱 디스패치 정책."""
from __future__ import annotations

from src.simulation.domain.problem import Move, ProblemInstance
from src.simulation.domain.state import SimState
from src.simulation.kernel.simulator import Simulator
from agents.registry import register_dispatch


def _remaining(p: ProblemInstance, s: SimState, ti: int) -> int:
    return max(0, p.tasks[ti].plan_qty - s.produced[ti])


@register_dispatch("heuristic")
def heuristic_actions(sim: Simulator, s: SimState) -> list[Move]:
    p = sim.p
    moves: list[Move] = []
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
