"""AllocationEnv PPO 학습."""
from __future__ import annotations

import random
from pathlib import Path

import numpy as np
import stable_baselines3 as sb3
import torch
from stable_baselines3.common.vec_env import DummyVecEnv

import config
from src.simulation.domain.problem import ProblemInstance
from src.training.callbacks import ConvergenceLogger
from src.training.log_io import append_training_point, reset_training_log
from envs.allocation_env import AllocationEnv


def _analytic_target_logits(env: AllocationEnv) -> np.ndarray:
    p = env.p
    analytic = p.plan_target_allocation()
    logits = np.full((env.mm * env.mt,), -3.0, dtype=np.float32)
    eps = 1e-6
    for mi, model in enumerate(env.models):
        eqp = max(1.0, float(p.eqp_qty[model]))
        for ti in range(env.n_tasks):
            if p.uph_of(model, ti) is None:
                continue
            frac = analytic.get((model, ti), 0.0) / eqp
            logits[mi * env.mt + ti] = float(np.clip(np.log(frac + eps) + 3.0, -3.0, 3.0))
    return logits


def behavior_clone_alloc(model, problems, epochs: int, lr: float):
    if epochs <= 0 or not problems:
        return
    obs_list, tgt_list, mask_list = [], [], []
    for p in problems:
        env = AllocationEnv(p, max_tasks=config.MAX_TASKS, max_models=config.MAX_MODELS)
        obs, _ = env.reset()
        obs_list.append(obs)
        tgt_list.append(_analytic_target_logits(env))
        mask = np.zeros((env.mm * env.mt,), dtype=np.float32)
        for mi, m in enumerate(env.models):
            for ti in range(env.n_tasks):
                if env.p.uph_of(m, ti) is not None:
                    mask[mi * env.mt + ti] = 1.0
        mask_list.append(mask)
    obs_t = torch.as_tensor(np.asarray(obs_list), dtype=torch.float32)
    tgt_t = torch.as_tensor(np.asarray(tgt_list), dtype=torch.float32)
    mask_t = torch.as_tensor(np.asarray(mask_list), dtype=torch.float32)
    policy = model.policy
    policy.set_training_mode(True)
    opt = torch.optim.Adam(policy.parameters(), lr=lr)
    for _ in range(epochs):
        opt.zero_grad()
        dist = policy.get_distribution(obs_t)
        mean = dist.distribution.mean
        sq = (mean - tgt_t) ** 2 * mask_t
        loss = sq.sum() / mask_t.sum().clamp(min=1.0)
        loss.backward()
        opt.step()
        if (_ + 1) % max(1, epochs // 10) == 0 or _ == 0:
            append_training_point("alloc", {
                "phase": "bc",
                "timesteps": _ + 1,
                "mean_reward": round(-float(loss.item()), 6),
                "loss": round(float(loss.item()), 6),
            })
    policy.set_training_mode(False)


def train_alloc_model(problems: list[ProblemInstance], ppo_steps: int = 5000,
                      bc_epochs: int = config.BC_EPOCHS, lr: float = config.BC_LR,
                      save_path: Path | None = None):
    save_path = Path(save_path) if save_path else (config.SAVED_MODELS_DIR / "ppo_alloc.zip")
    save_path.parent.mkdir(parents=True, exist_ok=True)

    def _shape(p):
        e = AllocationEnv(p, max_tasks=config.MAX_TASKS, max_models=config.MAX_MODELS)
        return (tuple(e.observation_space.shape), tuple(e.action_space.shape))
    base = _shape(problems[0])
    same = [p for p in problems if _shape(p) == base]

    def _vec_env():
        return DummyVecEnv([lambda: AllocationEnv(random.choice(same), max_tasks=config.MAX_TASKS,
                                                     max_models=config.MAX_MODELS)])

    reset_training_log("alloc")
    model = sb3.PPO("MlpPolicy", _vec_env(), verbose=0, n_steps=64, batch_size=32)
    behavior_clone_alloc(model, same, bc_epochs, lr)
    model.set_env(_vec_env())
    model.learn(
        total_timesteps=ppo_steps,
        progress_bar=False,
        callback=ConvergenceLogger("alloc"),
    )
    model.save(save_path)
    return model
