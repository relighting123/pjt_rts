"""상위 배분 RL 환경: 계획·UPH·가용 장비만 보고 공정별 장비 배치 대수를 결정.

1-step 환경: reset() → step(action) → done=True
action은 연속(softmax logit), 내부에서 정수 배분으로 변환한다.

계층 구조:
  AllocationEnv (상위) → target_allocation
  DispatchEnv   (하위) → 실시간 이동, target_allocation을 가이드로 사용
"""
from __future__ import annotations
import math
import numpy as np
import gymnasium as gym
from gymnasium import spaces

from simulator import ProblemInstance


def _softmax(x: list[float]) -> list[float]:
    mx = max(x)
    ex = [math.exp(v - mx) for v in x]
    s = sum(ex)
    return [v / s for v in ex]


def _largest_remainder(fracs: list[float], total: int) -> list[int]:
    """소수점 배분을 정수로 변환, 합계 = total 보장 (최대잉여법)."""
    floors = [int(f) for f in fracs]
    remainders = [(fracs[i] - floors[i], i) for i in range(len(fracs))]
    deficit = total - sum(floors)
    remainders.sort(reverse=True)
    for k in range(deficit):
        floors[remainders[k][1]] += 1
    return floors


class AllocationEnv(gym.Env):
    """1-step RL 환경: 계획 파라미터를 관측하고 장비 배분 대수를 출력.

    관측 공간:
      [plan_qty 정규화 × mt]
      [UPH 행렬 정규화 × mm×mt]
      [eqp_qty 정규화 × mm]
      [tool_qty 정규화 × mm×mt]

    액션 공간:
      Box[-3, 3] shape=(mm×mt,) — model별 softmax logit
      내부에서 softmax → eqp_qty 비례 → tool 상한 클리핑 → 정수 변환

    리워드:
      이론적 계획달성율 평균
      = mean_t( min(capacity_t × effective_h, plan_qty[t]) / plan_qty[t] )
      capacity_t = Σ_m alloc[m,t] × UPH[m,t]
      effective_h = horizon - (전환 필요 대수 × switch_time) 보정
    """

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

        # 관측 차원: mt + mm×mt + mm + mm×mt = mt(1+2mm) + mm
        obs_dim = self.mt + self.mm * self.mt + self.mm + self.mm * self.mt
        self.observation_space = spaces.Box(low=0.0, high=1.0, shape=(obs_dim,), dtype=np.float32)

        # 액션: model별 task logit (연속)
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
                    tq = p.tool_qty.get((batch, m), 0)
                    tool_part[mi * self.mt + ti] = tq / max_tool

        return np.asarray(plan_part + uph_part + eqp_part + tool_part, dtype=np.float32)

    def _logits_to_allocation(self, logits: np.ndarray) -> dict[tuple[str, int], int]:
        """logit 벡터 → model별 정수 배분. tool 상한 및 eqp_qty 제약 준수."""
        p = self.p
        alloc: dict[tuple[str, int], int] = {}
        for mi, model in enumerate(self.models):
            model_logits = logits[mi * self.mt: (mi + 1) * self.mt]
            # UPH 없는 task는 -9999 masking
            masked = [
                float(model_logits[ti]) if (ti < self.n_tasks and p.uph_of(model, ti) is not None)
                else -9999.0
                for ti in range(self.mt)
            ]
            fracs_full = _softmax(masked)
            fracs = fracs_full[:self.n_tasks]  # 실제 task 수만 사용
            raw = [fracs[ti] * p.eqp_qty[model] for ti in range(self.n_tasks)]

            # tool 상한 클리핑
            for ti in range(self.n_tasks):
                batch = p.batch_of(ti)
                tool_cap = p.tool_qty.get((batch, model), 0)
                raw[ti] = min(raw[ti], float(tool_cap))

            # 합계가 eqp_qty를 넘지 않도록 스케일
            raw_sum = sum(raw)
            eqp = p.eqp_qty[model]
            if raw_sum > eqp and raw_sum > 0:
                scale = eqp / raw_sum
                raw = [v * scale for v in raw]

            counts = _largest_remainder(raw, eqp)
            for ti, cnt in enumerate(counts):
                if ti < self.n_tasks and p.uph_of(model, ti) is not None:
                    alloc[(model, ti)] = cnt
        return alloc

    def _compute_reward(self, alloc: dict[tuple[str, int], int]) -> float:
        """배분에 대한 이론적 계획달성율 평균.

        파이프라인(순차 공정)은 하위 DispatchEnv가 처리하므로 독립 취급.
        전환 비용: task ti로 새로 유입되는 장비 대수 × switch_time_hours를
        해당 task의 effective_horizon에서 차감 (task별 개별 보정).
        """
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
            # ti로 전환해 오는 장비 수: alloc > init_assign인 만큼
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
        """마지막 step()에서 결정된 배분 반환."""
        return dict(self._last_allocation)

    def get_float_target(self) -> dict[tuple[str, int], float]:
        """정수 배분을 float으로 변환 (DispatchEnv target_allocation 주입용)."""
        return self.p.complete_guide_allocation(self._last_allocation)
