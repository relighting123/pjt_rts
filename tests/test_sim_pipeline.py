from simulator import Task, ProblemInstance, Simulator


def _three_oper_chain() -> ProblemInstance:
    """P1의 OP10→OP20→OP30 체인. 각 1대 100UPH, 같은 batch B1(무비용).

    OP10만 초기 재공 보유. 생산분이 한 시간씩 뒤로 흘러야 한다.
    """
    tasks = [
        Task("P1", "OP10", 1, "B1", 100, 100),
        Task("P1", "OP20", 2, "B1", 100, 0),
        Task("P1", "OP30", 3, "B1", 100, 0),
    ]
    return ProblemInstance(
        rule_timekey="T", horizon_hours=5, switch_time_hours=1, tasks=tasks,
        _uph={("M1", 0): 100.0, ("M1", 1): 100.0, ("M1", 2): 100.0},
        eqp_qty={"M1": 3},
        init_assign={("M1", 0): 1, ("M1", 1): 1, ("M1", 2): 1},
        tool_qty={("B1", "M1"): 3},
        conv_groups={"G1": ["B1"]},
    )


def test_wip_flows_one_oper_per_hour():
    sim = Simulator(_three_oper_chain())
    s = sim.reset()
    # 정적 배치(이동 없음)로 시간만 흘린다.
    sim.advance_hour(s)   # h1: OP10 100 생산, OP20/30은 재공 0 → 0
    assert (s.produced[0], s.produced[1], s.produced[2]) == (100, 0, 0)
    sim.advance_hour(s)   # h2: OP20가 h1 유입분(100) 처리 → 100
    assert (s.produced[0], s.produced[1], s.produced[2]) == (100, 100, 0)
    sim.advance_hour(s)   # h3: OP30가 h2 유입분(100) 처리 → 100
    assert (s.produced[0], s.produced[1], s.produced[2]) == (100, 100, 100)
