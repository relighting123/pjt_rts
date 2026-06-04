# 장비 전환 스케줄링 강화학습 시스템 — 설계 문서

- 작성일: 2026-06-05
- 상태: 승인됨 (구현 계획 단계로 진행)

## 1. 목적

`plan_prod_key`/`OPER`별 계획량에 대해 장비 배치를 수행하여 **전체 평균 계획달성률**을
높인다. 초기 장비 배치는 주어진 상태에서, **시간이 1시간씩 흐르는 동적 환경** 안에서
매 시간 "각 장비(모델별 대수)를 옮길지/유지할지"를 가동률·계획달성 기준으로 판단한다.
모방학습으로 초기 정책을 잡고 PPO(Stable-Baselines3)로 강화한다.

## 2. 범위 (이번 구축)

- **단순 평면 파일 구조** + 핵심 수직 슬라이스: 도메인모델 → 1시간 step 시뮬레이터 →
  최적/휴리스틱 teacher → 모방학습(BC) → PPO → 평가/기록까지 한 번에 동작.
- **DB 없이 벤치마크(JSON) 우선.** `db.py`는 `.env`를 읽는 얇은 Oracle 어댑터로 두되
  `oracledb` 미설치 시에도 코어는 동작.
- 동적 멀티피리어드 단일 모드에 집중(README의 plan-only/wip-static 분리 모드는 후속).

## 3. 문제 정식화

### 상태 (매 시간)
- 태스크별 (`plan_prod_key` × `OPER`): 잔여 계획량(D0_TARGET − 누적생산), 현재 유입재공
  (WIP 큐), OPER_SEQ.
- (batch × model)별: 현재 배치 대수, 여유 tool 수, 전환 중(Idle 잔여시간) 대수.
- 적격성·UPH 행렬(`PLAN_PROD_KEY`/`OPER`/`EQP_MODEL` → UPH, AVAIL_YN), conversion 그룹 정의.

### 액션 (model-count 단위, substep 방식)
- 매 시간 내부에서 substep마다 `(모델 M 1대를 태스크 A→B로 이동)` 또는 `commit` 선택.
- 마스킹: 부적격 조합, conversion 그룹 외 이동, to-batch tool 부족 이동은 선택 불가.
- `commit` 시 1시간 경과 처리.

### 전이 (1시간 경과)
- 각 (model, task) 배치 대수 × UPH × 1h, 단 **유입재공(WIP) 상한**으로 캡 → 생산량 확정.
- 생산분은 OPER_SEQ 다음 공정의 WIP로 **다음 시간에** 유입(앞→뒤 흐름).
- batch 전환한 대수는 이번 1시간 **Idle(생산 0)**, to-batch tool 소진 / from-batch tool 반환.
- tool 수(`TOOL_QTY`, batch×model)가 batch별 동시 가동 가능 대수를 제한하는 공유 풀.

### 전환 규칙 (배경지식 [6], 범위 [5])
- 동일 `batch_id` 내 `plan_prod_key`/`OPER` 변경: 시간·tool 비용 없음(자유 이동).
- `batch_id` 변경: tool 교체 → 1시간 Idle + tool 반환/소진.
- conversion 그룹(예: `G001:[9C/92, 9C/102]`) 내에서만 batch 전환 허용. 그룹 외 전환 불가.

### 보상
- 시간별 dense: 미충족 계획에 기여한 생산 단위(캡 적용).
- 종료 시: 평균 계획달성률 보너스.
- 전환 비용은 "1시간 Idle로 인한 생산 손실"로 자연 반영(인위적 페널티 최소화).
- 목적 함수: 전체 평균 달성률 극대화 (보조 지표: 장비 가동률).

## 4. 파일 구조 (단순 평면)

```
data/                 # 임시/중간 데이터
saved_models/         # ppo_dispatch.zip + bc_init 정책
benchmarks/           # benchmark_01.json … (+ 각 문제의 ground_truth 최적해)
.env                  # DB 접속정보(민감)
.gitignore            # .env 등 제외
config.py             # 설정·하이퍼파라미터, .env 로드
db.py                 # Oracle 어댑터(oracledb 선택적). RTS_LINEDSDB_INF 조회→pivot, 결과/전환 기록
simulator.py          # 도메인모델 + 1시간 step 시뮬레이터(WIP흐름·전환Idle·tool풀) + teacher + 지표
env.py                # Gym 환경(model-count substep 액션 + 마스킹)
train.py              # 모방학습(BC)→PPO(SB3), 학습 후 벤치마크 평가 + 결과 md 기록
test.py               # 학습 정책 평가, RL vs 휴리스틱 vs 최적 비교, 간트/리포트
run.py                # CLI 디스패처(train/infer/eval) — README 사용 예시와 정합
```

> `benchmarks/`·`run.py`는 README [1] 목록엔 없으나 본문이 벤치마크와 `python run.py …`를
> 전제하므로 포함한다.

## 5. 데이터 흐름

- **벤치마크 경로(우선):** `benchmarks/*.json` → `simulator.ProblemInstance` → env/teacher → 평가.
- **DB 경로(얇은 어댑터):** `.env` → `db.py`가 `RTS_LINEDSDB_INF` 조회 → `GBN_CD` 피벗
  (ASSIGN_EQUIP_CNT / UPH / WIP_QTY / D0_TARGET / D1_TARGET / TOOL_QTY) → 동일한
  `ProblemInstance` → 추론 결과를 `RTS_RSLT_MAS/HIS`, batch 변경 시점은
  `RTS_CONV_INF/HIS`에 삭제 후 insert.
- 두 경로가 동일 도메인 객체로 수렴 → 코어 로직은 DB 유무와 무관.

### RULE_TIMEKEY / 타깃 치환
- 추론: `rule_timekey` 미지정 시 `MAX(RULE_TIMEKEY)`. 조회·출력 키 동일. START_TIME = rule_timekey.
- D0_TARGET: rule_timekey ~ 다음날 07시 계획. D1_TARGET: 다음날 07시 ~ 그 다음날 07시.
  horizon은 D0_TARGET 구간(rule_timekey → 다음 07시)을 기본으로 한다.

## 6. 벤치마크 세트 (최적해 기지)

각 JSON은 문제 + `ground_truth`(최적 평균달성률·배치)를 포함. 7종:
1. 전환 불필요 기본(정합성 sanity).
2. 단일 batch 전환 필요(앞공정 빌드 → 전환 → 뒷공정).
3. 병목: 특정 공정에 장비 몰림 → 재배치해야 최종공정 달성.
4. UPH 이질성: 같은 태스크 모델별 UPH 차 → 모델 선택이 달성률 좌우.
5. Capacity 초과: 계획 > 총 capacity → 달성률 상한 검증.
6. WIP 부족: 유입재공 한계로 장비 남아도 생산 제한.
7. Thrashing 회피: 2배치 교차 다제품 → 묶어서 전환 최소화가 최적.

휴리스틱 teacher(한계이득 그리디 + batch 묶기 lookahead)가 7종에서 최적해에 도달하는지
검증 후, 그 궤적으로 모방학습 초기화.

## 7. 학습 / 평가 / 기록

- `train.py`: teacher 궤적 BC로 PPO 정책 초기화 → SB3 PPO 학습(기본 작은 steps) →
  종료 시 전체 벤치마크로 Optimal·휴리스틱·RL 비교(`evaluate_all_benchmark_datasets`).
- `test.py` / `eval`: 벤치마크별 시간대별 PLAN_PROD_KEY/MODEL별 대수, 계획달성률,
  장비달성률 + 상단 평균(계획·장비) + 최적해 동일 형태 제시 + 장비별 간트.
- 평가 결과는 **md 파일로 갱신(기록용)** — 모델 수준 추적.

## 8. 의존성

- 코어: Python 표준 + numpy.
- RL: `stable-baselines3`, `gymnasium` (optional extra `[rl]`).
- DB: `oracledb` (optional extra `[oracle]`), `python-dotenv`.

## 9. 비범위 (후속)

- README의 plan-only / wip-static / dynamic **분리 모드 옵션화**(현재는 동적 단일 모드).
- 실제 Oracle 운영 검증/배포(DEPLOYMENT.md).
- `num_envs` 병렬 가속 등 성능 튜닝.
