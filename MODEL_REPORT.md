# 모델 평가 리포트 (기록용)

- 평균 계획달성률 — 최적: 0.795 / 휴리스틱: 0.795 / RL: 0.224

| 벤치마크 | 최적 | 휴리스틱 | RL |
|---|---|---|---|
| benchmark_01 | 1.000 | 1.000 | 1.000 |
| benchmark_02 | 1.000 | 1.000 | 0.000 |
| benchmark_03 | 1.000 | 1.000 | 0.000 |
| benchmark_04 | 1.000 | 1.000 | 0.000 |
| benchmark_05 | 0.400 | 0.400 | 0.400 |
| benchmark_06 | 0.167 | 0.167 | 0.167 |
| benchmark_07 | 1.000 | 1.000 | 0.000 |

## benchmark_01
- 비고: 1대 x 100UPH x 3h = 300 = plan, 전환 없음
```
간트 (model x hour → task)
      M1 | P1     | P1     | P1    
```

## benchmark_02
- 비고: PA 2h(200) → 전환 1h Idle → PB 1h(100). 총 4h.
```
간트 (model x hour → task)
      M1 | PA     | PA     | PB     | PB    
```

## benchmark_03
- 비고: OP10 2대 1h로 200 생산→OP20 WIP 확보. OP20(B2)로 전환해 후공정 달성. OP20 init_wip=0이라 앞공정 빌드 필수.
```
간트 (model x hour → task)
      M1 | P1     | P1     | P1     | P1    
```

## benchmark_04
- 비고: 같은 batch라 전환 무비용. M_FAST를 P1(150x2h=300)에, M_SLOW를 P2(50x2h=100)에 두면 둘 다 100%. 초기 배치는 반대라 교체 필요.
```
간트 (model x hour → task)
  M_FAST | P1     | P1    
  M_SLOW | P2     | P2    
```

## benchmark_05
- 비고: 최대 2대x100x2h=400 vs 계획 1000 → 0.4 상한.
```
간트 (model x hour → task)
      M1 | P1     | P1    
```

## benchmark_06
- 비고: WIP 50개 한계 → 50/300=0.1667.
```
간트 (model x hour → task)
      M1 | P1     | P1     | P1    
```

## benchmark_07
- 비고: PA 1h(100)→전환1h→PB 1h(100): 3h, 1회 전환으로 둘 다 100%.
```
간트 (model x hour → task)
      M1 | PA     | PB     | PB     | PB    
```
