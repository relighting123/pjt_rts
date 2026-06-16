-- 최신 RULE_TIMEKEY (facid별)
SELECT MAX(RULE_TIMEKEY)
  FROM {table}
 WHERE FAC_ID = :facid
