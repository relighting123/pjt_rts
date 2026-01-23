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
# simulator.py:108-112
for p in self.production_data:
    key = (p['product'], p['process'])
    self.wip[key] = p['wip']  # (Fast_A, Step_10) = 36 설정
    self.plan[key] = p['plan']
```
- **결과**: `T=0` 시점에 Step_10 버퍼에는 36개의 자재가 채워집니다.

---

### 단계 2: 스케줄러의 의사결정 프로세스 (`scheduler.py`)
매 분마다 시뮬레이터는 유급 장비를 모아 `select_tasks`를 호출합니다.

#### ① 현재 시작 허용 대수 계산 (Takt Gate)
가장 중요한 "심장박동(Pulse)" 제어 로직입니다.

```python
# scheduler.py:104-108
takt_time = deadline / target_qty  # 36.6분
allowed_starts = int(context.get('t', 0) / takt_time) + 1
current_started = achieved.get(task, 0) + current_assignments.get(task, 0)

if current_started >= allowed_starts:
    continue  # 리듬보다 빠르면 작업을 시작하지 않고 대기 (Busy Wait 방지)
```
- **데이터 분석**: 
  - `T=0`: `allowed_starts`는 1입니다. 현재 `started`는 0이므로 **1대 생산 시작 가능**.
  - `T=10`: 아직 `T < 36.6`이므로 `allowed_starts`는 여전히 1입니다. 하지만 이미 1대가 투입되었다면 `current_started >= 1`이 되어 다음 Takt까지 **추가 투입을 차단**합니다.

#### ② 다운스트림 잠재량 계산 (Final Target Awareness)
전체 공정이 끝까지 도달했는지를 판단하여 과잉 생산을 막습니다.

```python
# scheduler.py:77-84 (잠재량 계산 루프)
pipeline = 0
for (p_prod, p_proc), p_seq in oper_seq.items():
    if p_prod == prod and p_seq > oper_seq[task]:
        pipeline += wip.get((p_prod, p_proc), 0) # 뒷 공정에 쌓인 재공
        pipeline += current_assignments.get((p_prod, p_proc), 0) # 현재 가동 중인 작업
potential_downstream[task] = finished + pipeline
```
- **판단**: 현재 작업하고 있는 유닛이 최종 공정까지 흘러갔을 때 목표를 달성한다면, 더 이상 상류 공정(`Step_10`)에서 자재를 투입하지 않습니다.

#### ③ 점수 계산 및 최적 할당 (Scoring)
여러 공정 중 어떤 장비가 어디로 갈지 점수를 매깁니다.

```python
# scheduler.py:120-130
# 1. Flow Score: 당장 처리할 WIP가 있으면 높은 점수
if imm_wip > 0: flow_score = 1000 + (imm_wip * 10)
# 2. Resident Bonus: 이동하지 않고 현재 자리에 있으면 보너스
resident_bonus = 200 if is_resident else 0
# 3. Move Penalty: 설비 교체 시간이 길면 감점
move_penalty = (co_time * 15) if not is_resident else 0

score = flow_score + resident_bonus - move_penalty - balance_penalty
```
- **데이터 분석**: 
  - 특정 장비가 `Step_10`에 이미 있고(`is_resident`), 투입 리듬(`Takt`)이 찾아왔다면 높은 점수로 즉시 작업을 시작합니다.
  - 만약 장비가 다른 곳에 있다면 패널티 때문에 신중하게 이동 여부를 결정합니다.

---

## 3. 타임라인에 따른 동작 요약 (Snapshot)

| 시간(T) | 릴리스 허용량 | 주요 의사결정 (Logic Path) | 결과 |
| :--- | :--- | :--- | :--- |
| **0분** | 1대 | `current_started(0) < 1` 이므로 Step_10 투입 승인 | 1번 장비 작업 시작 |
| **10분** | 1대 | `current_started(1) >= 1` 이므로 Step_10 추가 투입 거부 | 추가 장비는 유휴(IDLE) 대기 |
| **20분** | 1대 | Step_10 작업 종료 -> Step_20 버퍼에 1개 쌓임 | 2번 장비가 Step_20 작업 시작 |
| **37분** | 2대 | `allowed_starts`가 2로 증가. Step_10 투입 가능 | 다음 자재 투입 시작 |

---

## 4. 요약: 왜 이 로직이 효율적인가?
- **과잉 생산 억제**: `allowed_starts` 로직이 공장 내 재공(WIP)이 급증하는 것을 원천 차단합니다.
- **병목 동기화**: `potential_downstream` 로직이 최종 목표 달성에 필요한 양만 생산하도록 조절하여, 쓸데없는 가동률 낭비를 막습니다.
- **안정적인 흐름**: 설비 교체 패널티와 거주 보너스가 조화를 이루어 장비가 이리저리 뛰어다니지 않고 자기 자리를 지키며 묵묵히 생산하게 만듭니다.
