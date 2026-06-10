-- 장비 호기 현재 배치 명단 조회 (RTD_ARRANGE_INF)
-- AS 별칭 = db.adapter.arrange_rows_to_equipments 필드명 (컬럼명 기반 매핑)
SELECT EQP_ID AS eqp_id,
       EQP_MODEL_CD AS eqp_model_cd,
       BATCH_ID AS batch_id,
       PLAN_PROD_KEY AS plan_prod_key
  FROM {table}
 WHERE RULE_TIMEKEY = :rk
   AND FAC_ID = :facid
   AND BATCH_ID LIKE :batch_like
