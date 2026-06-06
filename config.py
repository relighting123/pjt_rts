"""전역 설정과 .env 로더."""
from __future__ import annotations
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BENCHMARKS_DIR = ROOT / "benchmarks"
SAVED_MODELS_DIR = ROOT / "saved_models"
DATA_DIR = ROOT / "data"
ARTIFACTS_DIR = ROOT / "artifacts"
REPORT_PATH = ROOT / "MODEL_REPORT.md"
HTML_REPORT_PATH = ROOT / "MODEL_REPORT.html"

MODEL_PATH = SAVED_MODELS_DIR / "ppo_dispatch.zip"
BC_POLICY_PATH = SAVED_MODELS_DIR / "bc_init.pt"

# 학습 하이퍼파라미터
DEFAULT_PPO_STEPS = 50_000
BC_EPOCHS = 300
BC_LR = 1e-3
DEFAULT_SWITCH_TIME_HOURS = 1

# --- DB 테이블 (INF=현행, HIS=이력) ---
INPUT_TABLE = "RTS_LINEDSDB_INF"

# 시간대별 계획/달성 (task × hour)
PLAN_ACHV_TABLE = "RTS_PLAN_ACHV_INF"
PLAN_ACHV_HIS_TABLE = "RTS_PLAN_ACHV_HIS"

# 장비 배치·생산 (eqp × hour)
ASSIGN_TABLE = "RTS_ASSIGN_INF"
ASSIGN_HIS_TABLE = "RTS_ASSIGN_HIS"

# batch(tool) 전환 이벤트
CONV_TABLE = "RTS_CONV_INF"
CONV_HIS_TABLE = "RTS_CONV_HIS"

# db.write_assign_results 하위호환 alias
RESULT_TABLE = ASSIGN_TABLE
RESULT_HIS_TABLE = ASSIGN_HIS_TABLE


def _build_dsn() -> str:
    """ORACLE_DSN이 있으면 그대로 사용.

    없으면 ORACLE_HOST1(/ORACLE_HOST2)·ORACLE_PORT·ORACLE_SERVICE로
    TNS connect descriptor를 조립한다 (HOST2 지정 시 ADDRESS_LIST 페일오버).
    """
    dsn = os.getenv("ORACLE_DSN")
    if dsn:
        return dsn

    host1 = os.getenv("ORACLE_HOST1")
    if not host1:
        return "localhost:1521/XEPDB1"

    port = os.getenv("ORACLE_PORT", "1521")
    service = os.getenv("ORACLE_SERVICE", "XEPDB1")
    host2 = os.getenv("ORACLE_HOST2")

    addresses = f"(ADDRESS=(PROTOCOL=TCP)(HOST={host1})(PORT={port}))"
    if host2:
        addresses += f"(ADDRESS=(PROTOCOL=TCP)(HOST={host2})(PORT={port}))"
    return (
        f"(DESCRIPTION=(ADDRESS_LIST={addresses})"
        f"(CONNECT_DATA=(SERVICE_NAME={service})))"
    )


def load_config() -> dict:
    """.env(있으면)와 환경변수에서 DB 설정을 읽는다."""
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except Exception:
        pass
    return {
        "user": os.getenv("ORACLE_USER", "dispatcher"),
        "password": os.getenv("ORACLE_PASSWORD", "dispatcher"),
        "dsn": _build_dsn(),
        "crt_user_id": os.getenv("RTS_CRT_USER_ID", "RL_AGENT"),
    }
