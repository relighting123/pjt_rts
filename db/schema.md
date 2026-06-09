"""DB 스냅샷·추론 결과 테이블 및 JSON 스키마."""

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
# }
# `conv_groups`는 JSON에 두지 않음 — config.py CONV_GROUPS로 설정.
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
#     "rows": [
#       {
#         "RULE_TIMEKEY": "2026052922500000",
#         "PLAN_PROD_KEY": "P1",
#         "OPER_ID": "OP10",
#         "EQP_MODEL_CD": "M1",
#         "TARGET_EQP_CNT": 1.0,
#         "FAC_ID": "ICPRB",
#         "BATCH_ID": "B1",
#         "MODE_TYP": "Heuristic",
#         "CUR_EQP_CNT": 1,
#         "CRT_USER_ID": config.SYS_ID 값으로 기록
#       }
#     ]
#   },
#   "dynamic": {
#     "plan_achv_rows": [...],
#     "assign_rows": [...],
#     "eqpconvplan_rows": [...]
#     "conv_rows": [...]  # eqpconvplan_rows alias
#   }
# }
# ```
#
# `guide.eqpallocation_rows` → RTS_EQPALLOCATION_INF/HIS (`rows`는 alias)
# `dynamic.*` → RTS_PLAN_ACHV / RTS_ASSIGN / RTS_EQPCONVPLAN
# (`eqpconvplan_rows` 권장, `conv_rows`는 하위호환 alias)
#
# ## Oracle DDL — RTS_EQPALLOCATION_INF / RTS_EQPALLOCATION_HIS
#
# FAC_ID, BATCH_ID, OPER_ID, MODE_TYP(RL|Heuristic), TARGET_EQP_CNT, CUR_EQP_CNT
# HIS EVENT_TIMEKEY = TO_CHAR(CRT_TM, 'YYYYMMDDHH24MISS')
#
# ## 학습용 JSON (data/train/{RULE_TIMEKEY}.json)
#
# 입력 JSON과 동일 형식. DB `list_timekeys_in_range`로 export.

SCHEMA_VERSION = 1
