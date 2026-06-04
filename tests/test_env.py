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
