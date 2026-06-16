-- =============================================================================
-- RTS 출력 샘플 — 가이드 + 동적 운영 (검증·UI 확인용)
-- RULE_TIMEKEY = 2026052922500000 (benchmark_01 기준 예시)
-- 실제 운영: python run.py infer 가 DELETE 후 INSERT (INF/HIS 동시)
-- 실행 전: @db/sql/reference/01_create_tables.sql
-- =============================================================================

DEFINE RK = '2026052922500000'
DEFINE USER_ID = 'RL_AGENT'

-- 기존 샘플 삭제
DELETE FROM RTS_EQPALLOCATION_INF WHERE RULE_TIMEKEY = '&RK';
DELETE FROM RTS_EQPALLOCATION_HIS WHERE RULE_TIMEKEY = '&RK';
DELETE FROM RTS_ASSIGN_INF    WHERE RULE_TIMEKEY = '&RK';
DELETE FROM RTS_ASSIGN_HIS    WHERE RULE_TIMEKEY = '&RK';
DELETE FROM RTS_EQPCONVPLAN_INF WHERE RULE_TIMEKEY = '&RK';
DELETE FROM RTS_EQPCONVPLAN_HIS WHERE RULE_TIMEKEY = '&RK';

-- ---------------------------------------------------------------------------
-- 1. 가이드 배분 (RTS_EQPALLOCATION_INF) — Mode 1
-- ---------------------------------------------------------------------------
INSERT INTO RTS_EQPALLOCATION_INF
  (FAC_ID, RULE_TIMEKEY, BATCH_ID, PLAN_PROD_KEY, OPER_ID, EQP_MODEL_CD,
   TARGET_EQP_CNT, CUR_EQP_CNT, MODE_TYP, CRT_USER_ID)
VALUES ('ICPRB', '&RK', 'B1', 'P1', 'OP10', 'M1', 1, 1, 'Heuristic', '&USER_ID');

INSERT INTO RTS_EQPALLOCATION_HIS
  (FAC_ID, RULE_TIMEKEY, BATCH_ID, PLAN_PROD_KEY, OPER_ID, EQP_MODEL_CD,
   TARGET_EQP_CNT, CUR_EQP_CNT, MODE_TYP, CRT_USER_ID, EVENT_TIMEKEY)
VALUES ('ICPRB', '&RK', 'B1', 'P1', 'OP10', 'M1', 1, 1, 'Heuristic', '&USER_ID',
        TO_CHAR(SYSTIMESTAMP, 'YYYYMMDDHH24MISS'));

-- ---------------------------------------------------------------------------
-- 2. 장비 배치 (RTS_ASSIGN_INF)
-- ---------------------------------------------------------------------------
INSERT INTO RTS_ASSIGN_INF
  (RULE_TIMEKEY, EQP_ID, EQP_MODEL_CD, SEQ_NO, START_TIME, END_TIME,
   PLAN_PROD_KEY, OPER_ID, PRODUCE_QTY, CRT_USER_ID)
VALUES ('&RK', 'M1-001', 'M1', 1, '&RK', '2026052923500000', 'P1', 'OP10', 100, '&USER_ID');

INSERT INTO RTS_ASSIGN_INF VALUES
  ('&RK', 'M1-001', 'M1', 2, '2026052923500000', '2026053000500000', 'P1', 'OP10', 100, '&USER_ID');

INSERT INTO RTS_ASSIGN_INF VALUES
  ('&RK', 'M1-001', 'M1', 3, '2026053000500000', '2026053001500000', 'P1', 'OP10', 100, '&USER_ID');

-- ---------------------------------------------------------------------------
-- 3. 전환 계획 (RTS_EQPCONVPLAN_INF) — benchmark_01 은 전환 없음 (행 없음)
-- ---------------------------------------------------------------------------

COMMIT;

-- 확인
SELECT 'EQPALLOCATION' AS TBL, COUNT(*) AS CNT FROM RTS_EQPALLOCATION_INF WHERE RULE_TIMEKEY = '&RK'
UNION ALL
SELECT 'ASSIGN', COUNT(*) FROM RTS_ASSIGN_INF WHERE RULE_TIMEKEY = '&RK'
UNION ALL
SELECT 'EQPCONVPLAN', COUNT(*) FROM RTS_EQPCONVPLAN_INF WHERE RULE_TIMEKEY = '&RK';
