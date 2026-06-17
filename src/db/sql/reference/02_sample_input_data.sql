-- =============================================================================
-- RTS 입력 샘플 — RTS_LINEDSDB_INF
-- benchmark_01 / benchmark_02 에 해당하는 2개 RULE_TIMEKEY
-- 실행 전: @db/sql/reference/01_create_tables.sql
-- =============================================================================

DELETE FROM RTS_LINEDSDB_INF;

-- ---------------------------------------------------------------------------
-- 스냅샷 1: benchmark_01 (P1/OP10, 1대, plan 300)
-- RULE_TIMEKEY = 2026052922500000
-- ---------------------------------------------------------------------------
INSERT INTO RTS_LINEDSDB_INF
  (RULE_TIMEKEY, FAC_ID, BATCH_ID, LOT_CD, TEMPER_VAL, PLAN_PROD_KEY, OPER_ID, OPER_SEQ, EQP_MODEL_CD, GBN_CD, ATTR_VAL)
VALUES ('2026052922500000', 'ICPRB', 'B1', 'B1', '-', 'P1', 'OP10', 1, 'M1', 'EQUIP_UPH', '100');
INSERT INTO RTS_LINEDSDB_INF VALUES
  ('2026052922500000', 'ICPRB', 'B1', 'B1', '-', 'P1', 'OP10', 1, 'M1', 'ASSIGN_EQUIP_CNT', '1');
INSERT INTO RTS_LINEDSDB_INF VALUES
  ('2026052922500000', 'ICPRB', 'B1', 'B1', '-', 'P1', 'OP10', 1, 'M1', 'D0_TARGET_QTY', '300');
INSERT INTO RTS_LINEDSDB_INF VALUES
  ('2026052922500000', 'ICPRB', 'B1', 'B1', '-', 'P1', 'OP10', 1, 'M1', 'WIP_QTY', '1000');
INSERT INTO RTS_LINEDSDB_INF VALUES
  ('2026052922500000', 'ICPRB', 'B1', 'B1', '-', 'P1', 'OP10', 1, 'M1', 'TOOL_QTY', '1');
-- 실제 장비 호기 명단: GBN_CD='EQP_ID', ATTR_VAL=호기 ID
INSERT INTO RTS_LINEDSDB_INF VALUES
  ('2026052922500000', 'ICPRB', 'B1', 'B1', '-', 'P1', 'OP10', 1, 'M1', 'EQP_ID', 'ETX-101');

-- ---------------------------------------------------------------------------
-- 스냅샷 2: benchmark_02 (PA/PB batch 전환, plan 200+100)
-- RULE_TIMEKEY = 2026053000500000
-- ---------------------------------------------------------------------------
INSERT INTO RTS_LINEDSDB_INF VALUES
  ('2026053000500000', 'ICPRB', 'B1', 'B1', '-', 'PA', 'OP10', 1, 'M1', 'EQUIP_UPH', '100');
INSERT INTO RTS_LINEDSDB_INF VALUES
  ('2026053000500000', 'ICPRB', 'B1', 'B1', '-', 'PA', 'OP10', 1, 'M1', 'ASSIGN_EQUIP_CNT', '1');
INSERT INTO RTS_LINEDSDB_INF VALUES
  ('2026053000500000', 'ICPRB', 'B1', 'B1', '-', 'PA', 'OP10', 1, 'M1', 'D0_TARGET_QTY', '200');
INSERT INTO RTS_LINEDSDB_INF VALUES
  ('2026053000500000', 'ICPRB', 'B1', 'B1', '-', 'PA', 'OP10', 1, 'M1', 'WIP_QTY', '1000');
INSERT INTO RTS_LINEDSDB_INF VALUES
  ('2026053000500000', 'ICPRB', 'B1', 'B1', '-', 'PA', 'OP10', 1, 'M1', 'TOOL_QTY', '1');

INSERT INTO RTS_LINEDSDB_INF VALUES
  ('2026053000500000', 'ICPRB', 'B2', 'B2', '-', 'PB', 'OP10', 1, 'M1', 'EQUIP_UPH', '100');
INSERT INTO RTS_LINEDSDB_INF VALUES
  ('2026053000500000', 'ICPRB', 'B2', 'B2', '-', 'PB', 'OP10', 1, 'M1', 'D0_TARGET_QTY', '100');
INSERT INTO RTS_LINEDSDB_INF VALUES
  ('2026053000500000', 'ICPRB', 'B2', 'B2', '-', 'PB', 'OP10', 1, 'M1', 'WIP_QTY', '1000');
INSERT INTO RTS_LINEDSDB_INF VALUES
  ('2026053000500000', 'ICPRB', 'B2', 'B2', '-', 'PB', 'OP10', 1, 'M1', 'TOOL_QTY', '1');

COMMIT;

-- 확인 쿼리
SELECT RULE_TIMEKEY, PLAN_PROD_KEY, OPER_ID, LOT_CD, GBN_CD, ATTR_VAL
  FROM RTS_LINEDSDB_INF
 ORDER BY RULE_TIMEKEY, PLAN_PROD_KEY, OPER_ID, GBN_CD;

SELECT MAX(RULE_TIMEKEY) AS MAX_RULE_TIMEKEY FROM RTS_LINEDSDB_INF;
