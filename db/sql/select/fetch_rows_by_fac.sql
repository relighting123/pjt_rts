-- 입력 스냅샷 long-format 조회 (RULE_TIMEKEY + FAC_ID)
SELECT RULE_TIMEKEY,
       FAC_ID,
       BATCH_ID,
       PLAN_PROD_KEY,
       OPER_ID,
       OPER_SEQ,
       EQP_MODEL_CD,
       GBN_CD,
       ATTR_VAL
  FROM {table}
 WHERE RULE_TIMEKEY = :rk
   AND FAC_ID = :fac_id
