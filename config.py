"""전역 설정과 .env 로더."""
from __future__ import annotations
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
API_PORT = int(os.getenv("API_PORT", "7000"))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

DATA_DIR = ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
TRAIN_DATA_DIR = RAW_DATA_DIR / "train"
TEST_DATA_DIR = RAW_DATA_DIR / "test"
INFERENCE_INPUT_DIR = RAW_DATA_DIR / "inference"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
INFERENCE_RESULT_DIR = PROCESSED_DATA_DIR / "inference"
INFERENCE_DATA_DIR = INFERENCE_INPUT_DIR
TRAIN_DB_EXPORT_DIR = TRAIN_DATA_DIR
DEFAULT_TRAIN_LOOKBACK_DAYS = int(os.getenv("TRAIN_LOOKBACK_DAYS", "30"))
DEFAULT_FACID = os.getenv("DEFAULT_FACID") or os.getenv("DEFAULT_FAC_ID") or None


def resolve_facid(facid: str | None = None) -> str | None:
    if facid:
        return facid
    return DEFAULT_FACID


def require_facid(facid: str | None = None) -> str:
    fac = resolve_facid(facid)
    if not fac:
        raise ValueError("facid 필수입니다. --facid 지정 또는 .env에 DEFAULT_FACID 설정")
    return fac


DEFAULT_BATCHID = os.getenv("DEFAULT_BATCHID") or None


def resolve_batchid(batchid: str | None = None) -> str | None:
    if batchid:
        return batchid
    return DEFAULT_BATCHID


def require_batchid(batchid: str | None = None) -> str:
    bid = resolve_batchid(batchid)
    if not bid:
        raise ValueError("batchid 필수입니다. --batchid 지정 또는 .env에 DEFAULT_BATCHID 설정")
    return bid


def replace_file(path: str | Path) -> Path:
    p = Path(path)
    if p.is_file():
        p.unlink()
    return p


BENCHMARKS_DIR = TEST_DATA_DIR
BENCHMARKS_TRAIN_DIR = TRAIN_DATA_DIR
CHECKPOINTS_DIR = ROOT / "models" / "checkpoints"
BEST_MODEL_DIR = ROOT / "models" / "best"
MODELS_DIR = ROOT / "models"
SAVED_MODELS_DIR = CHECKPOINTS_DIR
LOGS_DIR = ROOT / "logs"
TENSORBOARD_DIR = LOGS_DIR / "tensorboard"
OUTPUTS_DIR = ROOT / "outputs"
ARTIFACTS_DIR = OUTPUTS_DIR / "results"

MODEL_PATH = CHECKPOINTS_DIR / "ppo_dispatch.zip"
BC_POLICY_PATH = CHECKPOINTS_DIR / "bc_init.pt"

DEFAULT_PPO_STEPS = 50_000
BC_EPOCHS = 300
BC_LR = 1e-3
BC_LOSS_TARGET = 0.05
DEFAULT_SWITCH_TIME_HOURS = 1

MAX_TASKS = 8
MAX_MODELS = 5
CONV_GROUPS: dict[str, list[str]] = {"G1": ["B1", "B2", "B3"]}
SYS_ID = "RL_AGENT"


def load_conv_groups() -> dict[str, list[str]]:
    return {k: list(v) for k, v in CONV_GROUPS.items()}


resolve_conv_groups = load_conv_groups

DWELL_LAMBDA = float(os.getenv("DWELL_LAMBDA", "0.3"))
ALLOC_LAMBDA = float(os.getenv("ALLOC_LAMBDA", "0.3"))
DWELL_OBS = os.getenv("DWELL_OBS", "true").lower() == "true"
USE_ALLOC_MODEL = os.getenv("USE_ALLOC_MODEL", "true").lower() == "true"
GUIDE_UTIL_THRESHOLD = float(os.getenv("GUIDE_UTIL_THRESHOLD", "0.70"))
GUIDE_BAND_PCT = float(os.getenv("GUIDE_BAND_PCT", "0.20"))

INPUT_TABLE = "RTS_LINEDSDB_INF"
EQPALLOCATION_TABLE = "RTS_EQPALLOCATION_INF"
EQPALLOCATION_HIS_TABLE = "RTS_EQPALLOCATION_HIS"
GUIDE_TABLE = EQPALLOCATION_TABLE
GUIDE_HIS_TABLE = EQPALLOCATION_HIS_TABLE
ASSIGN_TABLE = "RTS_ASSIGN_INF"
ASSIGN_HIS_TABLE = "RTS_ASSIGN_HIS"
EQPCONVPLAN_TABLE = "RTS_EQPCONVPLAN_INF"
EQPCONVPLAN_HIS_TABLE = "RTS_EQPCONVPLAN_HIS"
CONV_TABLE = EQPCONVPLAN_TABLE
CONV_HIS_TABLE = EQPCONVPLAN_HIS_TABLE
RESULT_TABLE = ASSIGN_TABLE
RESULT_HIS_TABLE = ASSIGN_HIS_TABLE


def _build_dsn() -> str:
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
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except Exception:
        pass
    return {
        "user": os.getenv("ORACLE_USER", "dispatcher"),
        "password": os.getenv("ORACLE_PASSWORD", "dispatcher"),
        "dsn": _build_dsn(),
        "sys_id": SYS_ID,
    }
