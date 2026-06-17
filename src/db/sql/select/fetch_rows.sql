-- 입력 스냅샷 long-format 조회 (RULE_TIMEKEY + FAC_ID + BATCH_ID LIKE 필수)
-- AS 별칭 = db.input_row.InputRow 필드명 (컬럼명 기반 매핑)
SELECT RULE_TIMEKEY AS rule_timekey,
       FAC_ID AS fac_id,
       BATCH_ID AS batch_id,
       LOT_CD AS lot_cd,
       TEMPER_VAL AS temper_val,
       PLAN_PROD_KEY AS plan_prod_key,
       OPER_ID AS oper_id,
       OPER_SEQ AS oper_seq,
       EQP_MODEL_CD AS eqp_model,
       GBN_CD AS gbn_cd,
       ATTR_VAL AS attr_val
  FROM {table}
 WHERE RULE_TIMEKEY = :rk
   AND FAC_ID = :facid
   AND BATCH_ID LIKE :batch_like
