"""DB 스냅샷·추론 결과 테이블 및 JSON 스키마.

출력 테이블 상세: db/sql/reference/00_output_tables.md
"""

# ## 입력 JSON (data/inference/{RULE_TIMEKEY}.json)
#
# ProblemInstance와 동일. `simulator.load_problem()` / `save_problem()` 형식.
#
# ```json
# {
#   "rule_timekey": "2026052922500000",
#   "horizon_hours": 12,
#   "switch_time_hours": 1,
#   "tasks": [{"plan_prod_key","oper_id","oper_seq","batch_id","plan_qty","init_wip"}],
#   "uph": [{"plan_prod_key","oper_id","eqp_model","uph"}],
#   "eqp_qty": {"M1": 1},
#   "init_assign": [{"eqp_model","plan_prod_key","oper_id","count"}],
#   "tool_qty": [{"batch_id","eqp_model","tool_qty"}],
#   "equipments": [{"eqp_id","eqp_model","batch_id","plan_prod_key","oper_id"}],
#   "facid": "ICPRB"
# }
# `conv_groups`는 JSON에 두지 않음 — config.py CONV_GROUPS로 설정.
#
# `equipments` (선택): 실제 장비 호기 명단. DB에서는 RTD_ARRANGE_INF
# 테이블에서 EQP_ID·EQP_MODEL_CD·BATCH_ID·PLAN_PROD_KEY를 조회해 채운다
# (db.adapter.fetch_equipments → arrange_rows_to_equipments).
# 제공 시 RTS_ASSIGN(간트차트)·RTS_EQPCONVPLAN의 EQP_ID가 실제 호기로
# 매핑되고, 미제공/조회 실패 시 가상 호기({model}-{seq:03d})를 사용한다.
# ```
#
# ## 추론 결과 JSON (data/inference/{RULE_TIMEKEY}_result.json)
#
# ```json
# {
#   "schema_version": 1,
#   "rule_timekey": "2026052922500000",
#   "policy": "RL",
#   "plan_achievement": 0.95,
#   "eqp_util_rate": 0.75,
#   "guide": {
#     "source": "ANALYTIC",
#     "eqpallocation_rows": [...],
#     "rows": [...]
#   },
#   "dynamic": {
#     "assign_rows": [...],
#     "eqpconvplan_rows": [...]
#   }
# }
# ```
#
# ## 출력 Oracle 테이블 (infer 시 DELETE + INSERT)
#
# | JSON 키 | INF / HIS | 설명 |
# |---------|-----------|------|
# | guide.eqpallocation_rows | RTS_EQPALLOCATION_* | Mode 1 장비 배분 가이드 |
# | dynamic.assign_rows | RTS_ASSIGN_* | 장비 배치·생산 |
# | dynamic.eqpconvplan_rows | RTS_EQPCONVPLAN_* | batch 전환 계획 |
#
# alias: guide.rows, dynamic.conv_rows, dynamic.allocation_rows
#
# ## 학습용 JSON (data/train/{RULE_TIMEKEY}.json)
#
# 입력 JSON과 동일 형식. DB `list_timekeys_in_range`로 export.

SCHEMA_VERSION = 1
