# 2-모드 가이드 기반 장비 운영 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** rule_timekey마다 ① 재공-무한 가이드 수량(Mode 1)과 ② 재공 반영 동적 운영(Mode 2)을 항상 함께 산출하고, 가이드 준수를 가동률·밴드% 조건부로 개선한다.

**Architecture:** 기존 2계층(AllocationEnv→DispatchEnv) 골격을 마무리한다. AllocationEnv(1-step PPO)에 학습 진입점을 추가해 `ppo_alloc.zip`을 생성하고, DispatchEnv의 가이드 준수 보상을 "가동률 임계 이상에서 가이드 ±밴드%" 로직으로 교체한다. 관련 기본값을 ON으로 돌리고, 평가/리포트가 가이드+동적 2산출을 내도록 한다.

**Tech Stack:** Python, numpy, torch, stable-baselines3 (PPO), sb3-contrib (MaskablePPO), gymnasium, pytest.

---

## File Structure

- `config.py` — 신규 설정 키 2개(`GUIDE_UTIL_THRESHOLD`, `GUIDE_BAND_PCT`) + 기본값 4개 ON.
- `env.py` — `DispatchEnv` 생성자에 가이드 파라미터 추가, `_current_util()` 헬퍼, `_alloc_guide_reward()` 조건부 재작성.
- `train.py` — `train_alloc_model()` 신규(AllocationEnv 학습→`ppo_alloc.zip`), `train_model()`이 선행 호출, 환경 생성 시 가이드 파라미터 전달.
- `test.py` — 환경 생성에 `dwell_obs`/가이드 파라미터 전달(차원 일치 버그 수정), `evaluate_benchmark()`가 가이드 수량 산출 추가.
- `report_output.py` — 가이드 수량 표 렌더 헬퍼.
- `run.py` — infer 출력에 가이드+동적 둘 다 표시.
- `README.md` — 가짜 `--mode plan-only/wip-static/dynamic` 설명 정리.
- `tests/` — 신규/수정 테스트.

각 Task는 독립적으로 테스트 통과 가능하게 구성한다.

---

## Task 1: 조건부 가이드 준수 보상 (config + env)

가동률 임계 이상에서만, 가이드 대비 ±밴드% 밖 편차만 페널티. 재공 0인 task는 제외.

**Files:**
- Modify: `config.py` (설정 키 추가)
- Modify: `env.py` (`DispatchEnv.__init__`, `_current_util`, `_alloc_guide_reward`)
- Test: `tests/test_env.py`

- [ ] **Step 1: config에 설정 키 추가**

`config.py`의 `USE_ALLOC_MODEL` 줄 아래(41행 부근)에 추가:

```python
# 가이드 준수: 이 가동률 이상에서만 적용
GUIDE_UTIL_THRESHOLD = float(os.getenv("GUIDE_UTIL_THRESHOLD", "0.70"))
# 가이드 대비 허용 상·하단 비율 (±%). 밴드 안이면 페널티 0
GUIDE_BAND_PCT = float(os.getenv("GUIDE_BAND_PCT", "0.20"))
```

- [ ] **Step 2: 실패하는 테스트 작성**

`tests/test_env.py` 끝에 추가:

```python
def _env_with_guide(util_threshold, band):
    from env import DispatchEnv
    p = load_problem(BENCHMARKS_DIR / "benchmark_02.json")
    # 첫 두 task에 대해 모든 장비를 task 0에 몰아넣는 가이드(현실 배치와 일부러 다르게)
    models = p.models()
    target = {(models[0], 0): float(p.eqp_qty[models[0]])}
    env = DispatchEnv(
        p, alloc_lambda=1.0, target_allocation=target,
        guide_util_threshold=util_threshold, guide_band_pct=band,
    )
    env.reset(seed=0)
    return env


def test_guide_reward_zero_when_util_below_threshold():
    # 가동률 임계를 1.1로 두면 어떤 상태도 미달 → 항상 0
    env = _env_with_guide(util_threshold=1.1, band=0.2)
    assert env._alloc_guide_reward() == 0.0


def test_guide_reward_skips_zero_wip_tasks():
    # 가동률 임계를 0.0으로 낮춰 항상 적용되게 하고, WIP 0 task는 페널티 제외
    env = _env_with_guide(util_threshold=0.0, band=0.0)
    s = env._state
    # 모든 task WIP을 0으로 → count==0 → 0.0
    for i in range(len(env.p.tasks)):
        s.wip[i] = 0
    assert env._alloc_guide_reward() == 0.0


def test_guide_reward_band_tolerates_small_deviation():
    p = load_problem(BENCHMARKS_DIR / "benchmark_02.json")
    from env import DispatchEnv
    models = p.models()
    # 가이드 = 현재 init_assign 그대로 → 편차 0
    target = {(m, ti): float(c) for (m, ti), c in p.init_assign.items()}
    env = DispatchEnv(
        p, alloc_lambda=1.0, target_allocation=target,
        guide_util_threshold=0.0, guide_band_pct=0.20,
    )
    env.reset(seed=0)
    # 편차 0 → 페널티 0 → 보상 == alloc_lambda * 1.0
    assert abs(env._alloc_guide_reward() - 1.0) < 1e-9
```

- [ ] **Step 3: 테스트 실패 확인**

Run: `python -m pytest tests/test_env.py -k guide -v`
Expected: FAIL — `DispatchEnv.__init__()`에 `guide_util_threshold` 인자 없음(TypeError).

- [ ] **Step 4: env.py 생성자에 파라미터 추가**

`env.py`의 `DispatchEnv.__init__` 시그니처(20행 부근)를 수정:

```python
    def __init__(self, problem: ProblemInstance, max_substeps_per_hour: int | None = None,
                 max_tasks: int | None = None, max_models: int | None = None,
                 dwell_lambda: float = 0.0, alloc_lambda: float = 0.0,
                 target_allocation: dict | None = None, dwell_obs: bool = False,
                 guide_util_threshold: float = 0.0, guide_band_pct: float = 0.0):
```

그리고 `self.target_allocation = ...` 줄(56행 부근) 아래에 추가:

```python
        self.guide_util_threshold = guide_util_threshold
        self.guide_band_pct = guide_band_pct
```

- [ ] **Step 5: `_current_util` 헬퍼와 `_alloc_guide_reward` 재작성**

`env.py`의 기존 `_alloc_guide_reward` 메서드(138~152행) 전체를 아래로 교체:

```python
    def _current_util(self) -> float:
        from simulator import _active_eqp_count
        total = sum(self.p.eqp_qty.values()) or 1
        return _active_eqp_count(self.p, self._state) / total

    def _alloc_guide_reward(self) -> float:
        """가이드 준수 보상(조건부).

        - 전체 가동률이 guide_util_threshold 미만이면 0 (재공 부족 국면, 가이드 무의미).
        - task별 WIP==0이면 그 task 제외.
        - 가이드 tgt 대비 ±guide_band_pct 밴드 밖 편차만 페널티.
        """
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
```

- [ ] **Step 6: 테스트 통과 확인**

Run: `python -m pytest tests/test_env.py -k guide -v`
Expected: PASS (3개).

- [ ] **Step 7: 전체 env 테스트 회귀 확인**

Run: `python -m pytest tests/test_env.py -v`
Expected: 모두 PASS.

- [ ] **Step 8: 커밋**

```bash
git add config.py env.py tests/test_env.py
git commit -m "feat: 조건부 가이드 준수 보상(가동률 임계+밴드%)"
```

---

## Task 2: 환경 생성에 가이드/dwell 파라미터 일관 전달 (차원 버그 수정)

config 기본값을 ON으로 돌리기 전에, `train.py`/`test.py`가 동일한 `dwell_obs`·가이드
파라미터로 `DispatchEnv`를 만들도록 통일한다(현재 `test.py`는 `dwell_obs`를 안 넘겨
관측 차원이 어긋날 수 있음).

**Files:**
- Modify: `train.py` (`make_env`, `collect_teacher_dataset`)
- Modify: `test.py` (`_model_matches`, `_rl_policy_factory`)
- Test: `tests/test_sim_multimodel.py` (회귀로 사용; 신규 테스트는 Task 4)

- [ ] **Step 1: train.py 환경 생성에 가이드 파라미터 추가**

`train.py` `make_env`의 `DispatchEnv(...)` 호출(45~53행)에 두 인자 추가:

```python
    env = DispatchEnv(
        problem,
        max_tasks=config.MAX_TASKS,
        max_models=config.MAX_MODELS,
        dwell_lambda=config.DWELL_LAMBDA,
        alloc_lambda=config.ALLOC_LAMBDA,
        target_allocation=target,
        dwell_obs=config.DWELL_OBS,
        guide_util_threshold=config.GUIDE_UTIL_THRESHOLD,
        guide_band_pct=config.GUIDE_BAND_PCT,
    )
```

`collect_teacher_dataset`의 `DispatchEnv(...)`(62~66행)도 동일하게 두 인자 추가:

```python
        env = DispatchEnv(
            p, max_tasks=config.MAX_TASKS, max_models=config.MAX_MODELS,
            dwell_lambda=config.DWELL_LAMBDA, alloc_lambda=config.ALLOC_LAMBDA,
            target_allocation=target, dwell_obs=config.DWELL_OBS,
            guide_util_threshold=config.GUIDE_UTIL_THRESHOLD,
            guide_band_pct=config.GUIDE_BAND_PCT,
        )
```

- [ ] **Step 2: test.py 환경 생성에 dwell_obs 전달**

`test.py` `_model_matches`의 `DispatchEnv(problem, ...)`(20행)와 `_rl_policy_factory`의
`DispatchEnv(problem, ...)`(32행)를 각각 `dwell_obs=config.DWELL_OBS` 포함으로 수정:

```python
    env = DispatchEnv(problem, max_tasks=config.MAX_TASKS,
                      max_models=config.MAX_MODELS, dwell_obs=config.DWELL_OBS)
```

(두 곳 모두 동일하게.)

- [ ] **Step 3: 회귀 테스트 — 현 기본값(전부 OFF)에서 변화 없음 확인**

Run: `python -m pytest tests/test_env.py tests/test_train_smoke.py tests/test_report.py -v`
Expected: 모두 PASS (기본값 아직 OFF라 동작 동일).

- [ ] **Step 4: 커밋**

```bash
git add train.py test.py
git commit -m "fix: train/test DispatchEnv 생성에 dwell_obs·가이드 파라미터 일관 전달"
```

---

## Task 3: AllocationEnv 학습 완성 (`train_alloc_model` + `ppo_alloc.zip`)

해석식 `plan_target_allocation()`을 teacher로 BC(회귀) 후 PPO로 미세조정해 1-step 상위
배분 모델을 학습·저장한다.

**Files:**
- Modify: `train.py` (`train_alloc_model`, `train_model`)
- Test: `tests/test_alloc.py` (신규)

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_alloc.py` 신규 생성:

```python
from pathlib import Path
from simulator import load_problem
from config import BENCHMARKS_DIR
import train


def test_train_alloc_model_saves_and_respects_caps(tmp_path):
    p = load_problem(BENCHMARKS_DIR / "benchmark_02.json")
    out = tmp_path / "ppo_alloc.zip"
    model = train.train_alloc_model([p], ppo_steps=200, bc_epochs=5, save_path=out)
    assert out.exists()

    # 산출 배분이 모델별 eqp_qty 상한을 넘지 않아야 함
    from alloc_env import AllocationEnv
    import config as cfg
    env = AllocationEnv(p, max_tasks=cfg.MAX_TASKS, max_models=cfg.MAX_MODELS)
    obs, _ = env.reset()
    action, _ = model.predict(obs, deterministic=True)
    env.step(action)
    alloc = env.get_allocation()
    per_model = {}
    for (m, ti), c in alloc.items():
        per_model[m] = per_model.get(m, 0) + c
    for m, total in per_model.items():
        assert total <= p.eqp_qty[m]
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_alloc.py -v`
Expected: FAIL — `train`에 `train_alloc_model` 없음(AttributeError).

- [ ] **Step 3: `train_alloc_model` 구현**

`train.py`의 `import config` 아래(20행 부근)에 추가 import:

```python
import stable_baselines3 as sb3
```

`train.py`에 함수 추가(예: `_get_target_allocation` 위, 25행 부근):

```python
def _analytic_target_logits(env: "AllocationEnv") -> np.ndarray:
    """해석식 배분 → AllocationEnv 액션(모델별 task logit) 근사.

    fraction = alloc[m,ti]/eqp_qty[m] 를 log 로 변환(softmax 역근사).
    UPH 없는 조합은 -3(액션 하한)으로.
    """
    p = env.p
    analytic = p.plan_target_allocation()  # (model, ti) -> float
    logits = np.full((env.mm * env.mt,), -3.0, dtype=np.float32)
    eps = 1e-6
    for mi, model in enumerate(env.models):
        eqp = max(1.0, float(p.eqp_qty[model]))
        for ti in range(env.n_tasks):
            if p.uph_of(model, ti) is None:
                continue
            frac = analytic.get((model, ti), 0.0) / eqp
            logits[mi * env.mt + ti] = float(np.clip(np.log(frac + eps) + 3.0, -3.0, 3.0))
    return logits


def behavior_clone_alloc(model, problems, epochs: int, lr: float):
    """AllocationEnv 정책의 가우시안 평균을 해석식 target logit에 MSE 회귀."""
    if epochs <= 0:
        return
    obs_list, tgt_list = [], []
    for p in problems:
        env = AllocationEnv(p, max_tasks=config.MAX_TASKS, max_models=config.MAX_MODELS)
        obs, _ = env.reset()
        obs_list.append(obs)
        tgt_list.append(_analytic_target_logits(env))
    obs_t = torch.as_tensor(np.asarray(obs_list), dtype=torch.float32)
    tgt_t = torch.as_tensor(np.asarray(tgt_list), dtype=torch.float32)
    policy = model.policy
    policy.set_training_mode(True)
    opt = torch.optim.Adam(policy.parameters(), lr=lr)
    for _ in range(epochs):
        opt.zero_grad()
        dist = policy.get_distribution(obs_t)
        mean = dist.distribution.mean  # DiagGaussian 평균
        loss = torch.nn.functional.mse_loss(mean, tgt_t)
        loss.backward()
        opt.step()
    policy.set_training_mode(False)


def train_alloc_model(problems: list[ProblemInstance], ppo_steps: int = 5000,
                      bc_epochs: int = config.BC_EPOCHS, lr: float = config.BC_LR,
                      save_path: Path | None = None):
    """상위 배분(AllocationEnv) 1-step PPO 학습 → ppo_alloc.zip 저장."""
    save_path = Path(save_path) if save_path else (config.SAVED_MODELS_DIR / "ppo_alloc.zip")
    save_path.parent.mkdir(parents=True, exist_ok=True)

    def _shape(p):
        e = AllocationEnv(p, max_tasks=config.MAX_TASKS, max_models=config.MAX_MODELS)
        return (tuple(e.observation_space.shape), tuple(e.action_space.shape))
    base = _shape(problems[0])
    same = [p for p in problems if _shape(p) == base]

    def env_fn():
        return AllocationEnv(random.choice(same), max_tasks=config.MAX_TASKS,
                             max_models=config.MAX_MODELS)

    model = sb3.PPO("MlpPolicy", env_fn(), verbose=0, n_steps=64, batch_size=32)
    behavior_clone_alloc(model, same, bc_epochs, lr)
    model.set_env(env_fn())
    model.learn(total_timesteps=ppo_steps, progress_bar=False)
    model.save(save_path)
    return model
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_alloc.py -v`
Expected: PASS.

- [ ] **Step 5: `train_model`이 dispatch 전에 alloc 학습하도록 연결**

`train.py` `train_model` 안에서 `problems = same` 줄(129행 부근) 다음에 추가:

```python
    # 상위 배분 모델(가이드)을 먼저 학습 (USE_ALLOC_MODEL일 때만 실제 사용)
    if config.USE_ALLOC_MODEL and config.ALLOC_LAMBDA > 0.0:
        train_alloc_model(problems, ppo_steps=max(2000, ppo_steps // 10))
```

- [ ] **Step 6: smoke 회귀 확인**

Run: `python -m pytest tests/test_train_smoke.py -v`
Expected: PASS (기본값 OFF라 alloc 학습은 스킵됨 — Task 4에서 ON).

- [ ] **Step 7: 커밋**

```bash
git add train.py tests/test_alloc.py
git commit -m "feat: AllocationEnv 학습 완성(train_alloc_model→ppo_alloc.zip)"
```

---

## Task 4: 기본값 ON + 2-산출(가이드 수량 + 동적) 평가/리포트

기본값을 ON으로 돌리고, `evaluate_benchmark`가 가이드 수량을 함께 산출, 리포트가 이를
표시하게 한다.

**Files:**
- Modify: `config.py` (기본값 4개 ON)
- Modify: `test.py` (`evaluate_benchmark` 가이드 산출 추가)
- Modify: `report_output.py` (가이드 표 렌더)
- Modify: `test.py` (`render_markdown`에서 가이드 표 출력)
- Test: `tests/test_report.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_report.py` 끝에 추가:

```python
def test_evaluate_benchmark_includes_guide_allocation():
    from simulator import load_problem
    from config import BENCHMARKS_DIR
    import test as report
    p = load_problem(BENCHMARKS_DIR / "benchmark_02.json")
    res = report.evaluate_benchmark(p, model=None)
    assert "guide_allocation" in res
    # 가이드는 (model, task_index) -> 대수(float) 딕셔너리
    assert isinstance(res["guide_allocation"], dict)
    assert len(res["guide_allocation"]) > 0
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_report.py -k guide -v`
Expected: FAIL — `guide_allocation` 키 없음(KeyError/AssertionError).

- [ ] **Step 3: `evaluate_benchmark`에 가이드 산출 추가**

`test.py` `evaluate_benchmark`의 `out = {...}` 직후(70행 부근, `if model is not None` 위)에
추가:

```python
    out["guide_allocation"] = _guide_allocation(problem)
```

그리고 `test.py` 상단(import 아래, `_model_matches` 위)에 헬퍼 추가:

```python
def _guide_allocation(problem: ProblemInstance) -> dict:
    """가이드 수량(Mode 1). USE_ALLOC_MODEL이면 RL, 아니면 해석식."""
    if config.USE_ALLOC_MODEL:
        path = config.SAVED_MODELS_DIR / "ppo_alloc.zip"
        if path.exists():
            try:
                import stable_baselines3 as sb3
                from alloc_env import AllocationEnv
                env = AllocationEnv(problem, max_tasks=config.MAX_TASKS,
                                    max_models=config.MAX_MODELS)
                m = sb3.PPO.load(path)
                obs, _ = env.reset()
                action, _ = m.predict(obs, deterministic=True)
                env.step(action)
                return env.get_float_target()
            except Exception:
                pass
    return problem.plan_target_allocation()
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_report.py -k guide -v`
Expected: PASS.

- [ ] **Step 5: 가이드 표 렌더 헬퍼 추가**

`report_output.py` 끝에 추가:

```python
def render_guide_table(problem, guide_allocation: dict) -> str:
    """가이드 수량(Mode 1)을 공정×모델 대수 표(markdown)로."""
    if not guide_allocation:
        return ""
    lines = ["**가이드 수량 (재공 무한 기준 목표 배치)**", "",
             "| 공정(PLAN_PROD_KEY/OPER) | 모델 | 목표 대수 |", "|---|---|---|"]
    for (model, ti), cnt in sorted(guide_allocation.items(), key=lambda x: (x[0][1], x[0][0])):
        t = problem.tasks[ti]
        lines.append(f"| {t.plan_prod_key}/{t.oper_id} | {model} | {cnt:.1f} |")
    return "\n".join(lines)
```

- [ ] **Step 6: render_markdown에서 가이드 표 출력**

`test.py` `render_markdown`의 import(7~13행)에 `render_guide_table` 추가:

```python
from report_output import (
    render_detail_sections,
    render_html_report,
    enrich_eval_result,
    gantt_text,
    avg_utilization,
    render_guide_table,
)
```

`render_markdown`에서 `lines.append(f"## {name}")` 다음 줄(123행 부근)에 추가:

```python
        guide_md = render_guide_table(p, r.get("guide_allocation", {}))
        if guide_md:
            lines.append(guide_md)
            lines.append("")
```

- [ ] **Step 7: 기본값 ON**

`config.py`의 4개 줄(35~41행)을 수정:

```python
# WIP 체류시간 성형 계수 (0.0 = 비활성)
DWELL_LAMBDA = float(os.getenv("DWELL_LAMBDA", "0.3"))
# 목표 배분 가이드 계수 (0.0 = 비활성)
ALLOC_LAMBDA = float(os.getenv("ALLOC_LAMBDA", "0.3"))
# True면 obs에 dwell 슬롯 추가 (차원 변경 → 기존 모델과 비호환)
DWELL_OBS = os.getenv("DWELL_OBS", "true").lower() == "true"
# True면 AllocationEnv 상위 모델을 사용해 target_allocation 주입
USE_ALLOC_MODEL = os.getenv("USE_ALLOC_MODEL", "true").lower() == "true"
```

- [ ] **Step 8: 전체 테스트 회귀**

Run: `python -m pytest tests/ -v`
Expected: 모두 PASS. (실패 시 차원/기본값 영향 — 해당 테스트가 `DispatchEnv`를 기본
생성자로 만드는지 확인하고, 모델 재학습이 필요한 평가 테스트는 `model=None` 경로인지 점검.)

- [ ] **Step 9: 커밋**

```bash
git add config.py test.py report_output.py tests/test_report.py
git commit -m "feat: 기본 2-모드 ON + 가이드 수량 산출/리포트"
```

---

## Task 5: infer 2-산출 출력 + README 정리

`infer`가 rule_timekey마다 가이드+동적을 함께 보여주고, README의 미구현 `--mode` 설명을
실제 동작으로 교체한다.

**Files:**
- Modify: `run.py` (`cmd_infer` 출력)
- Modify: `README.md`
- Test: `tests/test_cli.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_cli.py` 끝에 추가(파일 상단의 기존 import 스타일을 따른다):

```python
def test_infer_prints_guide_and_dynamic(capsys, tmp_path):
    import run
    from config import BENCHMARKS_DIR
    args = run.build_parser().parse_args([
        "infer", "--benchmark-dataset", str(BENCHMARKS_DIR / "benchmark_01"),
        "--report", str(tmp_path / "r.md"), "--html", str(tmp_path / "r.html"),
    ])
    args.func(args)
    out = capsys.readouterr().out
    assert "가이드" in out          # 가이드 수량 산출 표시
    assert "달성률" in out          # 동적 운영 달성률 표시
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_cli.py -k guide_and_dynamic -v`
Expected: FAIL — 출력에 "가이드" 문자열 없음.

- [ ] **Step 3: cmd_infer 출력 보강**

`run.py` `cmd_infer`의 결과 루프(66~69행)를 아래로 교체:

```python
    for name, p in named:
        res = report.evaluate_benchmark(p, model)
        rate = res.get("rl", res["heuristic"])
        guide = res.get("guide_allocation", {})
        n_guide = len(guide)
        print(f"{p.rule_timekey}: [가이드 수량] 공정×모델 {n_guide}건 / "
              f"[동적 운영] 평균 계획달성률 {rate:.3f}")
        results[name] = (p, res)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_cli.py -k guide_and_dynamic -v`
Expected: PASS.

- [ ] **Step 5: README의 가짜 `--mode` 설명 정리**

`README.md`에서 다음을 수정한다:
- "### 모델 모드 (`--mode`)" 섹션과 그 하위 "#### 모드별 명령"의 `plan-only`/`wip-static`/
  `dynamic` CLI 예시 블록(현재 147~204행)을 삭제.
- 그 자리에 아래 단락으로 교체:

```markdown
### 2-모드 운영 (가이드 + 동적)

`train`/`infer`/`eval`은 rule_timekey마다 두 산출을 함께 만든다.

- **가이드 수량(Mode 1):** 재공을 무한으로 가정하고 계획·UPH·장비수·tool로 공정별 목표
  장비 대수를 산출(`AllocationEnv`, 없으면 `plan_target_allocation()` 해석식).
- **동적 운영(Mode 2):** 가이드를 *가급적* 준수하며 실제 재공에 따라 시간대별 재배치.
  가이드 준수는 가동률이 `GUIDE_UTIL_THRESHOLD` 이상일 때만, 가이드 대비
  `±GUIDE_BAND_PCT` 밴드 밖 편차에만 적용된다(재공 0인 공정은 제외).

관련 설정(`config.py`/`.env`): `USE_ALLOC_MODEL`, `ALLOC_LAMBDA`, `DWELL_LAMBDA`,
`DWELL_OBS`, `GUIDE_UTIL_THRESHOLD`, `GUIDE_BAND_PCT`.
```

- 하단 "구현 범위 / 미구현" 노트에서 `--mode … plan-only/wip-static/dynamic 분리`를
  "미구현" 목록에서 제거(이제 2-모드로 대체됨).

- [ ] **Step 6: 전체 테스트 회귀**

Run: `python -m pytest tests/ -v`
Expected: 모두 PASS.

- [ ] **Step 7: 커밋**

```bash
git add run.py README.md tests/test_cli.py
git commit -m "feat: infer 2-산출 출력 + README 2-모드 문서 정리"
```

---

## Self-Review 결과

- **스펙 커버리지:** Mode 1 완성=Task 3, 조건부 가이드 준수=Task 1, 차원 버그/파라미터
  배선=Task 2, 기본 ON + 2-산출 평가/리포트=Task 4, infer 출력 + README 정리=Task 5. 스펙
  7절 설정 키 6개 모두 Task 1·4에서 추가/변경. 스펙 6절 2-산출=Task 4·5.
- **비범위 준수:** DB write 경로·멀티피리어드·전 shape 일반화는 손대지 않음.
- **타입 일관성:** `guide_allocation`(dict (model,ti)->float)을 Task 4에서 정의하고 Task 5에서
  동일하게 사용. `train_alloc_model`/`behavior_clone_alloc`/`_analytic_target_logits` 시그니처 일관.
- **주의(실행자):** `DWELL_OBS=true` 기본화로 기존 `saved_models/ppo_dispatch.zip`은 차원
  불일치 → 평가 시 RL 미적용(휴리스틱 폴백)되거나 재학습 필요. 정상 동작이며, 새 baseline은
  `python run.py train --benchmark-dataset benchmarks/benchmark_03` 후 `eval`로 재생성.
