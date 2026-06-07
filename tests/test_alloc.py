from pathlib import Path
from simulator import load_problem
from config import BENCHMARKS_DIR
import train


def test_train_alloc_model_saves_and_respects_caps(tmp_path):
    p = load_problem(BENCHMARKS_DIR / "benchmark_02.json")
    out = tmp_path / "ppo_alloc.zip"
    model = train.train_alloc_model([p], ppo_steps=200, bc_epochs=5, save_path=out)
    assert out.exists()

    from alloc_env import AllocationEnv
    import config as cfg
    env = AllocationEnv(p, max_tasks=cfg.MAX_TASKS, max_models=cfg.MAX_MODELS)
    obs, _ = env.reset()
    action, _ = model.predict(obs, deterministic=True)
    env.step(action)
    alloc = env.get_allocation()
    per_model = {}
    for (m, ti), c in alloc.items():
        per_model[m] = per_model.get(m, 0) + c
    for m, total in per_model.items():
        assert total == p.eqp_qty[m]
