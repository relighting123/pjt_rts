"""Gym DispatchEnv ↔ kernel SimState 동기화."""
from __future__ import annotations

import config
from src.simulation.domain.problem import ProblemInstance
from src.simulation.domain.state import SimState
from src.simulation.kernel.simulator import Simulator


class DispatchBridge:
    """RL 모델 추론 시 env._state 직접 접근을 캡슐화."""

    def __init__(self, problem: ProblemInstance):
        from envs.dispatch_env import DispatchEnv
        self._env = DispatchEnv(
            problem,
            max_tasks=config.MAX_TASKS,
            max_models=config.MAX_MODELS,
            dwell_obs=config.DWELL_OBS,
        )

    def plan_moves(self, sim: Simulator, state: SimState, model) -> list:
        env = self._env
        env._state = state
        env._substeps = 0
        moves = []
        for _ in range(env.max_substeps):
            obs = env._obs()
            mask = env.action_masks()
            action, _ = model.predict(obs, action_masks=mask, deterministic=True)
            action = int(action)
            if action == 0:
                break
            mv = env.move_list[action - 1]
            if mv in set(sim.valid_moves(state)):
                sim.apply_move(state, mv)
                moves.append(mv)
            else:
                break
        return moves
