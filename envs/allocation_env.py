"""Gymnasium AllocationEnv — sb3 격리."""
from __future__ import annotations

import math

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from src.simulation.domain.problem import ProblemInstance, largest_remainder


def _softmax(x: list[float]) -> list[float]:
    mx = max(x)
    ex = [math.exp(v - mx) for v in x]
    s = sum(ex)
    return [v / s for v in ex]


class AllocationEnv(gym.Env):
    def __init__(self, problem: ProblemInstance,
                 max_tasks: int | None = None, max_models: int | None = None):
        super().__init__()
        self.p = problem
        self.models = problem.models()
        self.n_tasks = len(problem.tasks)
        self.n_models = len(self.models)
        self.mt = max_tasks if max_tasks is not None else self.n_tasks
        self.mm = max_models if max_models is not None else self.n_models
        if self.mt < self.n_tasks:
            raise ValueError(f"max_tasks({self.mt}) < 실제 tasks({self.n_tasks})")
        if self.mm < self.n_models:
            raise ValueError(f"max_models({self.mm}) < 실제 models({self.n_models})")
        obs_dim = self.mt + self.mm * self.mt + self.mm + self.mm * self.mt
        self.observation_space = spaces.Box(low=0.0, high=1.0, shape=(obs_dim,), dtype=np.float32)
        self.action_space = spaces.Box(low=-3.0, high=3.0,
                                       shape=(self.mm * self.mt,), dtype=np.float32)
        self._last_allocation: dict[tuple[str, int], int] = {}
        self._done = False

    def _build_obs(self) -> np.ndarray:
        p = self.p
        max_plan = max((t.plan_qty for t in p.tasks), default=1)
        max_uph = max((v for v in p._uph.values()), default=1.0)
        max_eqp = max(p.eqp_qty.values(), default=1)
        max_tool = max(p.tool_qty.values(), default=1)
        plan_part = [0.0] * self.mt
        for i, t in enumerate(p.tasks):
            plan_part[i] = t.plan_qty / max_plan
        uph_part = [0.0] * (self.mm * self.mt)
        for mi, m in enumerate(self.models):
            for ti in range(self.n_tasks):
                uph = p.uph_of(m, ti) or 0.0
                uph_part[mi * self.mt + ti] = uph / max_uph
        eqp_part = [0.0] * self.mm
        for mi, m in enumerate(self.models):
            eqp_part[mi] = p.eqp_qty[m] / max_eqp
        tool_part = [0.0] * (self.mm * self.mt)
        for mi, m in enumerate(self.models):
            for ti in range(self.n_tasks):
                batch = p.batch_of(ti) if ti < self.n_tasks else None
                if batch:
                    tq = p.tool_cap(batch, m)
                    tool_part[mi * self.mt + ti] = tq / max_tool
        return np.asarray(plan_part + uph_part + eqp_part + tool_part, dtype=np.float32)

    def _logits_to_allocation(self, logits: np.ndarray) -> dict[tuple[str, int], int]:
        p = self.p
        alloc: dict[tuple[str, int], int] = {}
        for mi, model in enumerate(self.models):
            model_logits = logits[mi * self.mt: (mi + 1) * self.mt]
            masked = [
                float(model_logits[ti]) if (ti < self.n_tasks and p.uph_of(model, ti) is not None)
                else -9999.0
                for ti in range(self.mt)
            ]
            fracs_full = _softmax(masked)
            fracs = fracs_full[:self.n_tasks]
            raw = [fracs[ti] * p.eqp_qty[model] for ti in range(self.n_tasks)]
            for ti in range(self.n_tasks):
                batch = p.batch_of(ti)
                tool_cap = p.tool_cap(batch, model)
                raw[ti] = min(raw[ti], float(tool_cap))
            raw_sum = sum(raw)
            eqp = p.eqp_qty[model]
            if raw_sum > eqp and raw_sum > 0:
                scale = eqp / raw_sum
                raw = [v * scale for v in raw]
            counts = largest_remainder(raw, eqp)
            for ti, cnt in enumerate(counts):
                if ti < self.n_tasks and p.uph_of(model, ti) is not None:
                    alloc[(model, ti)] = cnt
        return alloc

    def _compute_reward(self, alloc: dict[tuple[str, int], int]) -> float:
        p = self.p
        rates = []
        for ti, task in enumerate(p.tasks):
            if task.plan_qty <= 0:
                rates.append(1.0)
                continue
            cap = sum(
                alloc.get((model, ti), 0) * (p.uph_of(model, ti) or 0.0)
                for model in self.models
            )
            switches_in = sum(
                max(0, alloc.get((model, ti), 0) - p.init_assign.get((model, ti), 0))
                for model in self.models
            )
            eff_h = max(0.0, float(p.horizon_hours) - switches_in * p.switch_time_hours)
            max_prod = cap * eff_h
            rate = min(max_prod, task.plan_qty) / task.plan_qty
            rates.append(rate)
        return sum(rates) / len(rates) if rates else 0.0

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        self._done = False
        self._last_allocation = {}
        return self._build_obs(), {}

    def step(self, action):
        if self._done:
            raise RuntimeError("AllocationEnv: step() called after episode ended. Call reset().")
        alloc = self._logits_to_allocation(np.asarray(action, dtype=np.float32))
        self._last_allocation = alloc
        reward = self._compute_reward(alloc)
        self._done = True
        return self._build_obs(), float(reward), True, False, {"allocation": alloc}

    def get_allocation(self) -> dict[tuple[str, int], int]:
        return dict(self._last_allocation)

    def get_float_target(self) -> dict[tuple[str, int], float]:
        return self.p.complete_guide_allocation(self._last_allocation)
