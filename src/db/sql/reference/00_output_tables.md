# RTS 출력 테이블 정리

`python run.py infer` 실행 시 추론 결과가 아래 **3종 INF/HIS** 쌍에 기록됩니다.  
공통: 동일 `RULE_TIMEKEY` 기존 행 **DELETE 후 INSERT** (`delete_by_timekey.sql`).

DDL: `01_create_tables.sql` · 샘플: `03_sample_output_data.sql` · 확인: `04_verify_queries.sql`

---

## 개요

| 구분 | INF / HIS | Mode | 행 단위 | 빌더 | DB writer |
|------|-----------|------|---------|------|-----------|
| 장비 배분 (가이드) | `RTS_EQPALLOCATION_*` | Mode 1 | 공정×모델 | `build_eqpallocation_rows()` | `write_eqpallocation_results()` |
| 장비 배치 | `RTS_ASSIGN_*` | Mode 2 | eqp×hour | `build_assign_rows()` | `write_assign_results()` |
| 전환 계획 | `RTS_EQPCONVPLAN_*` | Mode 2 | batch 전환 이벤트 | `build_eqpconvplan_rows()` | `write_eqpconvplan_results()` |

`config.py` 상수: `EQPALLOCATION_TABLE`, `ASSIGN_TABLE`, `EQPCONVPLAN_TABLE`  
하위호환 alias: `GUIDE_TABLE`→EQPALLOCATION, `CONV_TABLE`→EQPCONVPLAN, `RESULT_TABLE`→ASSIGN

---

## 1. RTS_EQPALLOCATION_INF / RTS_EQPALLOCATION_HIS

**목적:** Mode 1 가이드 — 공정×장비모델별 **목표 배치 대수**와 **현재 배치 대수**.

| 컬럼 | 설명 |
|------|------|
| `FAC_ID` | 공장 ID (`problem.facid`, 없으면 `-`) |
| `RULE_TIMEKEY` | 스냅샷 키 (16자) |
| `BATCH_ID` | 배치 ID |
| `PLAN_PROD_KEY` | 계획 제품 키 |
| `OPER_ID` | 공정 ID |
| `EQP_MODEL_CD` | 장비 모델 |
| `TARGET_EQP_CNT` | 목표 장비 수 (가이드 배분, 정수) |
| `CUR_EQP_CNT` | 현재 장비 수 (`init_assign`) |
| `MODE_TYP` | `ALLOC_RL` 가이드 → `RL`, 그 외 → `Heuristic` |
| `CRT_TM` / `CRT_USER_ID` | insert 시 `SYSTIMESTAMP` / `SYS_ID` |

**PK (INF):** `RULE_TIMEKEY, FAC_ID, BATCH_ID, PLAN_PROD_KEY, OPER_ID, EQP_MODEL_CD`  
**HIS 추가:** `EVENT_TIMEKEY` = `TO_CHAR(SYSTIMESTAMP,'YYYYMMDDHH24MISS')`

**JSON:** `guide.eqpallocation_rows` (`guide.rows` alias)

---

## 2. RTS_ASSIGN_INF / RTS_ASSIGN_HIS

**목적:** Mode 2 동적 시뮬 — 장비(호기)별 배치·생산 구간.

| 컬럼 | 설명 |
|------|------|
| `RULE_TIMEKEY` | 스냅샷 키 |
| `EQP_ID` | 장비 호기 ID (`M1-001` 형식) |
| `EQP_MODEL_CD` | 장비 모델 |
| `SEQ_NO` | **호기별** 순번 (1부터) |
| `START_TIME` / `END_TIME` | 배치 구간 (16자) |
| `PLAN_PROD_KEY` / `OPER_ID` | 작업 공정 |
| `PRODUCE_QTY` | 구간 생산량 |

**PK (INF):** `RULE_TIMEKEY, EQP_ID, SEQ_NO`  
**HIS PK:** 위 + `CRT_TM`

**JSON:** `dynamic.assign_rows` (`allocation_rows` alias)

---

## 3. RTS_EQPCONVPLAN_INF / RTS_EQPCONVPLAN_HIS

**목적:** Mode 2 동적 시뮬 — **BATCH_ID가 바뀌는** 장비 이동(tool 전환) 계획.

| 컬럼 | 설명 |
|------|------|
| `FAC_ID` | 공장 ID |
| `RULE_TIMEKEY` | 스냅샷 키 |
| `JOB_ID` | `CONV_{seq:03d}_{RULE_TIMEKEY}` |
| `PRCS_STAT_CD` | `WAIT` |
| `RTS_GBN_CD` | `RTS` |
| `TESTER_EQP_MODEL_CD` | 이동 장비 모델 |
| `CONV_START_TM` | 전환 시작 (`yyyyMMddHHmm`, 시뮬 EVENT_TM) |
| `CONV_END_TM` | 시작 + 1시간 |
| `CONV_TIME` | `1` |
| `LOT_CD` / `TEMPER_VAL` | FROM batch `/` 앞·뒤 (예 `9C/92` → `9C`, `92`) |
| `TO_LOT_CD` / `TO_TEMPER_VAL` | TO batch 동일 규칙 |
| `PLAN_PROD_ATTR_VAL` / `TO_PLAN_PROD_ATTR_VAL` | FROM/TO `PLAN_PROD_KEY` |
| `REASON_CD` / `REASON_CTN` | `RTS-001` / `테스트 데이터` |
| `TRANSMIT_YN` / `TRANSMIT_TM` | `N` / NULL |
| `CRT_TM`·`CHG_TM` / `CRT_USER_ID`·`CHG_USER_ID` | `SYSDATE` / `RTS` |

**PK (INF):** `RULE_TIMEKEY, JOB_ID`  
**HIS 추가:** `EVENT_TIMEKEY` = `TO_CHAR(SYSTIMESTAMP,'YYYYMMDDHH24MISS')`

**JSON:** `dynamic.eqpconvplan_rows` (`conv_rows` alias)

---

## 추론 결과 JSON → DB 매핑

```
{RULE_TIMEKEY}_result.json
├── guide.eqpallocation_rows  → RTS_EQPALLOCATION_INF/HIS
└── dynamic
    ├── assign_rows         → RTS_ASSIGN_INF/HIS
    └── eqpconvplan_rows    → RTS_EQPCONVPLAN_INF/HIS
```

진입점: `db.write_inference_result(rule_timekey, doc)` (`run.py infer`)

---

## HIS 테이블 패턴

| 테이블 | 이력 키 | insert SQL |
|--------|---------|------------|
| EQPALLOCATION | `EVENT_TIMEKEY` (VARCHAR14) | `insert_eqpallocation_his.sql` |
| ASSIGN | `CRT_TM` (TIMESTAMP, PK 일부) | `insert_assign.sql` (INF/HIS 동일) |
| EQPCONVPLAN | `EVENT_TIMEKEY` (VARCHAR14) | `insert_eqpconvplan_his.sql` |

---

## 폐기 테이블 (DDL에서 DROP)

- `RTS_PLAN_ACHV_*` (제거됨)
- `RTS_GUIDE_*` → `RTS_EQPALLOCATION_*`
- `RTS_CONV_*` → `RTS_EQPCONVPLAN_*`
- `RTS_RSLT_MAS/HIS` (구 설계명, 미사용)
