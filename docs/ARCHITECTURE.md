# RTS 아키텍처 (RL 프로젝트 레이아웃)

```
pjt_rts/
├── configs/           train.yaml, eval.yaml
├── data/
│   ├── raw/           test, train, inference 입력 JSON
│   └── processed/     inference 결과 JSON
├── envs/              Gym 환경 (DispatchEnv, AllocationEnv)
├── agents/            정책 (heuristic, PPO dispatch, registry)
├── models/
│   ├── checkpoints/   ppo_dispatch.zip, ppo_alloc.zip
│   └── best/
├── logs/tensorboard/
├── src/
│   ├── simulation/    domain + kernel (시뮬레이터)
│   ├── stages/        allocation / dispatch use-case
│   ├── training/      BC + PPO 학습
│   ├── evaluate.py    벤치마크 평가
│   ├── train.py       학습 파이프라인
│   ├── play.py        추론 (DB infer)
│   ├── rows.py        Oracle 출력 행 / 추론 JSON
│   ├── views.py       API view-model (간트, 피벗)
│   ├── db/            Oracle, SQL, pipeline
│   └── api/           FastAPI + 대시보드 API
├── web/               React UI
├── tests/
├── outputs/           charts, results
├── main.py            CLI (train / eval / infer / export)
└── requirements.txt
```

## 실행

```bash
python main.py train
python main.py eval
python main.py infer --dataset benchmark_01
uvicorn src.api.main:app --host 0.0.0.0 --port 7000
```

## 레이어 규칙

- `simulation/domain` → RL·DB·API import 금지
- `simulation/kernel` → agents·training import 금지

검증: `tests/test_import_layers.py`
