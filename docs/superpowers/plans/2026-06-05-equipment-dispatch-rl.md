# 장비 전환 스케줄링 강화학습 시스템 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 시간이 1시간씩 흐르는 동적 환경에서 매 시간 장비(모델별 대수)를 옮길지/유지할지 판단해 평균 계획달성률을 높이는, 모방학습+PPO 기반 장비 전환 스케줄러를 구축한다.

**Architecture:** 순수 도메인 시뮬레이터(1시간 step, WIP 흐름, batch 전환 시 1시간 Idle + tool 풀 제약)를 코어로 두고, 그 위에 Gymnasium 환경(model-count substep 액션 + 액션 마스킹)을 올린다. 휴리스틱 teacher 궤적으로 MaskablePPO 정책을 행동복제(BC) 초기화한 뒤 PPO로 강화한다. DB 없이 JSON 벤치마크로 전 파이프라인을 검증하고, `db.py`는 얇은 Oracle 어댑터로 둔다.

**Tech Stack:** Python 3.13, numpy, gymnasium 1.2, stable-baselines3 + sb3-contrib(MaskablePPO), torch(CPU), pytest, python-dotenv, oracledb(선택).

---

## File Structure

| 파일 | 책임 |
|------|------|
| `config.py` | 경로·하이퍼파라미터 상수, `.env` 로드(`load_config()`) |
| `simulator.py` | 도메인 모델(`Task`, `ProblemInstance`, `SimState`), `Simulator`(reset/valid_moves/apply_move/advance_hour/metrics), 휴리스틱 teacher, `load_problem`, `evaluate` |
| `env.py` | `DispatchEnv(gym.Env)` — 고정 액션 목록 + `action_masks()` |
| `train.py` | teacher 궤적 수집 → BC 사전학습 → MaskablePPO 학습 → 저장 → 벤치마크 평가 |
| `test.py` | 모델 로드 → 벤치마크별 RL/휴리스틱/최적 비교, 시간대별 표 + 간트, md 리포트 기록 |
| `db.py` | `.env` 기반 Oracle 어댑터(oracledb 선택). `RTS_LINEDSDB_INF` 조회→pivot→`ProblemInstance`, 결과/전환 테이블 기록 |
| `run.py` | CLI 디스패처(`train`/`infer`/`eval`) |
| `benchmarks/benchmark_01..07.json` | 최적해 기지 벤치마크 7종 |
| `.env` / `.gitignore` / `pyproject.toml` | 설정·제외·의존성 |
| `tests/` | pytest 단위 테스트 |

각 파일은 단일 책임을 가지며 코어(`simulator.py`)는 gym/sb3/DB에 의존하지 않는다(테스트 용이).

---

## Task 0: 프로젝트 초기화

**Files:**
- Create: `.gitignore`, `pyproject.toml`, `config.py`, `.env`, `tests/__init__.py`
- Create dirs: `data/`, `saved_models/`, `benchmarks/`, `tests/`

- [ ] **Step 1: git 저장소 초기화 및 디렉토리 생성**

Run:
```bash
git init
mkdir -p data saved_models benchmarks tests artifacts/inference
```
Expected: `Initialized empty Git repository`.

- [ ] **Step 2: `.gitignore` 작성**

Create `.gitignore`:
```gitignore
.env
__pycache__/
*.pyc
saved_models/*.zip
saved_models/*.pt
data/*
!data/.gitkeep
artifacts/
.pytest_cache/
```

- [ ] **Step 3: `pyproject.toml` 작성**

Create `pyproject.toml`:
```toml
[project]
name = "equipment-dispatch-rl"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["numpy"]

[project.optional-dependencies]
rl = ["gymnasium>=1.0", "stable-baselines3>=2.7", "sb3-contrib>=2.7", "torch"]
oracle = ["oracledb", "python-dotenv"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 4: `.env` 작성 (커밋되지 않음)**

Create `.env`:
```dotenv
ORACLE_USER=sys
ORACLE_PASSWORD=sys
ORACLE_DSN=localhost:1521/XEPDB1
RTS_CRT_USER_ID=RL_AGENT
```

- [ ] **Step 5: `config.py` 작성**

Create `config.py`:
```python
"""전역 설정과 .env 로더."""
from __future__ import annotations
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BENCHMARKS_DIR = ROOT / "benchmarks"
SAVED_MODELS_DIR = ROOT / "saved_models"
DATA_DIR = ROOT / "data"
ARTIFACTS_DIR = ROOT / "artifacts"
REPORT_PATH = ROOT / "MODEL_REPORT.md"

MODEL_PATH = SAVED_MODELS_DIR / "ppo_dispatch.zip"
BC_POLICY_PATH = SAVED_MODELS_DIR / "bc_init.pt"

# 학습 하이퍼파라미터
DEFAULT_PPO_STEPS = 50_000
BC_EPOCHS = 300
BC_LR = 1e-3
DEFAULT_SWITCH_TIME_HOURS = 1

# 출력 테이블 (db.py)
RESULT_TABLE = "RTS_RSLT_MAS"
RESULT_HIS_TABLE = "RTS_RSLT_HIS"
CONV_TABLE = "RTS_CONV_INF"
CONV_HIS_TABLE = "RTS_CONV_HIS"


def load_config() -> dict:
    """.env(있으면)와 환경변수에서 DB 설정을 읽는다."""
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except Exception:
        pass
    return {
        "user": os.getenv("ORACLE_USER", "dispatcher"),
        "password": os.getenv("ORACLE_PASSWORD", "dispatcher"),
        "dsn": os.getenv("ORACLE_DSN", "localhost:1521/XEPDB1"),
        "crt_user_id": os.getenv("RTS_CRT_USER_ID", "RL_AGENT"),
    }
```

- [ ] **Step 6: `tests/__init__.py` 와 `data/.gitkeep` 생성**

Create empty `tests/__init__.py` and empty `data/.gitkeep`.

- [ ] **Step 7: 커밋**

```bash
git add .gitignore pyproject.toml config.py tests/__init__.py data/.gitkeep
git commit -m "chore: scaffold project structure and config"
```

---

## Task 1: 도메인 모델 (ProblemInstance, 로더)

**Files:**
- Create: `simulator.py`
- Test: `tests/test_domain.py`
- Create: `benchmarks/benchmark_01.json`

- [ ] **Step 1: benchmark_01 (전환 불필요 기본) 작성**

Create `benchmarks/benchmark_01.json`:
```json
{
  "rule_timekey": "2026052922500000",
  "horizon_hours": 3,
  "switch_time_hours": 1,
  "tasks": [
    {"plan_prod_key": "P1", "oper_id": "OP10", "oper_seq": 1, "batch_id": "B1", "plan_qty": 300, "init_wip": 1000}
  ],
  "uph": [
    {"plan_prod_key": "P1", "oper_id": "OP10", "eqp_model": "M1", "uph": 100}
  ],
  "eqp_qty": {"M1": 1},
  "init_assign": [
    {"eqp_model": "M1", "plan_prod_key": "P1", "oper_id": "OP10", "count": 1}
  ],
  "tool_qty": [
    {"batch_id": "B1", "eqp_model": "M1", "tool_qty": 1}
  ],
  "conv_groups": {"G1": ["B1"]},
  "ground_truth": {"plan_achievement": 1.0, "note": "1대 x 100UPH x 3h = 300 = plan, 전환 없음"}
}
```

- [ ] **Step 2: 실패하는 도메인 테스트 작성**

Create `tests/test_domain.py`:
```python
from simulator import load_problem
from config import BENCHMARKS_DIR


def test_load_problem_indexes_tasks_and_uph():
    p = load_problem(BENCHMARKS_DIR / "benchmark_01.json")
    assert p.rule_timekey == "2026052922500000"
    assert p.horizon_hours == 3
    assert len(p.tasks) == 1
    t = p.tasks[0]
    assert (t.plan_prod_key, t.oper_id, t.batch_id, t.plan_qty) == ("P1", "OP10", "B1", 300)
    # uph 조회: (model, task_index)
    assert p.uph_of("M1", 0) == 100.0
    # 부적격(미등록 model)은 None
    assert p.uph_of("M9", 0) is None
    # 초기 배치
    assert p.init_assign[("M1", 0)] == 1
    # batch / 전환그룹
    assert p.batch_of(0) == "B1"
    assert p.conv_group_of("B1") == "G1"


def test_next_task_index_follows_oper_seq():
    p = load_problem(BENCHMARKS_DIR / "benchmark_01.json")
    # 단일 OPER → 다음 공정 없음
    assert p.next_task_index(0) is None
```

- [ ] **Step 3: 테스트 실행해 실패 확인**

Run: `python -m pytest tests/test_domain.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'simulator'` 또는 `ImportError`.

- [ ] **Step 4: `simulator.py` 도메인 모델 구현**

Create `simulator.py`:
```python
"""장비 전환 스케줄링 도메인 모델 + 1시간 step 시뮬레이터.

gym/sb3/DB에 의존하지 않는 순수 코어.
"""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Task:
    plan_prod_key: str
    oper_id: str
    oper_seq: int
    batch_id: str
    plan_qty: int
    init_wip: int


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

    def models(self) -> list[str]:
        return sorted(self.eqp_qty)


def load_problem(path: str | Path) -> ProblemInstance:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    tasks = [
        Task(t["plan_prod_key"], t["oper_id"], int(t["oper_seq"]),
             t["batch_id"], int(t["plan_qty"]), int(t.get("init_wip", 0)))
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
    return ProblemInstance(
        rule_timekey=data["rule_timekey"],
        horizon_hours=int(data["horizon_hours"]),
        switch_time_hours=int(data.get("switch_time_hours", 1)),
        tasks=tasks,
        _uph=uph,
        eqp_qty={k: int(v) for k, v in data["eqp_qty"].items()},
        init_assign=init_assign,
        tool_qty=tool_qty,
        conv_groups={k: list(v) for k, v in data["conv_groups"].items()},
        ground_truth=data.get("ground_truth", {}),
    )
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `python -m pytest tests/test_domain.py -v`
Expected: PASS (2 passed).

- [ ] **Step 6: 커밋**

```bash
git add simulator.py tests/test_domain.py benchmarks/benchmark_01.json
git commit -m "feat: domain model and problem loader"
```

---

## Task 2: 시뮬레이터 — 상태, 생산, WIP 흐름

**Files:**
- Modify: `simulator.py` (append `SimState`, `Simulator`)
- Test: `tests/test_sim_production.py`

- [ ] **Step 1: 실패하는 생산/WIP 흐름 테스트 작성**

Create `tests/test_sim_production.py`:
```python
from simulator import load_problem, Simulator
from config import BENCHMARKS_DIR


def test_single_task_production_capped_by_capacity_and_wip():
    p = load_problem(BENCHMARKS_DIR / "benchmark_01.json")
    sim = Simulator(p)
    s = sim.reset()
    # 1대 x 100 UPH, WIP 1000 → 시간당 100 생산
    sim.advance_hour(s)
    assert s.produced[0] == 100
    assert s.wip[0] == 900
    sim.advance_hour(s)
    sim.advance_hour(s)
    assert s.produced[0] == 300
    m = sim.metrics(s)
    assert m["plan_achievement"] == 1.0  # 300/300


def test_production_capped_by_wip_when_queue_small():
    p = load_problem(BENCHMARKS_DIR / "benchmark_01.json")
    p.tasks[0] = p.tasks[0].__class__(  # init_wip을 50으로 축소
        "P1", "OP10", 1, "B1", 300, 50)
    sim = Simulator(p)
    s = sim.reset()
    sim.advance_hour(s)
    assert s.produced[0] == 50  # WIP 상한
    sim.advance_hour(s)
    assert s.produced[0] == 50  # 더 생산 못함
```

- [ ] **Step 2: 테스트 실행해 실패 확인**

Run: `python -m pytest tests/test_sim_production.py -v`
Expected: FAIL — `ImportError: cannot import name 'Simulator'`.

- [ ] **Step 3: `SimState` 와 `Simulator`(생산/WIP) 구현**

Append to `simulator.py`:
```python
from dataclasses import dataclass as _dc


@_dc
class SimState:
    hour: int
    produced: dict[int, int]                 # task_index -> 누적 생산
    wip: dict[int, int]                       # task_index -> 현재 가용 유입재공
    assign: dict[tuple[str, int], int]        # (model, task_index) -> 배치 대수
    idle: dict[tuple[str, int], int]          # (model, task_index) -> 전환 Idle 잔여대수
    tool_used: dict[tuple[str, str], int]     # (batch_id, model) -> 사용중 tool


class Simulator:
    """1시간 단위로 전이하는 결정론적 시뮬레이터."""

    def __init__(self, problem: ProblemInstance):
        self.p = problem

    def reset(self) -> SimState:
        p = self.p
        wip = {i: t.init_wip for i, t in enumerate(p.tasks)}
        produced = {i: 0 for i in range(len(p.tasks))}
        assign = dict(p.init_assign)
        idle = {}
        tool_used: dict[tuple[str, str], int] = {}
        for (model, ti), cnt in assign.items():
            key = (p.batch_of(ti), model)
            tool_used[key] = tool_used.get(key, 0) + cnt
        return SimState(0, produced, wip, assign, idle, tool_used)

    def advance_hour(self, s: SimState) -> None:
        """배치된(Idle 아닌) 장비로 1시간 생산 후 WIP를 다음 공정으로 흘린다."""
        p = self.p
        inflow: dict[int, int] = {}
        for ti in range(len(p.tasks)):
            capacity = 0.0
            for model in p.models():
                active = s.assign.get((model, ti), 0) - s.idle.get((model, ti), 0)
                if active <= 0:
                    continue
                uph = p.uph_of(model, ti)
                if uph:
                    capacity += active * uph
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
        # 전환 Idle 1시간 차감
        for key in list(s.idle):
            s.idle[key] = max(0, s.idle[key] - 1)
            if s.idle[key] == 0:
                del s.idle[key]
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
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_sim_production.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: 커밋**

```bash
git add simulator.py tests/test_sim_production.py
git commit -m "feat: simulator hourly production and WIP flow"
```

---

## Task 3: 시뮬레이터 — 이동(전환) 규칙과 tool 풀

**Files:**
- Modify: `simulator.py` (append `Move`, `valid_moves`, `apply_move`)
- Test: `tests/test_sim_moves.py`
- Create: `benchmarks/benchmark_02.json`

- [ ] **Step 1: benchmark_02 (단일 batch 전환 필요) 작성**

Create `benchmarks/benchmark_02.json`:
```json
{
  "rule_timekey": "2026052922500000",
  "horizon_hours": 4,
  "switch_time_hours": 1,
  "tasks": [
    {"plan_prod_key": "PA", "oper_id": "OP10", "oper_seq": 1, "batch_id": "B1", "plan_qty": 200, "init_wip": 1000},
    {"plan_prod_key": "PB", "oper_id": "OP10", "oper_seq": 1, "batch_id": "B2", "plan_qty": 100, "init_wip": 1000}
  ],
  "uph": [
    {"plan_prod_key": "PA", "oper_id": "OP10", "eqp_model": "M1", "uph": 100},
    {"plan_prod_key": "PB", "oper_id": "OP10", "eqp_model": "M1", "uph": 100}
  ],
  "eqp_qty": {"M1": 1},
  "init_assign": [
    {"eqp_model": "M1", "plan_prod_key": "PA", "oper_id": "OP10", "count": 1}
  ],
  "tool_qty": [
    {"batch_id": "B1", "eqp_model": "M1", "tool_qty": 1},
    {"batch_id": "B2", "eqp_model": "M1", "tool_qty": 1}
  ],
  "conv_groups": {"G1": ["B1", "B2"]},
  "ground_truth": {"plan_achievement": 1.0, "note": "PA 2h(200) → 전환 1h Idle → PB 1h(100). 총 4h."}
}
```

- [ ] **Step 2: 실패하는 이동 테스트 작성**

Create `tests/test_sim_moves.py`:
```python
from simulator import load_problem, Simulator, Move
from config import BENCHMARKS_DIR


def test_cross_batch_move_costs_idle_and_swaps_tool():
    p = load_problem(BENCHMARKS_DIR / "benchmark_02.json")
    sim = Simulator(p)
    s = sim.reset()
    # 초기: M1 1대가 task0(PA,B1)
    assert s.assign[("M1", 0)] == 1
    assert s.tool_used[("B1", "M1")] == 1
    sim.apply_move(s, Move("M1", 0, 1))  # PA(B1) -> PB(B2)
    assert s.assign.get(("M1", 0), 0) == 0
    assert s.assign[("M1", 1)] == 1
    assert s.idle[("M1", 1)] == 1                 # 전환 1시간 Idle
    assert s.tool_used.get(("B1", "M1"), 0) == 0  # from tool 반환
    assert s.tool_used[("B2", "M1")] == 1         # to tool 소진
    # 전환 직후 1시간은 Idle → 생산 0
    sim.advance_hour(s)
    assert s.produced[1] == 0


def test_valid_moves_masks_tool_shortage_and_out_of_group():
    p = load_problem(BENCHMARKS_DIR / "benchmark_02.json")
    sim = Simulator(p)
    s = sim.reset()
    moves = sim.valid_moves(s)
    # B1->B2 같은 그룹 + tool 여유 → 가능
    assert Move("M1", 0, 1) in moves
    # to-batch tool을 모두 소진시키면 더 이상 전환 불가
    s.tool_used[("B2", "M1")] = 1
    moves2 = sim.valid_moves(s)
    assert Move("M1", 0, 1) not in moves2


def test_same_batch_move_is_free_no_idle():
    # 같은 batch 내 다른 task로의 이동은 tool 변화/Idle 없음
    p = load_problem(BENCHMARKS_DIR / "benchmark_02.json")
    # task1의 batch를 B1로 바꿔 같은 batch 시나리오 구성
    p.tasks[1] = p.tasks[1].__class__("PB", "OP10", 1, "B1", 100, 1000)
    p._uph[("M1", 1)] = 100.0
    sim = Simulator(p)
    s = sim.reset()
    sim.apply_move(s, Move("M1", 0, 1))
    assert ("M1", 1) not in s.idle           # Idle 없음
    assert s.tool_used.get(("B1", "M1")) == 1  # 같은 batch → tool 수 불변
```

- [ ] **Step 3: 테스트 실행해 실패 확인**

Run: `python -m pytest tests/test_sim_moves.py -v`
Expected: FAIL — `ImportError: cannot import name 'Move'`.

- [ ] **Step 4: `Move`, `valid_moves`, `apply_move` 구현**

Append to `simulator.py`:
```python
from typing import NamedTuple


class Move(NamedTuple):
    model: str
    from_index: int
    to_index: int


class Simulator(Simulator):  # 동일 클래스에 메서드 추가 (아래 메서드를 Task 2의 Simulator 본문에 합쳐도 됨)
    def valid_moves(self, s: SimState) -> list[Move]:
        """현재 상태에서 둘 수 있는 (model, from, to) 이동 목록."""
        p = self.p
        out: list[Move] = []
        n = len(p.tasks)
        for model in p.models():
            for fi in range(n):
                # 옮길 수 있는 (Idle 아닌) 대수가 있어야 함
                movable = s.assign.get((model, fi), 0) - s.idle.get((model, fi), 0)
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
            s.idle[(model, ti)] = s.idle.get((model, ti), 0) + p.switch_time_hours
            s.tool_used[(fb, model)] = s.tool_used.get((fb, model), 0) - 1
            s.tool_used[(tb, model)] = s.tool_used.get((tb, model), 0) + 1
```

> 구현 메모: 위 `class Simulator(Simulator)` 패턴 대신, 실제로는 Task 2에서 만든 `Simulator` 클래스 본문에 `valid_moves`/`apply_move` 두 메서드를 직접 추가하라(상속 트릭은 피한다). `Move`/`NamedTuple` import 줄은 파일 상단으로 옮긴다.

- [ ] **Step 5: 테스트 통과 확인**

Run: `python -m pytest tests/test_sim_moves.py -v`
Expected: PASS (3 passed).

- [ ] **Step 6: 커밋**

```bash
git add simulator.py tests/test_sim_moves.py benchmarks/benchmark_02.json
git commit -m "feat: simulator move rules with idle and tool pool"
```

---

## Task 4: 휴리스틱 teacher 와 정책 실행/평가

**Files:**
- Modify: `simulator.py` (append `heuristic_actions`, `run_policy`, `evaluate`)
- Test: `tests/test_teacher.py`

- [ ] **Step 1: 실패하는 teacher 테스트 작성**

Create `tests/test_teacher.py`:
```python
from simulator import load_problem, Simulator, heuristic_actions, run_policy
from config import BENCHMARKS_DIR


def _teacher_policy(sim, s):
    return heuristic_actions(sim, s)


def test_heuristic_reaches_ground_truth_bench01():
    p = load_problem(BENCHMARKS_DIR / "benchmark_01.json")
    sim = Simulator(p)
    final, trace = run_policy(sim, _teacher_policy)
    m = sim.metrics(final)
    assert m["plan_achievement"] >= p.ground_truth["plan_achievement"] - 1e-6


def test_heuristic_reaches_ground_truth_bench02_with_conversion():
    p = load_problem(BENCHMARKS_DIR / "benchmark_02.json")
    sim = Simulator(p)
    final, trace = run_policy(sim, _teacher_policy)
    m = sim.metrics(final)
    # PA 200 + PB 100 모두 달성 (전환 1h Idle 포함 4h 안에)
    assert m["plan_achievement"] >= 0.999
    # trace는 (hour, [moves]) 시퀀스
    assert len(trace) == p.horizon_hours
```

- [ ] **Step 2: 테스트 실행해 실패 확인**

Run: `python -m pytest tests/test_teacher.py -v`
Expected: FAIL — `ImportError: cannot import name 'heuristic_actions'`.

- [ ] **Step 3: teacher / run_policy / evaluate 구현**

Append to `simulator.py`:
```python
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
            # from task가 이미 잉여(잔여 0 또는 WIP 0)일 때만 이동 가치
            from_rem = _remaining(p, s, mv.from_index)
            from_wip = s.wip[mv.from_index]
            to_rem = _remaining(p, s, mv.to_index)
            to_wip = s.wip[mv.to_index]
            uph_to = p.uph_of(mv.model, mv.to_index) or 0.0
            same_batch = p.batch_of(mv.from_index) == p.batch_of(mv.to_index)
            # from이 여전히 생산 중이면(잔여>0 & WIP>0) 옮기지 않는다
            if from_rem > 0 and from_wip > 0:
                continue
            # to에서 이번 horizon 잔여시간 동안 추가로 낼 수 있는 양
            hours_left = p.horizon_hours - s.hour - (0 if same_batch else p.switch_time_hours)
            gain = min(to_rem, to_wip, uph_to * max(0, hours_left))
            if gain > best_gain:
                best, best_gain = mv, gain
        if best is None:
            break
        sim.apply_move(s, best)
        moves.append(best)
    return moves


def run_policy(sim: "Simulator", policy_fn) -> tuple[SimState, list]:
    """policy_fn(sim, state)->list[Move]를 매 시간 적용하며 horizon까지 시뮬레이션."""
    s = sim.reset()
    trace = []
    while not sim.is_done(s):
        applied = policy_fn(sim, s)
        snapshot = {(m, ti): c for (m, ti), c in s.assign.items()}
        sim.advance_hour(s)
        trace.append((s.hour - 1, applied, snapshot))
    return s, trace


def evaluate(problem: ProblemInstance) -> dict:
    """휴리스틱 vs ground_truth 비교."""
    sim = Simulator(problem)
    final, trace = run_policy(sim, heuristic_actions)
    m = sim.metrics(final)
    return {
        "heuristic": m["plan_achievement"],
        "optimal": problem.ground_truth.get("plan_achievement"),
        "per_task": m["per_task"],
        "trace": trace,
    }
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_teacher.py -v`
Expected: PASS (2 passed). 실패 시 `heuristic_actions`의 `from_rem>0 and from_wip>0` 가드와 `hours_left` 계산을 점검.

- [ ] **Step 5: 커밋**

```bash
git add simulator.py tests/test_teacher.py
git commit -m "feat: heuristic teacher, policy runner, evaluate"
```

---

## Task 5: 나머지 벤치마크 5종 (03–07)

**Files:**
- Create: `benchmarks/benchmark_03.json` … `benchmark_07.json`
- Test: `tests/test_benchmarks.py`

- [ ] **Step 1: benchmark_03 (병목: 특정 공정에 장비 몰림) 작성**

Create `benchmarks/benchmark_03.json`:
```json
{
  "rule_timekey": "2026052922500000",
  "horizon_hours": 4,
  "switch_time_hours": 1,
  "tasks": [
    {"plan_prod_key": "P1", "oper_id": "OP10", "oper_seq": 1, "batch_id": "B1", "plan_qty": 200, "init_wip": 1000},
    {"plan_prod_key": "P1", "oper_id": "OP20", "oper_seq": 2, "batch_id": "B2", "plan_qty": 200, "init_wip": 0}
  ],
  "uph": [
    {"plan_prod_key": "P1", "oper_id": "OP10", "eqp_model": "M1", "uph": 100},
    {"plan_prod_key": "P1", "oper_id": "OP20", "eqp_model": "M1", "uph": 100}
  ],
  "eqp_qty": {"M1": 2},
  "init_assign": [
    {"eqp_model": "M1", "plan_prod_key": "P1", "oper_id": "OP10", "count": 2}
  ],
  "tool_qty": [
    {"batch_id": "B1", "eqp_model": "M1", "tool_qty": 2},
    {"batch_id": "B2", "eqp_model": "M1", "tool_qty": 2}
  ],
  "conv_groups": {"G1": ["B1", "B2"]},
  "ground_truth": {"plan_achievement": 1.0, "note": "OP10 2대 1h로 200 생산→OP20 WIP 확보. 일부 장비 OP20(B2)로 전환해 후공정 달성. OP20 init_wip=0이라 앞공정 빌드 필수."}
}
```

- [ ] **Step 2: benchmark_04 (UPH 이질성: 모델 선택) 작성**

Create `benchmarks/benchmark_04.json`:
```json
{
  "rule_timekey": "2026052922500000",
  "horizon_hours": 2,
  "switch_time_hours": 1,
  "tasks": [
    {"plan_prod_key": "P1", "oper_id": "OP10", "oper_seq": 1, "batch_id": "B1", "plan_qty": 300, "init_wip": 1000},
    {"plan_prod_key": "P2", "oper_id": "OP10", "oper_seq": 1, "batch_id": "B1", "plan_qty": 100, "init_wip": 1000}
  ],
  "uph": [
    {"plan_prod_key": "P1", "oper_id": "OP10", "eqp_model": "M_FAST", "uph": 150},
    {"plan_prod_key": "P1", "oper_id": "OP10", "eqp_model": "M_SLOW", "uph": 50},
    {"plan_prod_key": "P2", "oper_id": "OP10", "eqp_model": "M_FAST", "uph": 50},
    {"plan_prod_key": "P2", "oper_id": "OP10", "eqp_model": "M_SLOW", "uph": 50}
  ],
  "eqp_qty": {"M_FAST": 1, "M_SLOW": 1},
  "init_assign": [
    {"eqp_model": "M_FAST", "plan_prod_key": "P2", "oper_id": "OP10", "count": 1},
    {"eqp_model": "M_SLOW", "plan_prod_key": "P1", "oper_id": "OP10", "count": 1}
  ],
  "tool_qty": [
    {"batch_id": "B1", "eqp_model": "M_FAST", "tool_qty": 2},
    {"batch_id": "B1", "eqp_model": "M_SLOW", "tool_qty": 2}
  ],
  "conv_groups": {"G1": ["B1"]},
  "ground_truth": {"plan_achievement": 1.0, "note": "같은 batch라 전환 무비용. M_FAST를 P1(150x2h=300)에, M_SLOW를 P2(50x2h=100)에 두면 둘 다 100%. 초기 배치는 반대라 교체 필요."}
}
```

- [ ] **Step 3: benchmark_05 (Capacity 초과) 작성**

Create `benchmarks/benchmark_05.json`:
```json
{
  "rule_timekey": "2026052922500000",
  "horizon_hours": 2,
  "switch_time_hours": 1,
  "tasks": [
    {"plan_prod_key": "P1", "oper_id": "OP10", "oper_seq": 1, "batch_id": "B1", "plan_qty": 1000, "init_wip": 5000}
  ],
  "uph": [
    {"plan_prod_key": "P1", "oper_id": "OP10", "eqp_model": "M1", "uph": 100}
  ],
  "eqp_qty": {"M1": 2},
  "init_assign": [
    {"eqp_model": "M1", "plan_prod_key": "P1", "oper_id": "OP10", "count": 2}
  ],
  "tool_qty": [
    {"batch_id": "B1", "eqp_model": "M1", "tool_qty": 2}
  ],
  "conv_groups": {"G1": ["B1"]},
  "ground_truth": {"plan_achievement": 0.4, "note": "최대 2대x100x2h=400 vs 계획 1000 → 0.4 상한. 어떤 정책도 0.4 초과 불가."}
}
```

- [ ] **Step 4: benchmark_06 (WIP 부족) 작성**

Create `benchmarks/benchmark_06.json`:
```json
{
  "rule_timekey": "2026052922500000",
  "horizon_hours": 3,
  "switch_time_hours": 1,
  "tasks": [
    {"plan_prod_key": "P1", "oper_id": "OP10", "oper_seq": 1, "batch_id": "B1", "plan_qty": 300, "init_wip": 50}
  ],
  "uph": [
    {"plan_prod_key": "P1", "oper_id": "OP10", "eqp_model": "M1", "uph": 100}
  ],
  "eqp_qty": {"M1": 2},
  "init_assign": [
    {"eqp_model": "M1", "plan_prod_key": "P1", "oper_id": "OP10", "count": 2}
  ],
  "tool_qty": [
    {"batch_id": "B1", "eqp_model": "M1", "tool_qty": 2}
  ],
  "conv_groups": {"G1": ["B1"]},
  "ground_truth": {"plan_achievement": 0.1667, "note": "WIP 50개 한계 → 50/300=0.1667. 장비 남아도 재공 부족."}
}
```

- [ ] **Step 5: benchmark_07 (Thrashing 회피) 작성**

Create `benchmarks/benchmark_07.json`:
```json
{
  "rule_timekey": "2026052922500000",
  "horizon_hours": 4,
  "switch_time_hours": 1,
  "tasks": [
    {"plan_prod_key": "PA", "oper_id": "OP10", "oper_seq": 1, "batch_id": "B1", "plan_qty": 100, "init_wip": 1000},
    {"plan_prod_key": "PB", "oper_id": "OP10", "oper_seq": 1, "batch_id": "B2", "plan_qty": 100, "init_wip": 1000}
  ],
  "uph": [
    {"plan_prod_key": "PA", "oper_id": "OP10", "eqp_model": "M1", "uph": 100},
    {"plan_prod_key": "PB", "oper_id": "OP10", "eqp_model": "M1", "uph": 100}
  ],
  "eqp_qty": {"M1": 1},
  "init_assign": [
    {"eqp_model": "M1", "plan_prod_key": "PA", "oper_id": "OP10", "count": 1}
  ],
  "tool_qty": [
    {"batch_id": "B1", "eqp_model": "M1", "tool_qty": 1},
    {"batch_id": "B2", "eqp_model": "M1", "tool_qty": 1}
  ],
  "conv_groups": {"G1": ["B1", "B2"]},
  "ground_truth": {"plan_achievement": 1.0, "note": "PA 1h(100)→전환1h→PB 1h(100): 3h 사용, 1회 전환으로 둘 다 100%. 잦은 전환은 Idle로 손해."}
}
```

- [ ] **Step 6: 전체 벤치마크가 휴리스틱으로 ground_truth에 도달하는지 테스트**

Create `tests/test_benchmarks.py`:
```python
import pytest
from simulator import load_problem, evaluate
from config import BENCHMARKS_DIR

BENCHES = sorted(BENCHMARKS_DIR.glob("benchmark_*.json"))


@pytest.mark.parametrize("path", BENCHES, ids=lambda p: p.stem)
def test_heuristic_matches_ground_truth(path):
    p = load_problem(path)
    res = evaluate(p)
    opt = res["optimal"]
    assert opt is not None, f"{path.name}: ground_truth.plan_achievement 누락"
    # 휴리스틱은 최적 이하이되, 설계상 최적에 도달해야 함(허용오차 2%p)
    assert res["heuristic"] >= opt - 0.02, (
        f"{path.name}: heuristic {res['heuristic']} < optimal {opt}")
    assert res["heuristic"] <= opt + 1e-6, (
        f"{path.name}: heuristic {res['heuristic']} > optimal {opt} (최적해 오류?)")
```

- [ ] **Step 7: 테스트 실행 및 휴리스틱 보정**

Run: `python -m pytest tests/test_benchmarks.py -v`
Expected: 7 passed. 일부 케이스(03/04/07)에서 휴리스틱이 최적에 못 미치면 `heuristic_actions`를 보정:
- bench04(같은 batch 교체): from_rem>0 가드가 교체를 막으면, **같은 batch이고 to의 UPH가 from보다 높아 총량이 늘 때**도 이동 허용하도록 조건 추가.
- bench03(빌드-어헤드): 후공정 WIP가 0이고 앞공정 잔여=0이면 앞→뒤 전환 허용.

보정 시 `heuristic_actions`의 가드를 다음으로 교체(append/replace):
```python
            # from이 여전히 유효 생산 중이면 기본적으로 유지하되,
            # (a) 같은 batch에서 to의 UPH가 더 높아 총 생산이 늘거나
            # (b) to가 잔여>0인데 현재 장비가 없을 때는 이동 허용
            uph_from = p.uph_of(mv.model, mv.from_index) or 0.0
            to_has_eqp = any(s.assign.get((m, mv.to_index), 0) > 0 for m in p.models())
            if from_rem > 0 and from_wip > 0:
                better_here = same_batch and uph_to > uph_from
                fill_empty = to_rem > 0 and not to_has_eqp
                if not (better_here or fill_empty):
                    continue
```

- [ ] **Step 8: 커밋**

```bash
git add benchmarks/benchmark_0[3-7].json tests/test_benchmarks.py simulator.py
git commit -m "feat: 7 benchmark datasets with known optima + heuristic tuning"
```

---

## Task 6: Gymnasium 환경 + 액션 마스킹

**Files:**
- Create: `env.py`
- Test: `tests/test_env.py`

- [ ] **Step 1: 실패하는 환경 테스트 작성**

Create `tests/test_env.py`:
```python
import numpy as np
from simulator import load_problem
from env import DispatchEnv
from config import BENCHMARKS_DIR


def test_env_reset_obs_shape_and_mask():
    p = load_problem(BENCHMARKS_DIR / "benchmark_02.json")
    env = DispatchEnv(p)
    obs, info = env.reset(seed=0)
    assert obs.shape == (env.observation_space.shape[0],)
    mask = env.action_masks()
    assert mask.shape == (env.action_space.n,)
    assert mask[0] == True   # commit은 항상 가능


def test_env_commit_advances_hour_and_terminates():
    p = load_problem(BENCHMARKS_DIR / "benchmark_01.json")
    env = DispatchEnv(p)
    env.reset(seed=0)
    done = False
    steps = 0
    total_r = 0.0
    while not done and steps < 100:
        obs, r, term, trunc, info = env.step(0)  # 매번 commit
        total_r += r
        done = term or trunc
        steps += 1
    assert done
    assert info["plan_achievement"] == 1.0  # bench01은 그냥 두면 100%


def test_env_masks_invalid_moves_match_simulator():
    p = load_problem(BENCHMARKS_DIR / "benchmark_02.json")
    env = DispatchEnv(p)
    env.reset(seed=0)
    mask = env.action_masks()
    # 유효 이동 수 + 1(commit) == 마스크 True 개수
    from simulator import Simulator
    sim = Simulator(p)
    s = sim.reset()
    assert mask.sum() == len(sim.valid_moves(s)) + 1
```

- [ ] **Step 2: 테스트 실행해 실패 확인**

Run: `python -m pytest tests/test_env.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'env'`.

- [ ] **Step 3: `env.py` 구현**

Create `env.py`:
```python
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
        forced_commit = False
        if action == 0:
            self._commit()
        else:
            mv = self.move_list[action - 1]
            if mv in set(self.sim.valid_moves(s)):
                self.sim.apply_move(s, mv)
            self._substeps += 1
            if self._substeps >= self.max_substeps:
                self._commit()
                forced_commit = True
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
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_env.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: 커밋**

```bash
git add env.py tests/test_env.py
git commit -m "feat: gymnasium dispatch env with action masking"
```

---

## Task 7: 학습 — 행동복제(BC) + MaskablePPO

**Files:**
- Create: `train.py`
- Test: `tests/test_train_smoke.py`

- [ ] **Step 1: 실패하는 학습 스모크 테스트 작성**

Create `tests/test_train_smoke.py`:
```python
from pathlib import Path
from simulator import load_problem
from config import BENCHMARKS_DIR
import train


def test_collect_teacher_dataset_nonempty():
    p = load_problem(BENCHMARKS_DIR / "benchmark_02.json")
    obs, acts, masks = train.collect_teacher_dataset([p])
    assert len(obs) == len(acts) == len(masks)
    assert len(obs) > 0


def test_train_smoke_runs_and_saves(tmp_path):
    p = load_problem(BENCHMARKS_DIR / "benchmark_01.json")
    out = tmp_path / "m.zip"
    model = train.train_model([p], ppo_steps=200, bc_epochs=5, save_path=out)
    assert out.exists()
```

- [ ] **Step 2: 테스트 실행해 실패 확인**

Run: `python -m pytest tests/test_train_smoke.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'train'`.

- [ ] **Step 3: `train.py` 구현**

Create `train.py`:
```python
"""모방학습(BC) → MaskablePPO 학습.

teacher(휴리스틱) 궤적을 환경 위에서 재현하며 (obs, action, mask)를 모아
정책망을 교차엔트로피로 사전학습한 뒤 PPO로 강화한다.
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
import torch

from sb3_contrib import MaskablePPO
from sb3_contrib.common.wrappers import ActionMasker
from sb3_contrib.common.maskable.utils import get_action_masks

from simulator import ProblemInstance, Simulator, heuristic_actions
from env import DispatchEnv
import config


def _mask_fn(env: DispatchEnv) -> np.ndarray:
    return env.action_masks()


def make_env(problem: ProblemInstance) -> ActionMasker:
    return ActionMasker(DispatchEnv(problem), _mask_fn)


def collect_teacher_dataset(problems: list[ProblemInstance]):
    """teacher가 두는 액션 시퀀스를 env 인덱스로 변환해 (obs, action, mask) 수집."""
    obs_buf, act_buf, mask_buf = [], [], []
    for p in problems:
        env = DispatchEnv(p)
        sim = Simulator(p)
        obs, _ = env.reset()
        done = False
        steps = 0
        while not done and steps < p.horizon_hours * (sum(p.eqp_qty.values()) + 2):
            # teacher가 이번 시간에 둘 이동들을 계산(상태를 복제해 비파괴적으로)
            planned = heuristic_actions(sim, _clone_state(env))
            # planned를 env 액션으로 하나씩 적용, 끝나면 commit
            move_to_idx = {mv: i + 1 for i, mv in enumerate(env.move_list)}
            action_seq = [move_to_idx[m] for m in planned if m in move_to_idx] + [0]
            for a in action_seq:
                mask = env.action_masks()
                if not mask[a]:
                    a = 0  # 유효하지 않으면 commit으로 대체
                obs_buf.append(obs.copy())
                act_buf.append(a)
                mask_buf.append(mask.copy())
                obs, r, term, trunc, info = env.step(a)
                steps += 1
                if term or trunc:
                    done = True
                    break
    return np.array(obs_buf, dtype=np.float32), np.array(act_buf), np.array(mask_buf)


def _clone_state(env: DispatchEnv):
    """env 내부 simulator 상태를 teacher 계산용으로 그대로 사용.

    heuristic_actions는 전달된 state를 변형하므로, env와 분리된 사본이 필요하다.
    여기서는 동일 problem의 새 Simulator+동일 누적상태를 복제한다.
    """
    import copy
    return copy.deepcopy(env._state)


def behavior_clone(model: MaskablePPO, obs, acts, masks, epochs: int, lr: float):
    """정책망을 teacher 액션에 대해 마스킹된 교차엔트로피로 사전학습."""
    if len(obs) == 0:
        return
    policy = model.policy
    policy.set_training_mode(True)
    opt = torch.optim.Adam(policy.parameters(), lr=lr)
    obs_t = torch.as_tensor(obs)
    act_t = torch.as_tensor(acts, dtype=torch.long)
    mask_t = torch.as_tensor(masks, dtype=torch.bool)
    for _ in range(epochs):
        opt.zero_grad()
        dist = policy.get_distribution(obs_t)
        logits = dist.distribution.logits.clone()
        logits[~mask_t] = -1e8                      # 마스킹
        loss = torch.nn.functional.cross_entropy(logits, act_t)
        loss.backward()
        opt.step()
    policy.set_training_mode(False)


def train_model(problems: list[ProblemInstance], ppo_steps: int = config.DEFAULT_PPO_STEPS,
                bc_epochs: int = config.BC_EPOCHS, lr: float = config.BC_LR,
                save_path: Path | None = None) -> MaskablePPO:
    save_path = Path(save_path) if save_path else config.MODEL_PATH
    save_path.parent.mkdir(parents=True, exist_ok=True)
    # 학습 환경: 여러 problem 중 매 에피소드 무작위 선택
    import random
    def env_fn():
        return make_env(random.choice(problems))
    model = MaskablePPO("MlpPolicy", env_fn(), verbose=0, n_steps=256, batch_size=64)
    # 1) 행동복제
    obs, acts, masks = collect_teacher_dataset(problems)
    behavior_clone(model, obs, acts, masks, bc_epochs, lr)
    # 2) PPO 강화
    model.set_env(env_fn())
    model.learn(total_timesteps=ppo_steps, progress_bar=False)
    model.save(save_path)
    return model


def load_problems_from_dir(directory: Path) -> list[ProblemInstance]:
    from simulator import load_problem
    return [load_problem(p) for p in sorted(Path(directory).glob("benchmark_*.json"))]
```

> 구현 메모: `collect_teacher_dataset`에서 teacher와 env가 같은 진행 상태를 봐야 한다. `heuristic_actions`는 전달된 state를 **변형**하므로, `_clone_state`로 깊은 복제본을 만들어 거기에 적용해 "이번 시간의 이동 목록"만 얻고, 실제 적용은 env.step으로 한다. 단 teacher의 substep 가정(한 시간에 여러 이동)과 env의 substep이 일치하도록, planned 목록을 순서대로 적용 후 commit(0)으로 마무리한다.

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_train_smoke.py -v`
Expected: PASS (2 passed). torch CPU 학습이라 수 초 소요. `get_action_masks` import가 미사용이면 제거.

- [ ] **Step 5: 커밋**

```bash
git add train.py tests/test_train_smoke.py
git commit -m "feat: behavior cloning + MaskablePPO training"
```

---

## Task 8: 평가/리포트 (test.py) + 간트

**Files:**
- Create: `test.py`
- Test: `tests/test_report.py`

- [ ] **Step 1: 실패하는 리포트 테스트 작성**

Create `tests/test_report.py`:
```python
from simulator import load_problem
from config import BENCHMARKS_DIR
import test as report


def test_evaluate_benchmark_with_policy_returns_rates():
    p = load_problem(BENCHMARKS_DIR / "benchmark_01.json")
    # 정책 없이(휴리스틱만) 평가 — RL 없어도 동작
    res = report.evaluate_benchmark(p, model=None)
    assert "heuristic" in res and "optimal" in res
    assert 0.0 <= res["heuristic"] <= 1.0


def test_render_markdown_contains_average_and_gantt(tmp_path):
    p = load_problem(BENCHMARKS_DIR / "benchmark_02.json")
    res = report.evaluate_benchmark(p, model=None)
    md = report.render_markdown({"benchmark_02": (p, res)})
    assert "평균 계획달성률" in md
    assert "간트" in md or "Gantt" in md
```

- [ ] **Step 2: 테스트 실행해 실패 확인**

Run: `python -m pytest tests/test_report.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'test'` 또는 함수 부재.

- [ ] **Step 3: `test.py` 구현**

Create `test.py`:
```python
"""학습된 정책 평가 + RL/휴리스틱/최적 비교 리포트(md) 생성."""
from __future__ import annotations
from pathlib import Path
import numpy as np

from simulator import ProblemInstance, Simulator, heuristic_actions, run_policy, Move
import config


def _rl_policy_factory(model, problem: ProblemInstance):
    """model을 사용해 매 시간 이동 목록을 반환하는 policy_fn."""
    from env import DispatchEnv
    env = DispatchEnv(problem)

    def policy_fn(sim: Simulator, s):
        # env 상태를 sim 상태와 동기화
        env._state = s
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
            if mv in set(sim.valid_moves(s)):
                sim.apply_move(s, mv)
                moves.append(mv)
            else:
                break
        return moves
    return policy_fn


def evaluate_benchmark(problem: ProblemInstance, model=None) -> dict:
    sim = Simulator(problem)
    h_final, h_trace = run_policy(sim, heuristic_actions)
    h_metrics = sim.metrics(h_final)
    out = {
        "heuristic": h_metrics["plan_achievement"],
        "optimal": problem.ground_truth.get("plan_achievement"),
        "heuristic_per_task": h_metrics["per_task"],
        "trace": h_trace,
    }
    if model is not None:
        sim2 = Simulator(problem)
        rl_final, rl_trace = run_policy(sim2, _rl_policy_factory(model, problem))
        rl_metrics = sim2.metrics(rl_final)
        out["rl"] = rl_metrics["plan_achievement"]
        out["rl_per_task"] = rl_metrics["per_task"]
        out["rl_trace"] = rl_trace
    return out


def _gantt(problem: ProblemInstance, trace) -> str:
    """장비(model)별 시간대 배치를 텍스트 간트로."""
    lines = ["```", "간트 (model x hour → task)"]
    n_tasks = len(problem.tasks)
    task_label = {i: f"{t.plan_prod_key}/{t.oper_id}" for i, t in enumerate(problem.tasks)}
    for model in problem.models():
        row = [f"{model:>8}"]
        for hour, applied, snapshot in trace:
            here = [task_label[ti] for (m, ti), c in snapshot.items() if m == model and c > 0]
            row.append((here[0] if here else "-").split("/")[0][:6].ljust(6))
        lines.append(" | ".join(row))
    lines.append("```")
    return "\n".join(lines)


def render_markdown(results: dict[str, tuple[ProblemInstance, dict]]) -> str:
    rows = []
    h_avg = np.mean([r["heuristic"] for _, r in results.values()])
    opt_avg = np.mean([r["optimal"] for _, r in results.values() if r["optimal"] is not None])
    has_rl = any("rl" in r for _, r in results.values())
    lines = ["# 모델 평가 리포트 (기록용)", ""]
    lines.append(f"- 평균 계획달성률 — 최적: {opt_avg:.3f} / 휴리스틱: {h_avg:.3f}"
                 + (f" / RL: {np.mean([r.get('rl', 0) for _, r in results.values()]):.3f}" if has_rl else ""))
    lines.append("")
    lines.append("| 벤치마크 | 최적 | 휴리스틱 | " + ("RL |" if has_rl else ""))
    lines.append("|---|---|---|" + ("---|" if has_rl else ""))
    for name, (p, r) in results.items():
        opt = r["optimal"]
        line = f"| {name} | {opt:.3f} | {r['heuristic']:.3f} | "
        if has_rl:
            line += f"{r.get('rl', 0):.3f} |"
        lines.append(line)
    lines.append("")
    for name, (p, r) in results.items():
        lines.append(f"## {name}")
        lines.append(f"- 비고: {p.ground_truth.get('note', '')}")
        lines.append(_gantt(p, r.get("rl_trace", r["trace"])))
        lines.append("")
    return "\n".join(lines)


def run_eval(benchmarks_dir: Path = config.BENCHMARKS_DIR, model=None,
             report_path: Path = config.REPORT_PATH) -> str:
    from simulator import load_problem
    results = {}
    for path in sorted(Path(benchmarks_dir).glob("benchmark_*.json")):
        p = load_problem(path)
        results[path.stem] = (p, evaluate_benchmark(p, model))
    md = render_markdown(results)
    Path(report_path).write_text(md, encoding="utf-8")
    return md
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_report.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: 커밋**

```bash
git add test.py tests/test_report.py
git commit -m "feat: evaluation report with gantt and ground-truth comparison"
```

---

## Task 9: DB 어댑터 (얇은 Oracle 레이어)

**Files:**
- Create: `db.py`
- Test: `tests/test_db_pivot.py`

- [ ] **Step 1: 실패하는 피벗 테스트 작성 (DB 없이 순수 변환만)**

Create `tests/test_db_pivot.py`:
```python
from db import rows_to_problem


def test_rows_to_problem_pivots_gbn_cd():
    # RTS_LINEDSDB_INF 한 줄 = (rule_timekey, fac_id, batch_id, ppk, oper_id, oper_seq, eqp_model, gbn_cd, attr_val)
    rows = [
        ("20260529", "ICPRB", "B1", "P1", "OP10", 1, "M1", "UPH", "100"),
        ("20260529", "ICPRB", "B1", "P1", "OP10", 1, "M1", "ASSIGN_EQUIP_CNT", "1"),
        ("20260529", "ICPRB", "B1", "P1", "OP10", 1, "M1", "D0_TARGET_QTY", "300"),
        ("20260529", "ICPRB", "B1", "P1", "OP10", 1, "M1", "WIP_QTY", "1000"),
        ("20260529", "ICPRB", "B1", "P1", "OP10", 1, "M1", "TOOL_QTY", "1"),
    ]
    p = rows_to_problem(rows, horizon_hours=3, conv_groups={"G1": ["B1"]})
    assert len(p.tasks) == 1
    assert p.tasks[0].plan_qty == 300
    assert p.uph_of("M1", 0) == 100.0
    assert p.init_assign[("M1", 0)] == 1
    assert p.tool_qty[("B1", "M1")] == 1
```

- [ ] **Step 2: 테스트 실행해 실패 확인**

Run: `python -m pytest tests/test_db_pivot.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'db'`.

- [ ] **Step 3: `db.py` 구현**

Create `db.py`:
```python
"""Oracle 어댑터 (oracledb 선택적). RTS_LINEDSDB_INF → ProblemInstance, 결과 테이블 기록.

oracledb 미설치/미접속이어도 rows_to_problem(순수 변환)은 동작한다.
"""
from __future__ import annotations
from collections import defaultdict
import config
from simulator import Task, ProblemInstance


def rows_to_problem(rows, horizon_hours: int, conv_groups: dict[str, list[str]],
                    switch_time_hours: int = config.DEFAULT_SWITCH_TIME_HOURS,
                    rule_timekey: str | None = None) -> ProblemInstance:
    """GBN_CD가 long-format인 행들을 ProblemInstance로 피벗.

    row = (rule_timekey, fac_id, batch_id, plan_prod_key, oper_id, oper_seq, eqp_model, gbn_cd, attr_val)
    """
    # task 식별: (ppk, oper_id) — batch_id/oper_seq는 첫 등장값 사용
    task_meta: dict[tuple[str, str], dict] = {}
    uph_raw: dict[tuple[str, str, str], float] = {}
    assign_raw: dict[tuple[str, str, str], int] = {}
    tool_raw: dict[tuple[str, str], int] = {}
    target_raw: dict[tuple[str, str], int] = {}
    wip_raw: dict[tuple[str, str], int] = {}
    eqp_models: set[str] = set()
    rk = rule_timekey

    for r in rows:
        rk = rk or r[0]
        _, _fac, batch_id, ppk, oper_id, oper_seq, eqp_model, gbn, val = r
        key = (ppk, oper_id)
        task_meta.setdefault(key, {"batch_id": batch_id, "oper_seq": int(oper_seq)})
        if eqp_model:
            eqp_models.add(eqp_model)
        if gbn == "UPH" and float(val) > 0:
            uph_raw[(ppk, oper_id, eqp_model)] = float(val)
        elif gbn == "ASSIGN_EQUIP_CNT":
            assign_raw[(ppk, oper_id, eqp_model)] = int(float(val))
        elif gbn == "TOOL_QTY":
            tool_raw[(batch_id, eqp_model)] = int(float(val))
        elif gbn == "D0_TARGET_QTY":
            target_raw[key] = int(float(val))
        elif gbn == "WIP_QTY":
            wip_raw[key] = int(float(val))

    keys = list(task_meta)
    index = {k: i for i, k in enumerate(keys)}
    tasks = [
        Task(ppk, oper, task_meta[(ppk, oper)]["oper_seq"], task_meta[(ppk, oper)]["batch_id"],
             target_raw.get((ppk, oper), 0), wip_raw.get((ppk, oper), 0))
        for (ppk, oper) in keys
    ]
    uph = {(m, index[(ppk, o)]): v for (ppk, o, m), v in uph_raw.items()}
    init_assign = {(m, index[(ppk, o)]): c for (ppk, o, m), c in assign_raw.items() if c > 0}
    eqp_qty: dict[str, int] = defaultdict(int)
    for (m, _ti), c in init_assign.items():
        eqp_qty[m] += c
    for m in eqp_models:
        eqp_qty.setdefault(m, 0)
    return ProblemInstance(
        rule_timekey=rk, horizon_hours=horizon_hours, switch_time_hours=switch_time_hours,
        tasks=tasks, _uph=uph, eqp_qty=dict(eqp_qty), init_assign=init_assign,
        tool_qty=tool_raw, conv_groups=conv_groups, ground_truth={},
    )


# --- 아래는 실제 Oracle 접속이 있을 때만 사용 (oracledb 필요) ---

def _connect():
    import oracledb  # 지연 import
    cfg = config.load_config()
    return oracledb.connect(user=cfg["user"], password=cfg["password"], dsn=cfg["dsn"])


def fetch_problem(rule_timekey: str | None = None, horizon_hours: int = 12,
                  conv_groups: dict | None = None) -> ProblemInstance:
    """RTS_LINEDSDB_INF에서 스냅샷을 읽어 ProblemInstance로 변환."""
    conn = _connect()
    try:
        cur = conn.cursor()
        if rule_timekey is None:
            cur.execute("SELECT MAX(RULE_TIMEKEY) FROM RTS_LINEDSDB_INF")
            rule_timekey = cur.fetchone()[0]
        cur.execute(
            "SELECT RULE_TIMEKEY, FAC_ID, BATCH_ID, PLAN_PROD_KEY, OPER_ID, OPER_SEQ, "
            "EQP_MODEL_CD, GBN_CD, ATTR_VAL FROM RTS_LINEDSDB_INF WHERE RULE_TIMEKEY = :rk",
            rk=rule_timekey)
        rows = cur.fetchall()
        return rows_to_problem(rows, horizon_hours, conv_groups or {}, rule_timekey=rule_timekey)
    finally:
        conn.close()


def write_results(rule_timekey: str, allocation_rows: list[dict]) -> None:
    """RTS_RSLT_MAS/HIS 삭제 후 insert. allocation_rows는 출력 스키마 dict 목록."""
    conn = _connect()
    try:
        cur = conn.cursor()
        for table in (config.RESULT_TABLE, config.RESULT_HIS_TABLE):
            cur.execute(f"DELETE FROM {table} WHERE RULE_TIMEKEY = :rk", rk=rule_timekey)
            cur.executemany(
                f"INSERT INTO {table} (RULE_TIMEKEY, EQP_ID, EQP_MODEL_CD, SEQ_NO, "
                f"START_TIME, END_TIME, PLAN_PROD_KEY, PRODUCE_QTY, CRT_TM, CRT_USER_ID) "
                f"VALUES (:RULE_TIMEKEY, :EQP_ID, :EQP_MODEL_CD, :SEQ_NO, :START_TIME, "
                f":END_TIME, :PLAN_PROD_KEY, :PRODUCE_QTY, SYSTIMESTAMP, :CRT_USER_ID)",
                allocation_rows)
        conn.commit()
    finally:
        conn.close()
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_db_pivot.py -v`
Expected: PASS (1 passed).

- [ ] **Step 5: 커밋**

```bash
git add db.py tests/test_db_pivot.py
git commit -m "feat: thin Oracle adapter with GBN_CD pivot (DB-optional)"
```

---

## Task 10: CLI (run.py) + 전체 회귀

**Files:**
- Create: `run.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: 실패하는 CLI 테스트 작성**

Create `tests/test_cli.py`:
```python
import subprocess, sys
from config import ROOT


def test_cli_eval_runs_and_writes_report(tmp_path):
    out = tmp_path / "report.md"
    r = subprocess.run(
        [sys.executable, "run.py", "eval", "--report", str(out)],
        cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert out.exists()
    assert "평균 계획달성률" in out.read_text(encoding="utf-8")


def test_cli_help():
    r = subprocess.run([sys.executable, "run.py", "--help"],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0
    assert "train" in r.stdout and "infer" in r.stdout and "eval" in r.stdout
```

- [ ] **Step 2: 테스트 실행해 실패 확인**

Run: `python -m pytest tests/test_cli.py -v`
Expected: FAIL — `run.py` 없음 → returncode != 0.

- [ ] **Step 3: `run.py` 구현**

Create `run.py`:
```python
"""CLI 디스패처: train / infer / eval.

벤치마크 우선. --timekey 지정 시 DB(db.fetch_problem) 경로 사용.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import config


def _load_problems(args):
    from simulator import load_problem
    if args.benchmark_dataset:
        return [load_problem(Path(args.benchmark_dataset).with_suffix(".json"))]
    if getattr(args, "timekey", None):
        import db
        return [db.fetch_problem(rule_timekey=args.timekey)]
    return [load_problem(p) for p in sorted(config.BENCHMARKS_DIR.glob("benchmark_*.json"))]


def cmd_train(args):
    import train
    problems = _load_problems(args)
    train.train_model(problems, ppo_steps=args.steps)
    print(f"학습 완료 → {config.MODEL_PATH}")
    # 학습 후 전체 벤치마크 평가/기록
    import test as report
    from sb3_contrib import MaskablePPO
    model = MaskablePPO.load(config.MODEL_PATH)
    report.run_eval(model=model)
    print(f"평가 리포트 → {config.REPORT_PATH}")


def cmd_eval(args):
    import test as report
    model = None
    if Path(config.MODEL_PATH).exists() and not args.no_model:
        from sb3_contrib import MaskablePPO
        model = MaskablePPO.load(config.MODEL_PATH)
    report_path = Path(args.report) if args.report else config.REPORT_PATH
    report.run_eval(model=model, report_path=report_path)
    print(f"평가 리포트 → {report_path}")


def cmd_infer(args):
    import test as report
    problems = _load_problems(args)
    model = None
    if Path(config.MODEL_PATH).exists():
        from sb3_contrib import MaskablePPO
        model = MaskablePPO.load(config.MODEL_PATH)
    for p in problems:
        res = report.evaluate_benchmark(p, model)
        rate = res.get("rl", res["heuristic"])
        print(f"{p.rule_timekey}: 평균 계획달성률 {rate:.3f}")


def build_parser():
    parser = argparse.ArgumentParser(description="장비 전환 스케줄링 RL — train/infer/eval")
    sub = parser.add_subparsers(dest="cmd", required=True)

    pt = sub.add_parser("train", help="모방학습+PPO 학습 후 벤치마크 평가")
    pt.add_argument("--benchmark-dataset", dest="benchmark_dataset")
    pt.add_argument("--timekey")
    pt.add_argument("--steps", type=int, default=config.DEFAULT_PPO_STEPS)
    pt.set_defaults(func=cmd_train)

    pi = sub.add_parser("infer", help="추론(달성률 출력)")
    pi.add_argument("--benchmark-dataset", dest="benchmark_dataset")
    pi.add_argument("--timekey")
    pi.set_defaults(func=cmd_infer)

    pe = sub.add_parser("eval", help="전체 벤치마크 평가 + md 리포트")
    pe.add_argument("--report")
    pe.add_argument("--no-model", action="store_true", help="휴리스틱만 평가")
    pe.set_defaults(func=cmd_eval)
    return parser


def main():
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_cli.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: 전체 테스트 회귀**

Run: `python -m pytest -v`
Expected: 모든 테스트 PASS.

- [ ] **Step 6: 엔드투엔드 수동 확인**

Run:
```bash
python run.py eval --no-model
python run.py train --benchmark-dataset benchmarks/benchmark_02 --steps 2000
python run.py infer --benchmark-dataset benchmarks/benchmark_02
```
Expected: eval은 `MODEL_REPORT.md` 생성(휴리스틱 vs 최적). train은 학습 후 리포트 갱신. infer는 달성률 출력.

- [ ] **Step 7: 커밋**

```bash
git add run.py tests/test_cli.py
git commit -m "feat: run.py CLI (train/infer/eval) and end-to-end wiring"
```

---

## Task 11: README 사용법 정합 + 최종 정리

**Files:**
- Modify: `README.md` (하단에 실제 사용법 추가)

- [ ] **Step 1: README에 실제 동작 사용법 섹션 추가**

Append to `README.md`:
```markdown

## 실제 구현 사용법 (이번 슬라이스)

DB 없이 벤치마크로 전 파이프라인이 동작한다.

```bash
pip install -e .[rl]                 # gymnasium, stable-baselines3, sb3-contrib, torch
python run.py eval --no-model        # 휴리스틱 vs 최적 비교 → MODEL_REPORT.md
python run.py train --benchmark-dataset benchmarks/benchmark_03 --steps 50000
python run.py eval                   # 학습된 RL 포함 평가
python run.py infer --benchmark-dataset benchmarks/benchmark_03
```

DB(Oracle) 사용 시 `.env` 설정 후:
```bash
pip install -e .[rl,oracle]
python run.py infer --timekey 20260529225000   # RTS_LINEDSDB_INF 조회
python run.py infer                              # 미지정 시 MAX(RULE_TIMEKEY)
```
```

- [ ] **Step 2: 전체 테스트 최종 확인**

Run: `python -m pytest -v`
Expected: 모든 테스트 PASS.

- [ ] **Step 3: 커밋**

```bash
git add README.md
git commit -m "docs: add actual usage for implemented slice"
```

---

## Self-Review 메모 (작성자 점검 결과)

- **스펙 커버리지:** 동적 1시간 step·WIP 흐름(Task 2), batch 전환 Idle+tool 풀(Task 3), conversion 그룹 제약(Task 3), model-count substep 액션+마스킹(Task 6), 모방학습+PPO(Task 7), 최적 비교 리포트+간트(Task 8), 7 벤치마크(Task 1·5), DB 얇은 어댑터(Task 9), CLI(Task 10) — 스펙 각 절에 대응 태스크 존재.
- **타입 일관성:** `Move(model, from_index, to_index)`, `ProblemInstance.uph_of/batch_of/next_task_index/can_convert`, `Simulator.reset/valid_moves/apply_move/advance_hour/metrics`, `run_policy→(state, trace)` 시그니처가 전 태스크에서 일관.
- **알려진 구현 리스크:** (1) 휴리스틱이 03/04/07 최적 도달 — Task 5 Step 7에 보정 코드 명시. (2) `collect_teacher_dataset`의 teacher/env 상태 동기화 — `_clone_state` 깊은복제로 비파괴 계산 후 env.step 적용. (3) `class Simulator(Simulator)` 상속 트릭 금지 — 메서드를 본 클래스에 직접 추가(Task 3 메모).
- **비범위 확인:** plan-only/wip-static/dynamic 분리 모드·실DB운영검증은 의도적으로 제외(스펙 §9).
