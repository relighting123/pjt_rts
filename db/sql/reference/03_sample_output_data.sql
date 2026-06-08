-- =============================================================================
-- RTS 출력 샘플 — 가이드 + 동적 운영 (검증·UI 확인용)
-- RULE_TIMEKEY = 2026052922500000 (benchmark_01 기준 예시)
-- 실제 운영: python run.py infer 가 DELETE 후 INSERT (INF/HIS 동시)
-- 실행 전: @db/sql/reference/01_create_tables.sql
-- =============================================================================

DEFINE RK = '2026052922500000'
DEFINE USER_ID = 'RL_AGENT'

-- 기존 샘플 삭제
DELETE FROM RTS_GUIDE_INF     WHERE RULE_TIMEKEY = '&RK';
DELETE FROM RTS_GUIDE_HIS     WHERE RULE_TIMEKEY = '&RK';
DELETE FROM RTS_PLAN_ACHV_INF WHERE RULE_TIMEKEY = '&RK';
DELETE FROM RTS_PLAN_ACHV_HIS WHERE RULE_TIMEKEY = '&RK';
DELETE FROM RTS_ASSIGN_INF    WHERE RULE_TIMEKEY = '&RK';
DELETE FROM RTS_ASSIGN_HIS    WHERE RULE_TIMEKEY = '&RK';
DELETE FROM RTS_EQPCONVPLAN_INF WHERE RULE_TIMEKEY = '&RK';
DELETE FROM RTS_EQPCONVPLAN_HIS WHERE RULE_TIMEKEY = '&RK';

-- ---------------------------------------------------------------------------
-- 1. 가이드 배분 (RTS_GUIDE_INF) — Mode 1
-- ---------------------------------------------------------------------------
INSERT INTO RTS_GUIDE_INF
  (RULE_TIMEKEY, PLAN_PROD_KEY, OPER_ID, EQP_MODEL_CD, TARGET_EQP_CNT, GUIDE_SOURCE, CRT_USER_ID)
VALUES ('&RK', 'P1', 'OP10', 'M1', 1.0, 'ANALYTIC', '&USER_ID');

INSERT INTO RTS_GUIDE_HIS
  (RULE_TIMEKEY, PLAN_PROD_KEY, OPER_ID, EQP_MODEL_CD, TARGET_EQP_CNT, GUIDE_SOURCE, CRT_USER_ID)
VALUES ('&RK', 'P1', 'OP10', 'M1', 1.0, 'ANALYTIC', '&USER_ID');

-- ---------------------------------------------------------------------------
-- 2. 계획/달성 (RTS_PLAN_ACHV_INF) — 3시간 horizon 예시
-- ---------------------------------------------------------------------------
INSERT INTO RTS_PLAN_ACHV_INF
  (RULE_TIMEKEY, EVENT_TM, BATCH_ID, PLAN_PROD_KEY, OPER_ID,
   PLAN_QTY, REMAIN_QTY, PRODUCE_QTY, ACHIEVE_RATE, EQP_UTIL_RATE, CRT_USER_ID)
VALUES ('&RK', '&RK', 'B1', 'P1', 'OP10', 300, 200, 100, 0.3333, 1.0, '&USER_ID');

INSERT INTO RTS_PLAN_ACHV_INF VALUES
  ('&RK', '2026052923500000', 'B1', 'P1', 'OP10', 300, 100, 100, 0.6667, 1.0, '&USER_ID');

INSERT INTO RTS_PLAN_ACHV_INF VALUES
  ('&RK', '2026053000500000', 'B1', 'P1', 'OP10', 300, 0, 100, 1.0, 1.0, '&USER_ID');

-- ---------------------------------------------------------------------------
-- 3. 장비 배치 (RTS_ASSIGN_INF)
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
-- 4. 전환 계획 (RTS_EQPCONVPLAN_INF) — benchmark_01 은 전환 없음 (행 없음)
-- ---------------------------------------------------------------------------

COMMIT;

-- 확인
SELECT 'GUIDE' AS TBL, COUNT(*) AS CNT FROM RTS_GUIDE_INF WHERE RULE_TIMEKEY = '&RK'
UNION ALL
SELECT 'PLAN_ACHV', COUNT(*) FROM RTS_PLAN_ACHV_INF WHERE RULE_TIMEKEY = '&RK'
UNION ALL
SELECT 'ASSIGN', COUNT(*) FROM RTS_ASSIGN_INF WHERE RULE_TIMEKEY = '&RK'
UNION ALL
SELECT 'EQPCONVPLAN', COUNT(*) FROM RTS_EQPCONVPLAN_INF WHERE RULE_TIMEKEY = '&RK';
