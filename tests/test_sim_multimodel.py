from simulator import Task, ProblemInstance, Simulator
import config


def _two_model_one_task() -> ProblemInstance:
    """단일 태스크에 두 모델(M_A 60UPH, M_B 40UPH)이 함께 배치된 인스턴스."""
    tasks = [Task("P1", "OP10", 1, "B1", 1000, 1000)]
    return ProblemInstance(
        rule_timekey="T", horizon_hours=2, switch_time_hours=1, tasks=tasks,
        _uph={("M_A", 0): 60.0, ("M_B", 0): 40.0},
        eqp_qty={"M_A": 1, "M_B": 1},
        init_assign={("M_A", 0): 1, ("M_B", 0): 1},
        tool_qty={("B1", "M_A"): 1, ("B1", "M_B"): 1},
        conv_groups=config.load_conv_groups(),
    )


def test_two_models_capacity_sums_on_same_task():
    sim = Simulator(_two_model_one_task())
    s = sim.reset()
    sim.advance_hour(s)
    # 60 + 40 = 100/hour
    assert s.produced[0] == 100
    sim.advance_hour(s)
    assert s.produced[0] == 200
