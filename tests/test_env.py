import numpy as np
from simulator import load_problem
from env import DispatchEnv
from config import BENCHMARKS_DIR


def test_env_reset_obs_shape_and_mask():
    p = load_problem(BENCHMARKS_DIR / "benchmark_02.json")
    env = DispatchEnv(p)
    obs, info = env.reset(seed=0)
    assert obs.shape == (env.observation_space.shape[0],)
    mask = env.action_masks()
    assert mask.shape == (env.action_space.n,)
    assert mask[0] == True   # commit은 항상 가능


def test_env_commit_advances_hour_and_terminates():
    p = load_problem(BENCHMARKS_DIR / "benchmark_01.json")
    env = DispatchEnv(p)
    env.reset(seed=0)
    done = False
    steps = 0
    total_r = 0.0
    while not done and steps < 100:
        obs, r, term, trunc, info = env.step(0)  # 매번 commit
        total_r += r
        done = term or trunc
        steps += 1
    assert done
    assert info["plan_achievement"] == 1.0  # bench01은 그냥 두면 100%


def test_env_masks_invalid_moves_match_simulator():
    p = load_problem(BENCHMARKS_DIR / "benchmark_02.json")
    env = DispatchEnv(p)
    env.reset(seed=0)
    mask = env.action_masks()
    # 유효 이동 수 + 1(commit) == 마스크 True 개수
    from simulator import Simulator
    sim = Simulator(p)
    s = sim.reset()
    assert mask.sum() == len(sim.valid_moves(s)) + 1


def _env_with_guide(util_threshold, band):
    from env import DispatchEnv
    p = load_problem(BENCHMARKS_DIR / "benchmark_02.json")
    models = p.models()
    target = {(models[0], 0): float(p.eqp_qty[models[0]])}
    env = DispatchEnv(
        p, alloc_lambda=1.0, target_allocation=target,
        guide_util_threshold=util_threshold, guide_band_pct=band,
    )
    env.reset(seed=0)
    return env


def test_guide_reward_zero_when_util_below_threshold():
    env = _env_with_guide(util_threshold=1.1, band=0.2)
    assert env._alloc_guide_reward() == 0.0


def test_guide_reward_skips_zero_wip_tasks():
    env = _env_with_guide(util_threshold=0.0, band=0.0)
    s = env._state
    for i in range(len(env.p.tasks)):
        s.wip[i] = 0
    assert env._alloc_guide_reward() == 0.0


def test_guide_reward_band_tolerates_small_deviation():
    p = load_problem(BENCHMARKS_DIR / "benchmark_02.json")
    from env import DispatchEnv
    target = {(m, ti): float(c) for (m, ti), c in p.init_assign.items()}
    env = DispatchEnv(
        p, alloc_lambda=1.0, target_allocation=target,
        guide_util_threshold=0.0, guide_band_pct=0.20,
    )
    env.reset(seed=0)
    assert abs(env._alloc_guide_reward() - 1.0) < 1e-9
