# DBR 제조 스케줄러 시뮬레이터

**DBR(Drum-Buffer-Rope)** 이론에 기반한 Python 제조 시뮬레이션 엔진입니다. 생산 흐름을 최적화하고 병목 현상을 관리하며, 일정하게 유지되는 생산 맥박(**Takt Time**)을 유지하도록 설계되었습니다.

## 🚀 주요 특징

- **모듈형 아키텍처**: 시뮬레이션 엔진(`simulator.py`)과 스케줄링 로직(`scheduler.py`)의 완전한 분리.
- **DBR 이론 구현**:
  - **Drum**: 자원 부하를 기반으로 병목 공정 자동 식별.
  - **Buffer**: 병목 현상의 가동 중단(Starvation)을 방지하기 위한 WIP 보호.
  - **Rope**: 병목 공정의 속도에 맞춘 자재 투입 제어.
- **Takt 기반 평준화**: 22시간 내에 일정한 속도로 생산되도록 제어하는 스마트 게이팅 메커니즘을 통해 과도한 WIP를 방지합니다.
- **설비 교체(Changeover) 관리**: 제품/공정 조합 간의 복잡한 설정 규칙 처리.
- **상세 리포팅**: 실시간 장비 할당 로그, CAPA 계산 및 최종 성과 지표(달성률, 가동률, 교체 횟수) 제공.

## 📁 프로젝트 구조

```text
├── data/
│   ├── equipment_inventory.json   # 모델별 장비 대수
│   ├── equipment_capability.json  # 공정 가능 여부 및 표준 시간(ST)
│   ├── plan_wip.json              # 생산 목표 및 초기 재공(WIP)
│   └── changeover_rules.json      # 설비 교체 규칙
├── docs/                          # 상세 문서 및 분석 자료 (한글)
├── scheduler.py                   # DBR 스케줄링 로직
├── simulator.py                   # 시간 단위 시뮬레이션 엔진
└── README.md                      # 프로젝트 개요
```

## 🛠️ 실행 방법

1. **사전 요구 사항**: Python 3.8 이상 (외부 라이브러리 의존성 없음).
2. **시뮬레이션 실행**:
   ```bash
   python simulator.py
   ```

## 📊 출력 예시

```text
==================== DBR Simulation Started ====================
time   | product    | process    | target(achieved) | wip    | capa
-------------------------------------------------------------------
0      | Fast_A     | Step_10    | 0                | 36     | 1.0
...
[Terminated] All final production targets met at 1390 minutes.

=== 최종 결과 요약 ===
전체 제품 달성률: 100.00%
설비 가동률:       38.85%
총 설비 교체 횟수:  54
```

## 🧠 핵심 로직: Takt 기반 밸런싱

시뮬레이터는 스케줄러 내에서 **Takt Gate**를 사용합니다:
- 목표 심장박동 계산: `마감 기한(1320분) / 목표 수량`.
- 이 주기에 맞춰 누적 생산 시작 대수를 제한합니다.
- 이를 통해 JIT(Just-In-Time) 환경에 최적화된 저재공(Low-WIP) 평준화 흐름을 실현합니다.
