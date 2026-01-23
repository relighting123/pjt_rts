# DBR 시뮬레이터 상세 동작 가이드 (소스코드 & 샘플 데이터 분석)

본 문서는 `Fast_A` 제품 36개를 22시간 내에 평준화 생산하는 시나리오를 바탕으로, 소스코드가 매 순간 어떻게 의사결정을 내리는지 상세히 설명합니다.

## 1. 분석 대상 데이터 (Sample Data)
- **대상**: Fast_A (Step_10 -> Step_20 -> Step_30)
- **목표량**: 36대
- **마감 기한**: 1320분 (22시간)
- **Takt Time**: 1320 / 36 = **36.6분/대**

---

## 2. 주요 소스코드 동작 단계별 분석

### 단계 1: 시뮬레이터 초기화 (`simulator.py`)
시뮬레이션 시작 시 `init_state()`는 `plan_wip.json`을 읽어 초기 상태를 설정합니다.

```python
# simulator.py:110-116
for p in self.production_data:
    key = (p['product'], p['process'])
    self.wip[key] = p['wip']  # (Fast_A, Step_10) = 36 설정
    self.plan[key] = p['plan']
    self.achieved[key] = 0
    self.oper_seq[key] = p['oper_seq']
```
- **결과**: `T=0` 시점에 Step_10 버퍼에는 데이터 파일에 정의된 대로 36개의 자재가 채워집니다.

---

### 단계 2: 스케줄러의 의사결정 프로세스 (`scheduler.py`)
매 분마다 시뮬레이터는 IDLE 장비를 모아 `select_tasks`를 호출합니다.

#### ① 현재 시작 허용 대수 계산 (Pacing Gate)
가장 중요한 "심장박동(Pulse)" 제어 로직입니다.

```python
# scheduler.py:114
if under_way[task] < plan[task]:
    # Rope logic (Takt Gate 대신 직관적인 WIP 제어로 동작 중)
    if oper_seq[task] < oper_seq[self.drum_process]:
        if local_wip[self.drum_process] >= self.buffer_size: continue
```
- **데이터 분석**: 
  - 현재 시너지 스케줄러는 `under_way`(이미 시작했거나 끝난 대수)가 계획량보다 적을 때만 작업을 고려합니다.
  - 여기에 Takt 로직을 적용하면, 특정 시간대에만 `under_way` 한도를 열어주는 방식으로 확장이 가능합니다.

#### ② 점수 계산 및 최적 할당 (Scoring Mechanism)
여러 공정 중 어떤 장비가 어디로 갈지 점수를 매깁니다. (`scheduler.py:90-111`)

```python
# scheduler.py:91-100
# 1. Flow Score: 당장 처리할 WIP가 있으면 높은 점수
if imm_wip > 0:
    flow_score = 1000 + (imm_wip * 10)
# 2. Resident Priority: 현재 위치에 작업이 있거나 올 가능성(potential)이 있으면 잔류
elif is_resident and potential[task] > 0:
    flow_score = 800 + (potential[task] * 5)
```
- **데이터 분석**: 
  - 특정 장비가 `Step_10`에 이미 있고(`is_resident`), 후속 공정으로 넘어갈 자재가 있다면(`potential`) 이동하지 않고 대기하거나 즉시 작업을 시작합니다.
  - **Resident Bonus (+200)**: 설비가 잦은 이동으로 인한 60분 패널티를 받지 않도록 보호합니다.

#### ③ 설비 배치 밸런싱 (Balancing)
장비들이 한 공정에 몰리는 것을 방지합니다.

```python
# scheduler.py:108-109
assigned_at_task = current_assignments.get(task, 0)
balance_penalty = assigned_at_task * 500
```
- **데이터 분석**: 
  - 이미 해당 공정에 장비가 1대 배치되어 있다면 500점의 패널티를 부여합니다.
  - 이는 장비가 다른 공정(`Step_20`)으로 이동하여 라인 밸런스를 맞추도록 유도합니다.

---

## 3. [상세 트레이스] T=0 시점의 의사결정 시뮬레이션

가장 첫 번째 장비(Basic_1)가 어떤 과정을 거쳐 `Step_10` 작업을 선택하는지 소스코드 흐름에 따라 추적합니다.

### 시나리오 데이터:
- **현재 시간(T)**: 0분
- **IDLE 장비**: Basic_1 (현재 제품/공정 없음)
- **Step_10 WIP**: 36개
- **Step_20 WIP**: 0개

### 소스코드 실행 추적:

1.  **[scheduler.py:63]** `for task in tasks:` 루프 시작
    - 첫 번째 후보: `task = (Fast_A, Step_10)`
2.  **[scheduler.py:74]** `potential[Step_10]` 계산
    - `imm(36) + running(0) + upstream_wip(0) = 36`
3.  **[scheduler.py:91]** `if imm_wip > 0:` 판단
    - 36 > 0 이므로 **True** 진입
    - `flow_score = 1000 + (36 * 10) = 1360`
4.  **[scheduler.py:100]** `resident_bonus` 계산
    - 초기 상태이므로 `is_resident` = False -> **0점**
5.  **[scheduler.py:104]** `move_penalty` 계산
    - 장비에 등록된 현재 공정이 없으므로 `co_time` = 0 -> **0점**
6.  **[scheduler.py:109]** `balance_penalty` 계산
    - 아직 할당된 장비가 없으므로 `assigned_at_task(0) * 500` -> **0점**
7.  **[scheduler.py:111]** 최종 점수 합산
    - `1360 + 0 - 0 - 0 = 1360점`
8.  **[scheduler.py:114]** `if under_way[task] < plan[task]:` 게이트 통과
    - `0 < 36` 이므로 **True** 진입
9.  **[scheduler.py:121]** `best_task = (Fast_A, Step_10)` 저장

**최종 결과**: `Basic_1` 장비는 1360점이라는 압도적인 점수로 `Step_10`에 할당됩니다.

---

## 4. 타임라인에 따른 동작 요약 (Snapshot)

| 시간(T) | 주요 의사결정 (Logic Path) | 결과 |
| :--- | :--- | :--- |
| **0분** | `local_wip[Step_10] = 36` 이므로 장비 1이 점수 가중치를 받아 작업 시작 | Step_10 가동 (남은 WIP 35) |
| **10분** | Step_10 첫 제품 완성 -> `wip[Step_20]`이 1 증가함 | Step_20 대기 중인 장비가 작업 시작 |
| **20분** | 장비들이 각각 Step_10, Step_20, Step_30에 1대씩 배치되려고 함 | 밸런스 패널티(-500)에 의해 최적 배치 유지 |

---

## 4. 요약: 왜 이 로직이 효율적인가?
- **WIP 가시성**: `potential` 계산을 통해 단순히 눈앞의 재고뿐만 아니라 상류에서 올 자재까지 고려하여 설비를 미리 대기시킵니다.
- **불필요한 이동 억제**: 설비 교체 시간(60분)이 매우 크기 때문에, `move_penalty`와 `resident_bonus`가 조화를 이루어 꼭 필요한 경우에만 이동을 단행합니다.
- **역할 분담**: `balance_penalty` 덕분에 장비들이 뭉치지 않고 Step 10, 20, 30에 골고루 퍼져 일정한 생산 속도(Takt)를 유지하게 됩니다.
