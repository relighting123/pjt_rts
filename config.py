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

# 출력 테이블 (db.py)
RESULT_TABLE = "RTS_RSLT_MAS"
RESULT_HIS_TABLE = "RTS_RSLT_HIS"
CONV_TABLE = "RTS_CONV_INF"
CONV_HIS_TABLE = "RTS_CONV_HIS"


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
        "dsn": os.getenv("ORACLE_DSN", "localhost:1521/XEPDB1"),
        "crt_user_id": os.getenv("RTS_CRT_USER_ID", "RL_AGENT"),
    }
