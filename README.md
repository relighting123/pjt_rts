# Equipment Dispatch RL

장비 배치/전환 스케줄링을 강화학습(PPO) + 휴리스틱으로 수행하는 프로젝트입니다.
입력 데이터(JSON 또는 Oracle)로 시뮬레이션을 실행하고, 계획달성률/가동률/전환 정보를 API와 UI로 확인할 수 있습니다.

## 프로젝트 구조

```text
pjt_rts/
├── configs/                  # train.yaml, eval.yaml
├── data/
│   ├── raw/
│   │   ├── test/             # 벤치마크 입력
│   │   ├── train/            # 학습 입력
│   │   └── inference/        # 추론 입력
│   └── processed/
│       └── inference/        # 추론 결과 JSON
├── envs/                     # Gym env (dispatch/allocation)
├── agents/                   # 정책/모델 로딩/registry
├── models/
│   ├── checkpoints/          # ppo_dispatch.zip, ppo_alloc.zip
│   └── best/
├── logs/
│   └── tensorboard/
├── src/
│   ├── simulation/           # domain + simulator kernel
│   ├── stages/               # allocation/dispatch use-case
│   ├── training/             # BC + PPO 학습 로직
│   ├── db/                   # Oracle adapter + SQL + pipeline
│   ├── api/                  # FastAPI
│   ├── views/                # API view-model (gantt/pivot)
│   ├── utils/                # json_io / eqp_units / ops_log / rows
│   ├── train.py              # 학습 파이프라인
│   ├── evaluate.py           # 평가 파이프라인
│   ├── inference.py          # 추론 파이프라인 래퍼
│   └── export.py             # export 래퍼
├── web/                      # React 대시보드
├── tests/
├── main.py                   # CLI 진입점
└── requirements.txt
```

## 설치

```bash
pip install -r requirements.txt
cd web && npm install
```

## 실행

### 1) API + UI 개발 모드

```bash
# 터미널 1: API
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

# 터미널 2: UI
cd web && npm run dev
```

- UI: `http://localhost:5173`
- API: `http://localhost:8000/api/health`

### 2) 운영 빌드 실행

```bash
cd web && npm run build
uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

## CLI 사용법

```bash
python main.py --help
```

### 평가

```bash
python main.py eval
python main.py eval --no-model
```

### 학습

```bash
python main.py train --steps 50000
python main.py train --benchmark-dataset data/raw/test/benchmark_03.json --steps 50000
```

### 추론 (로컬 JSON)

```bash
python main.py infer --benchmark-dataset data/raw/test/benchmark_01.json
```

### 추론 (DB)

```bash
python main.py infer --timekey 2026052922500000 --facid ICPRB --batchid B1
python main.py infer --facid ICPRB --batchid B1   # timekey 미지정 시 MAX(RULE_TIMEKEY)
```

### 입력 JSON export (DB -> 파일)

```bash
python main.py export --timekey 2026052922500000 --facid ICPRB --batchid B1
python main.py export --train --from-timekey 2026050100000000 --to-timekey 2026053123595900 --facid ICPRB --batchid B1
```

## API 엔드포인트

- `GET /api/health` : 헬스체크
- `GET /api/datasets` : 분석 가능한 데이터셋 목록
- `GET /api/datasets/{name}` : 데이터셋 상세 분석 결과
- `GET /api/summary` : 전체 데이터셋 요약

## 설정

- 런타임 설정: `config.py`
- 환경변수: `.env` (Oracle 연결 정보, 기본 FAC/BATCH 등)

주요 설정 항목:
- `MAX_TASKS`, `MAX_MODELS`
- `DWELL_LAMBDA`, `ALLOC_LAMBDA`
- `USE_ALLOC_MODEL`
- `GUIDE_UTIL_THRESHOLD`, `GUIDE_BAND_PCT`

## 테스트

```bash
python -m pytest -q
```

---

상세 아키텍처 설명은 `docs/ARCHITECTURE.md`를 참고하세요.
