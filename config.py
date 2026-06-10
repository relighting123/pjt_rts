"""전역 설정과 .env 로더."""
from __future__ import annotations
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
TRAIN_DATA_DIR = DATA_DIR / "train"
TEST_DATA_DIR = DATA_DIR / "test"
INFERENCE_DATA_DIR = DATA_DIR / "inference"
# 입력 {RULE_TIMEKEY}.json · 결과 {RULE_TIMEKEY}_result.json — 동일 디렉터리
INFERENCE_INPUT_DIR = INFERENCE_DATA_DIR
INFERENCE_RESULT_DIR = INFERENCE_DATA_DIR
TRAIN_DB_EXPORT_DIR = TRAIN_DATA_DIR  # 하위호환 alias (from_db 제거)
DEFAULT_TRAIN_LOOKBACK_DAYS = int(os.getenv("TRAIN_LOOKBACK_DAYS", "30"))
# DB SELECT 시 facid 필수 (--facid 또는 .env DEFAULT_FACID)
DEFAULT_FACID = os.getenv("DEFAULT_FACID") or os.getenv("DEFAULT_FAC_ID") or None


def resolve_facid(facid: str | None = None) -> str | None:
    """CLI --facid > 인자 facid > .env DEFAULT_FACID."""
    if facid:
        return facid
    return DEFAULT_FACID


def require_facid(facid: str | None = None) -> str:
    """DB 조회용 facid. 미지정 시 ValueError."""
    fac = resolve_facid(facid)
    if not fac:
        raise ValueError(
            "facid 필수입니다. --facid 지정 또는 .env에 DEFAULT_FACID 설정"
        )
    return fac


# DB SELECT 시 batchid 필수 (--batchid 또는 .env DEFAULT_BATCHID, LIKE %값%)
DEFAULT_BATCHID = os.getenv("DEFAULT_BATCHID") or None


def resolve_batchid(batchid: str | None = None) -> str | None:
    """CLI --batchid > 인자 batchid > .env DEFAULT_BATCHID."""
    if batchid:
        return batchid
    return DEFAULT_BATCHID


def require_batchid(batchid: str | None = None) -> str:
    """DB 조회용 batchid. 미지정 시 ValueError."""
    bid = resolve_batchid(batchid)
    if not bid:
        raise ValueError(
            "batchid 필수입니다. --batchid 지정 또는 .env에 DEFAULT_BATCHID 설정"
        )
    return bid


def replace_file(path: str | Path) -> Path:
    """동일 경로 파일이 있으면 삭제 후 새로 쓸 수 있게 한다."""
    p = Path(path)
    if p.is_file():
        p.unlink()
    return p
# 하위호환 alias
BENCHMARKS_DIR = TEST_DATA_DIR
BENCHMARKS_TRAIN_DIR = TRAIN_DATA_DIR
SAVED_MODELS_DIR = ROOT / "saved_models"
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

# RL obs/action 패딩 상한 · batch(tool) 전환 그룹 — 여기서만 수정
MAX_TASKS = 30
MAX_MODELS = 20
CONV_GROUPS: dict[str, list[str]] = {"G1": ["B1", "B2", "B3"]}
SYS_ID = "RL_AGENT"


def load_conv_groups() -> dict[str, list[str]]:
    """CONV_GROUPS 설정값 반환 (호출마다 복사본)."""
    return {k: list(v) for k, v in CONV_GROUPS.items()}


# 하위호환 alias
resolve_conv_groups = load_conv_groups

# WIP 체류시간 성형 계수 (0.0 = 비활성)
DWELL_LAMBDA = float(os.getenv("DWELL_LAMBDA", "0.3"))
# 목표 배분 가이드 계수 (0.0 = 비활성)
ALLOC_LAMBDA = float(os.getenv("ALLOC_LAMBDA", "0.3"))
# True면 obs에 dwell 슬롯 추가 (차원 변경 → 기존 모델과 비호환)
DWELL_OBS = os.getenv("DWELL_OBS", "true").lower() == "true"
# True면 AllocationEnv 상위 모델을 사용해 target_allocation 주입
USE_ALLOC_MODEL = os.getenv("USE_ALLOC_MODEL", "true").lower() == "true"
# 가이드 준수: 이 가동률 이상에서만 적용
GUIDE_UTIL_THRESHOLD = float(os.getenv("GUIDE_UTIL_THRESHOLD", "0.70"))
# 가이드 대비 허용 상·하단 비율 (±%). 밴드 안이면 페널티 0
GUIDE_BAND_PCT = float(os.getenv("GUIDE_BAND_PCT", "0.20"))

# --- DB 테이블 (INF=현행, HIS=이력) ---
# 입력
INPUT_TABLE = "RTS_LINEDSDB_INF"
# 장비 호기 현재 배치 명단 (EQP_ID/EQP_MODEL_CD/BATCH_ID/PLAN_PROD_KEY)
ARRANGE_TABLE = "RTD_ARRANGE_INF"

# 출력 4종 — 스키마·JSON 매핑: db/sql/reference/00_output_tables.md
# Mode 1: 가이드 배분 (공정×모델)
EQPALLOCATION_TABLE = "RTS_EQPALLOCATION_INF"
EQPALLOCATION_HIS_TABLE = "RTS_EQPALLOCATION_HIS"
GUIDE_TABLE = EQPALLOCATION_TABLE          # 하위호환 alias
GUIDE_HIS_TABLE = EQPALLOCATION_HIS_TABLE

# Mode 2: 동적 시뮬 결과
ASSIGN_TABLE = "RTS_ASSIGN_INF"
ASSIGN_HIS_TABLE = "RTS_ASSIGN_HIS"
EQPCONVPLAN_TABLE = "RTS_EQPCONVPLAN_INF"
EQPCONVPLAN_HIS_TABLE = "RTS_EQPCONVPLAN_HIS"
CONV_TABLE = EQPCONVPLAN_TABLE           # 하위호환 alias
CONV_HIS_TABLE = EQPCONVPLAN_HIS_TABLE
RESULT_TABLE = ASSIGN_TABLE              # 하위호환 alias
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
        "sys_id": SYS_ID,
    }
