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
#         "GUIDE_SOURCE": "ANALYTIC",
#         "CRT_USER_ID": config.SYS_ID 값으로 기록
#       }
#     ]
#   },
#   "dynamic": {
#     "plan_achv_rows": [...],
#     "assign_rows": [...],
#     "conv_rows": [...]
#   }
# }
# ```
#
# `guide.rows` → RTS_GUIDE_INF/HIS
# `dynamic.*` → RTS_PLAN_ACHV / RTS_ASSIGN / RTS_CONV (기존과 동일 키)
#
# ## Oracle DDL — RTS_GUIDE_INF / RTS_GUIDE_HIS (신규)
#
# ```sql
# CREATE TABLE RTS_GUIDE_INF (
#   RULE_TIMEKEY     VARCHAR2(16)  NOT NULL,
#   PLAN_PROD_KEY    VARCHAR2(50)  NOT NULL,
#   OPER_ID          VARCHAR2(50)  NOT NULL,
#   EQP_MODEL_CD     VARCHAR2(50)  NOT NULL,
#   TARGET_EQP_CNT   NUMBER(10,4)  NOT NULL,
#   GUIDE_SOURCE     VARCHAR2(20)  NOT NULL,  -- ANALYTIC | ALLOC_RL
#   CRT_TM           TIMESTAMP     DEFAULT SYSTIMESTAMP NOT NULL,
#   CRT_USER_ID      VARCHAR2(50)  NOT NULL,
#   CONSTRAINT PK_RTS_GUIDE_INF PRIMARY KEY (
#     RULE_TIMEKEY, PLAN_PROD_KEY, OPER_ID, EQP_MODEL_CD
#   )
# );
#
# CREATE TABLE RTS_GUIDE_HIS AS SELECT * FROM RTS_GUIDE_INF WHERE 1=0;
# ```
#
# ## 학습용 JSON (data/train/{RULE_TIMEKEY}.json)
#
# 입력 JSON과 동일 형식. DB `list_timekeys_in_range`로 export.

SCHEMA_VERSION = 1
