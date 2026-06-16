"""Gymnasium DispatchEnv — sb3 격리."""
from __future__ import annotations

import numpy as np
import gymnasium as gym
from gymnasium import spaces

from src.simulation.domain.problem import Move, ProblemInstance
from src.simulation.kernel.simulator import Simulator, active_eqp_count


class DispatchEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, problem: ProblemInstance, max_substeps_per_hour: int | None = None,
                 max_tasks: int | None = None, max_models: int | None = None,
                 dwell_lambda: float = 0.0, alloc_lambda: float = 0.0,
                 target_allocation: dict | None = None, dwell_obs: bool = False,
                 guide_util_threshold: float = 0.0, guide_band_pct: float = 0.0):
        super().__init__()
        self.p = problem
        self.sim = Simulator(problem)
        self.models = problem.models()
        self.n_tasks = len(problem.tasks)
        self.n_models = len(self.models)
        self.mt = max_tasks if max_tasks is not None else self.n_tasks
        self.mm = max_models if max_models is not None else self.n_models
        if self.mt < self.n_tasks:
            raise ValueError(f"max_tasks({self.mt}) < 실제 tasks({self.n_tasks})")
        if self.mm < self.n_models:
            raise ValueError(f"max_models({self.mm}) < 실제 models({self.n_models})")
        padded_models = self.models + [
            f"__pad_model_{i}__" for i in range(self.mm - self.n_models)
        ]
        self.move_list: list[Move] = [
            Move(m, fi, ti)
            for m in padded_models
            for fi in range(self.mt)
            for ti in range(self.mt)
            if fi != ti
        ]
        self.action_space = spaces.Discrete(len(self.move_list) + 1)
        self._move_to_idx: dict[Move, int] = {mv: i + 1 for i, mv in enumerate(self.move_list)}
        obs_dim = self.mt * 2 + 2 * self.mm * self.mt + 1
        self.observation_space = spaces.Box(low=0.0, high=1.0, shape=(obs_dim,), dtype=np.float32)
        total_eqp = sum(problem.eqp_qty.values())
        self.max_substeps = max_substeps_per_hour or (total_eqp + 1)
        self.dwell_lambda = dwell_lambda
        self.alloc_lambda = alloc_lambda
        self.target_allocation: dict[tuple[str, int], float] = dict(target_allocation or {})
        self.guide_util_threshold = guide_util_threshold
        self.guide_band_pct = guide_band_pct
        self.dwell_obs = dwell_obs
        if dwell_obs:
            obs_dim = self.mt * 2 + 2 * self.mm * self.mt + 1 + self.mt
            self.observation_space = spaces.Box(low=0.0, high=1.0, shape=(obs_dim,), dtype=np.float32)
        self._state = None
        self._substeps = 0

    def _obs(self) -> np.ndarray:
        p, s = self.p, self._state
        plan_part = [0.0] * self.mt
        for i, t in enumerate(p.tasks):
            rem = max(0, t.plan_qty - s.produced[i])
            plan_part[i] = rem / t.plan_qty if t.plan_qty else 0.0
        max_wip = max([t.init_wip for t in p.tasks] + [1])
        wip_part = [0.0] * self.mt
        for i in range(self.n_tasks):
            wip_part[i] = min(1.0, s.wip[i] / max_wip)
        assign_part = [0.0] * (self.mm * self.mt)
        for mi, m in enumerate(self.models):
            cap = max(1, p.eqp_qty[m])
            for i in range(self.n_tasks):
                assign_part[mi * self.mt + i] = s.assign.get((m, i), 0) / cap
        change_part = [0.0] * (self.mm * self.mt)
        for mi, m in enumerate(self.models):
            max_change = p.switch_time_hours * max(1, p.eqp_qty[m])
            for i in range(self.n_tasks):
                change_part[mi * self.mt + i] = min(
                    1.0, s.switching.get((m, i), 0) / max_change
                )
        hour_part = [s.hour / max(1, p.horizon_hours)]
        base = plan_part + wip_part + assign_part + change_part + hour_part
        if self.dwell_obs:
            H = float(p.horizon_hours)
            dwell_part = [0.0] * self.mt
            for i in range(self.n_tasks):
                d = self.sim.wip_dwell_time(s, i)
                dwell_part[i] = 0.0 if d is None else min(d, H) / H
            base = base + dwell_part
        return np.asarray(base, dtype=np.float32)

    def action_masks(self) -> np.ndarray:
        mask = np.zeros(self.action_space.n, dtype=bool)
        mask[0] = True
        for mv in self.sim.valid_moves(self._state):
            idx = self._move_to_idx.get(mv)
            if idx is not None:
                mask[idx] = True
        return mask

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        self._state = self.sim.reset()
        self._substeps = 0
        return self._obs(), {}

    def _dwell_shaping_reward(self) -> float:
        if self.dwell_lambda == 0.0:
            return 0.0
        p, s = self.p, self._state
        H = float(p.horizon_hours)
        total_plan = sum(t.plan_qty for t in p.tasks) or 1
        shaping = 0.0
        for i, t in enumerate(p.tasks):
            remaining = max(0, t.plan_qty - s.produced[i])
            if remaining == 0:
                continue
            d = self.sim.wip_dwell_time(s, i)
            if d is None:
                continue
            weight = remaining / total_plan
            shaping += weight * min(d, H) / H
        return self.dwell_lambda * shaping

    def _current_util(self) -> float:
        total = sum(self.p.eqp_qty.values()) or 1
        return active_eqp_count(self.p, self._state) / total

    def _alloc_guide_reward(self) -> float:
        if self.alloc_lambda == 0.0 or not self.target_allocation:
            return 0.0
        s = self._state
        if self._current_util() < self.guide_util_threshold:
            return 0.0
        band = self.guide_band_pct
        total_pen = 0.0
        count = 0
        for (model, ti), tgt in self.target_allocation.items():
            if s.wip.get(ti, 0) == 0:
                continue
            actual = s.assign.get((model, ti), 0)
            lower = tgt * (1.0 - band)
            upper = tgt * (1.0 + band)
            if actual < lower:
                over = lower - actual
            elif actual > upper:
                over = actual - upper
            else:
                over = 0.0
            total_pen += over / max(1.0, self.p.eqp_qty[model])
            count += 1
        if count == 0:
            return 0.0
        return self.alloc_lambda * (1.0 - total_pen / count)

    def step(self, action: int):
        p, s = self.p, self._state
        before = self._achievement_qty()
        dwell_r = alloc_r = 0.0
        if action == 0:
            dwell_r = self._dwell_shaping_reward()
            alloc_r = self._alloc_guide_reward()
            self._commit()
        else:
            mv = self.move_list[action - 1]
            if mv in set(self.sim.valid_moves(s)):
                self.sim.apply_move(s, mv)
            self._substeps += 1
            if self._substeps >= self.max_substeps:
                dwell_r = self._dwell_shaping_reward()
                alloc_r = self._alloc_guide_reward()
                self._commit()
        gained = self._achievement_qty() - before
        total_plan = sum(t.plan_qty for t in p.tasks) or 1
        reward = gained / total_plan + dwell_r + alloc_r
        terminated = self.sim.is_done(s)
        info = {}
        if terminated:
            m = self.sim.metrics(s)
            reward += m["plan_achievement"]
            info["plan_achievement"] = m["plan_achievement"]
            info["per_task"] = m["per_task"]
        return self._obs(), float(reward), terminated, False, info

    def _commit(self):
        self.sim.advance_hour(self._state)
        self._substeps = 0

    def _achievement_qty(self) -> int:
        s, p = self._state, self.p
        return sum(min(s.produced[i], t.plan_qty) for i, t in enumerate(p.tasks))
