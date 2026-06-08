-- 추론 결과 기록 전 해당 RULE_TIMEKEY 삭제
DELETE FROM {table}
 WHERE RULE_TIMEKEY = :rk
