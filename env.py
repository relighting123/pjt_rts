"""Gymnasium 환경: model-count substep 액션 + 액션 마스킹.

액션 0 = commit(1시간 경과). 1..N = 사전 열거된 (model, from, to) 이동.
MaskablePPO(sb3-contrib)와 호환되도록 action_masks()를 제공한다.
"""
from __future__ import annotations
import numpy as np
import gymnasium as gym
from gymnasium import spaces

from simulator import Simulator, Move, ProblemInstance


class DispatchEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, problem: ProblemInstance, max_substeps_per_hour: int | None = None):
        super().__init__()
        self.p = problem
        self.sim = Simulator(problem)
        self.models = problem.models()
        self.n_tasks = len(problem.tasks)
        # 가능한 모든 (model, from, to) 조합을 고정 인덱싱 (마스크로 유효성 판단)
        self.move_list: list[Move] = [
            Move(m, fi, ti)
            for m in self.models
            for fi in range(self.n_tasks)
            for ti in range(self.n_tasks)
            if fi != ti
        ]
        self.action_space = spaces.Discrete(len(self.move_list) + 1)  # 0=commit
        # 관측: [per-task 잔여계획비율, per-task WIP(정규화), per (model,task) 배치대수(정규화), hour 비율]
        obs_dim = self.n_tasks * 2 + len(self.models) * self.n_tasks + 1
        self.observation_space = spaces.Box(low=0.0, high=1.0, shape=(obs_dim,), dtype=np.float32)
        total_eqp = sum(problem.eqp_qty.values())
        self.max_substeps = max_substeps_per_hour or (total_eqp + 1)
        self._state = None
        self._substeps = 0

    def _obs(self) -> np.ndarray:
        p, s = self.p, self._state
        parts = []
        for i, t in enumerate(p.tasks):
            rem = max(0, t.plan_qty - s.produced[i])
            parts.append(rem / t.plan_qty if t.plan_qty else 0.0)
        max_wip = max([t.init_wip for t in p.tasks] + [1])
        for i in range(self.n_tasks):
            parts.append(min(1.0, s.wip[i] / max_wip))
        for m in self.models:
            cap = max(1, p.eqp_qty[m])
            for i in range(self.n_tasks):
                parts.append(s.assign.get((m, i), 0) / cap)
        parts.append(s.hour / max(1, p.horizon_hours))
        return np.asarray(parts, dtype=np.float32)

    def action_masks(self) -> np.ndarray:
        valid = set(self.sim.valid_moves(self._state))
        mask = np.zeros(self.action_space.n, dtype=bool)
        mask[0] = True  # commit 항상 허용
        for idx, mv in enumerate(self.move_list, start=1):
            if mv in valid:
                mask[idx] = True
        return mask

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        self._state = self.sim.reset()
        self._substeps = 0
        return self._obs(), {}

    def step(self, action: int):
        p, s = self.p, self._state
        before = self._achievement_qty()
        if action == 0:
            self._commit()
        else:
            mv = self.move_list[action - 1]
            if mv in set(self.sim.valid_moves(s)):
                self.sim.apply_move(s, mv)
            self._substeps += 1
            if self._substeps >= self.max_substeps:
                self._commit()
        # dense 보상: 미충족 계획에 기여한 생산 증가분(정규화)
        gained = self._achievement_qty() - before
        total_plan = sum(t.plan_qty for t in p.tasks) or 1
        reward = gained / total_plan
        terminated = self.sim.is_done(s)
        info = {}
        if terminated:
            m = self.sim.metrics(s)
            reward += m["plan_achievement"]  # 종료 보너스
            info["plan_achievement"] = m["plan_achievement"]
            info["per_task"] = m["per_task"]
        return self._obs(), float(reward), terminated, False, info

    def _commit(self):
        self.sim.advance_hour(self._state)
        self._substeps = 0

    def _achievement_qty(self) -> int:
        """달성에 기여한(계획 캡) 누적 생산량 합."""
        s, p = self._state, self.p
        return sum(min(s.produced[i], t.plan_qty) for i, t in enumerate(p.tasks))
