from simulator import load_problem, Simulator, Move
from config import BENCHMARKS_DIR


def test_cross_batch_move_costs_idle_and_swaps_tool():
    p = load_problem(BENCHMARKS_DIR / "benchmark_02.json")
    sim = Simulator(p)
    s = sim.reset()
    # 초기: M1 1대가 task0(PA,B1)
    assert s.assign[("M1", 0)] == 1
    assert s.tool_used[("B1", "M1")] == 1
    sim.apply_move(s, Move("M1", 0, 1))  # PA(B1) -> PB(B2)
    assert s.assign.get(("M1", 0), 0) == 0
    assert s.assign[("M1", 1)] == 1
    assert s.idle[("M1", 1)] == 1                 # 전환 1시간 Idle
    assert s.tool_used.get(("B1", "M1"), 0) == 0  # from tool 반환
    assert s.tool_used[("B2", "M1")] == 1         # to tool 소진
    # 전환 직후 1시간은 Idle → 생산 0
    sim.advance_hour(s)
    assert s.produced[1] == 0


def test_valid_moves_masks_tool_shortage_and_out_of_group():
    p = load_problem(BENCHMARKS_DIR / "benchmark_02.json")
    sim = Simulator(p)
    s = sim.reset()
    moves = sim.valid_moves(s)
    # B1->B2 같은 그룹 + tool 여유 → 가능
    assert Move("M1", 0, 1) in moves
    # to-batch tool을 모두 소진시키면 더 이상 전환 불가
    s.tool_used[("B2", "M1")] = 1
    moves2 = sim.valid_moves(s)
    assert Move("M1", 0, 1) not in moves2


def test_same_batch_move_is_free_no_idle():
    # 같은 batch 내 다른 task로의 이동은 tool 변화/Idle 없음
    p = load_problem(BENCHMARKS_DIR / "benchmark_02.json")
    # task1의 batch를 B1로 바꿔 같은 batch 시나리오 구성
    p.tasks[1] = p.tasks[1].__class__("PB", "OP10", 1, "B1", 100, 1000)
    p._uph[("M1", 1)] = 100.0
    sim = Simulator(p)
    s = sim.reset()
    sim.apply_move(s, Move("M1", 0, 1))
    assert ("M1", 1) not in s.idle           # Idle 없음
    assert s.tool_used.get(("B1", "M1")) == 1  # 같은 batch → tool 수 불변
