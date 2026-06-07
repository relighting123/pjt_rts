# 2-모드 가이드 기반 장비 운영 — 설계 문서

- 작성일: 2026-06-07
- 상태: 초안 (사용자 검토 대기)
- 선행: `2026-06-05-equipment-dispatch-rl-design.md` (기본 RL 시스템), 커밋 #19(계층적 배분 RL 골격)

## 1. 목적

하나의 `rule_timekey`에 대해 **두 가지 산출물**을 항상 순차로 생성한다.

1. **가이드 수량 (Mode 1 · 정적):** 재공을 무한으로 가정하고 계획량·UPH·장비 수·tool
   수·배분 가능여부만으로 **공정별 목표 장비 대수**를 산출한다. "이 계획을 달성하려면
   공정별로 장비를 몇 대씩 둬야 하는가"의 기준선.
2. **동적 운영 (Mode 2):** 가이드 수량을 *가급적* 준수하되, 실제 재공(WIP) 상황에 따라
   장비를 이동하며 시간에 따라 운영한다. 가이드 준수는 **무조건이 아니라 가동률 조건부**다.

두 산출물은 별도 on/off 토글 없이 `train`/`infer`/`eval` 모두에서 rule_timekey마다 함께
나온다.

## 2. 현행 자산 (재사용 — 신규 파일 없음)

이 설계의 대부분은 이미 코드에 골격이 존재한다. 신규 구축이 아니라 **미완성 마무리 +
기본 활성화 + 가이드 준수 로직 개선**이다.

| 요소 | 위치 | 현 상태 |
|---|---|---|
| 가이드 해석식 (계획량/UPH 비례) | `simulator.py` `plan_target_allocation()` | 동작 |
| 가이드 RL 환경 (1-step) | `alloc_env.py` `AllocationEnv` | **학습 진입점 없음 → 완성 필요** |
| 가이드→동적 주입 | `train.py` `_get_target_allocation()` | 배선됨(기본 OFF) |
| 가이드 준수 보상 | `env.py` `_alloc_guide_reward()` | **균일 페널티 → 조건부로 개선 필요** |
| WIP 체류시간 산식 `wip/(min(uph_cur,wip)-min(uph_prev,wip))` | `simulator.py` `wip_dwell_time()` | 동작 |
| 체류시간 보상/관측 | `env.py` `_dwell_shaping_reward()`, `dwell_obs` | 동작(기본 OFF) |
| 가동률 | `simulator.py` `_active_eqp_count`/`util_rate` | 동작 |

### 정리(삭제) 대상
- README의 `--mode plan-only/wip-static/dynamic` 설명: `run.py`에 존재하지 않는 가짜 모드.
  → 본 설계의 실제 동작(가이드+동적 2산출)으로 문서 교체.

## 3. 아키텍처

```
rule_timekey 입력 (벤치마크 JSON 또는 DB 조회)
        │
        ├─► [Mode 1] AllocationEnv (1-step PPO)        ← 학습 완성
        │      입력: 계획량·UPH·eqp수·tool수 (WIP 무시)
        │      출력: 공정별 목표 장비 대수 = 가이드 수량
        │      teacher(BC): plan_target_allocation() 해석식
        │      저장: saved_models/ppo_alloc.zip
        │
        └─► [Mode 2] DispatchEnv (시간 step MaskablePPO)
               target_allocation = Mode 1 가이드 주입
               보상 = 생산기여(dense) + 가이드준수(조건부) + WIP체류(dwell) + 종료달성률
               출력: 시간대별 장비 배치·생산 = 동적 운영 결과
```

학습 오케스트레이션(`train.py`): **① AllocationEnv 학습 → ppo_alloc.zip → ② 그 가이드로
DispatchEnv 학습**.

## 4. Mode 1 — AllocationEnv 학습 완성

신규 함수 `train_alloc_model(problems, ...)`을 `train.py`에 추가한다.

- **BC(모방학습):** 각 문제의 `plan_target_allocation()` 해석식 배분을 정답 logit으로
  변환해 AllocationEnv 정책을 사전학습. (해석식이 곧 teacher.)
- **PPO 강화:** AllocationEnv의 기존 보상(이론적 계획달성률 − 전환비용 보정)으로 미세조정.
- **저장:** `config.SAVED_MODELS_DIR / "ppo_alloc.zip"`.
- **shape 처리:** DispatchEnv와 동일하게 `MAX_TASKS/MAX_MODELS`로 차원 고정, 동일 shape
  문제만 묶어 학습.
- `train_model()`은 dispatch 학습 전에 `train_alloc_model()`을 호출한다.

`USE_ALLOC_MODEL=true`(기본)이면 `_get_target_allocation()`이 `ppo_alloc.zip`을 로드해
가이드를 산출하고, 없으면 해석식으로 폴백(안전망 유지).

## 5. Mode 2 — 조건부 가이드 준수 로직

현행 `_alloc_guide_reward()`는 모든 편차를 균일 페널티하여 재공 적응과 충돌한다.
이를 **가동률 조건부 + 밴드(±%)** 로 교체한다.

### 규칙
설정값:
- `GUIDE_UTIL_THRESHOLD` (기본 0.70) — 전체 가동률이 이 값 미만이면 가이드 준수 페널티
  **미적용**(재공이 부족해 장비가 노는 상황에선 가이드 배치가 무의미).
- `GUIDE_BAND_PCT` (기본 0.20) — 가이드 대비 허용 상·하단 비율. 가이드 `tgt`에 대해
  `[tgt·(1−band), tgt·(1+band)]` 안이면 페널티 0, 벗어난 만큼만 페널티.

판정(매 commit 시점):
1. 전체 가동률 `util < GUIDE_UTIL_THRESHOLD` → 가이드 항 = 0 (적용 안 함).
2. 그 외, 각 (model, task)에 대해:
   - 해당 task의 WIP == 0 → 그 task의 가이드 페널티 제외(가이드 무의미).
   - 실제 배치가 밴드 `[tgt·(1−band), tgt·(1+band)]` 안 → 페널티 0.
   - 밴드 밖 → 초과분을 `eqp_qty`로 정규화해 페널티 누적.
3. 보상 = `ALLOC_LAMBDA · (1 − 평균 밴드초과 페널티)`.

효과: 가동률이 높아 "장비가 충분히 일하는" 국면에선 가이드 ±밴드 안에서만 움직여
thrashing을 막고, 재공이 비어 가이드가 무의미한 국면에선 자유롭게 재공을 따라간다.
이로써 "가급적 준수하되 재공 상황에 따라 적절히 운영"을 구현한다.

WIP 체류시간 보상(`_dwell_shaping_reward`, `dwell_obs`)은 그대로 사용해 "앞단에만 재공이
있으면 그 재공을 진행하고, 유입·소진이 균형이면 유지"하는 행동을 유도한다.

## 6. 산출/실행 — 2-산출 순차

별도 모드 플래그 없음. `infer`/`eval`/`train` 후 평가에서 rule_timekey마다 둘 다 산출한다.

- **가이드 수량(정적):** AllocationEnv(또는 해석식) 결과를 공정별 목표 대수 표로.
- **동적 운영:** DispatchEnv 정책으로 horizon 시뮬레이션한 시간대별 배치·생산·가동률.

리포트(`test.py`/`report_output.py`)는 기존 RL/휴리스틱/최적 비교에 더해, 각 벤치마크
섹션에 **가이드 수량 표**와 **동적 결과 대비 가이드 편차**(밴드 내/외 표시)를 추가한다.
기존 가동률 컬럼은 유지.

DB 기록은 동적 운영 결과를 운영 스케줄(RTS_ASSIGN 등)로, 가이드 수량은 참조 산출로
취급한다(기록 경로 자체는 본 슬라이스 비범위 — 현행과 동일).

## 7. 설정 (config.py / .env)

| 키 | 기본값 | 의미 |
|---|---|---|
| `USE_ALLOC_MODEL` | **true** | 가이드를 AllocationEnv RL로 산출(없으면 해석식 폴백) |
| `ALLOC_LAMBDA` | **>0** (예 0.3) | 가이드 준수 보상 계수 |
| `DWELL_LAMBDA` | **>0** (예 0.3) | WIP 체류시간 보상 계수 |
| `DWELL_OBS` | **true** | 관측에 체류시간 추가 |
| `GUIDE_UTIL_THRESHOLD` | 0.70 | 이 가동률 이상에서만 가이드 준수 적용 |
| `GUIDE_BAND_PCT` | 0.20 | 가이드 대비 허용 상·하단 비율 |

> **비호환 주의:** `DWELL_OBS=true`는 관측 차원을 바꾼다. 기존 `ppo_dispatch.zip`은
> 재학습이 필요하다(의도된 일회성 비용). 기본값 변경으로 기존 벤치마크 baseline 수치도
> 이동한다 — MODEL_REPORT는 재생성한다.

## 8. 테스트 (TDD)

- `wip_dwell_time` 산식: 기존 테스트 유지/보강.
- `train_alloc_model`: 작은 문제에서 `ppo_alloc.zip` 생성 + 산출 배분이 tool/eqp 제약을
  지키는지 (smoke).
- 조건부 가이드 준수: util<threshold면 항=0, 밴드 안이면 페널티 0, 밴드 밖이면 >0 인지
  단위 테스트.
- 2-산출: `infer`/`eval`이 rule_timekey마다 가이드+동적 둘 다 반환하는지.
- 기존 `tests/` 회귀 통과(차원 변경 영향 반영해 갱신).

## 9. 비범위

- DB 기록 경로(RTS_ASSIGN/CONV write 호출부) — 현행과 동일하게 미구현 유지.
- 단일 정책의 전 shape 일반화(패딩+마스킹) — 후속.
- 멀티피리어드(`core/flow.py` 류) 별도 경로 — 본 설계는 단일 시뮬레이터 경로.
