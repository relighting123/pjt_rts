"""DispatchEnv MaskablePPO 학습."""
from __future__ import annotations

import copy
import logging
import random
from pathlib import Path

import numpy as np
import torch
from sb3_contrib import MaskablePPO
from sb3_contrib.common.wrappers import ActionMasker
from stable_baselines3.common.vec_env import DummyVecEnv

import config
from src.simulation.domain.problem import ProblemInstance
from src.simulation.kernel.simulator import Simulator
from agents.heuristic import heuristic_actions
from envs.dispatch_env import DispatchEnv
from src.training.allocation import train_alloc_model
from src.training.callbacks import ConvergenceLogger
from src.training.log_io import append_training_point, reset_training_log
from src.stages.allocation.use_case import allocate

log = logging.getLogger(__name__)


def _mask_fn(env) -> np.ndarray:
    return env.action_masks()


def _get_target_allocation(problem: ProblemInstance) -> dict:
    if config.USE_ALLOC_MODEL and config.ALLOC_LAMBDA > 0.0:
        alloc_model_path = config.SAVED_MODELS_DIR / "ppo_alloc.zip"
        if alloc_model_path.exists():
            from agents.model_store import load_alloc_model
            alloc_model = load_alloc_model(alloc_model_path)
            if alloc_model is not None:
                from envs.allocation_env import AllocationEnv
                alloc_env = AllocationEnv(problem, max_tasks=config.MAX_TASKS,
                                          max_models=config.MAX_MODELS)
                obs, _ = alloc_env.reset()
                action, _ = alloc_model.predict(obs, deterministic=True)
                alloc_env.step(action)
                return problem.complete_guide_allocation(alloc_env.get_allocation())
    return allocate(problem).as_dict()


def make_env(problem: ProblemInstance) -> ActionMasker:
    target = _get_target_allocation(problem) if config.ALLOC_LAMBDA > 0.0 else {}
    env = DispatchEnv(
        problem,
        max_tasks=config.MAX_TASKS,
        max_models=config.MAX_MODELS,
        dwell_lambda=config.DWELL_LAMBDA,
        alloc_lambda=config.ALLOC_LAMBDA,
        target_allocation=target,
        dwell_obs=config.DWELL_OBS,
        guide_util_threshold=config.GUIDE_UTIL_THRESHOLD,
        guide_band_pct=config.GUIDE_BAND_PCT,
    )
    return ActionMasker(env, _mask_fn)


def collect_teacher_dataset(problems: list[ProblemInstance]):
    obs_buf, act_buf, mask_buf = [], [], []
    for p in problems:
        target = _get_target_allocation(p) if config.ALLOC_LAMBDA > 0.0 else {}
        env = DispatchEnv(
            p, max_tasks=config.MAX_TASKS, max_models=config.MAX_MODELS,
            dwell_lambda=config.DWELL_LAMBDA, alloc_lambda=config.ALLOC_LAMBDA,
            target_allocation=target, dwell_obs=config.DWELL_OBS,
            guide_util_threshold=config.GUIDE_UTIL_THRESHOLD,
            guide_band_pct=config.GUIDE_BAND_PCT,
        )
        sim = Simulator(p)
        obs, _ = env.reset()
        move_to_idx = {mv: i + 1 for i, mv in enumerate(env.move_list)}
        done = False
        guard = 0
        max_guard = p.horizon_hours * (sum(p.eqp_qty.values()) + 2) + 5
        while not done and guard < max_guard:
            planned = heuristic_actions(sim, copy.deepcopy(env._state))
            action_seq = [move_to_idx[m] for m in planned if m in move_to_idx] + [0]
            for a in action_seq:
                mask = env.action_masks()
                if not mask[a]:
                    a = 0
                obs_buf.append(obs.copy())
                act_buf.append(a)
                mask_buf.append(mask.copy())
                obs, r, term, trunc, info = env.step(a)
                guard += 1
                if term or trunc:
                    done = True
                    break
    return np.array(obs_buf, dtype=np.float32), np.array(act_buf), np.array(mask_buf)


def behavior_clone(model: MaskablePPO, obs, acts, masks, epochs: int, lr: float,
                   loss_target: float = config.BC_LOSS_TARGET):
    if len(obs) == 0:
        return
    policy = model.policy
    policy.set_training_mode(True)
    opt = torch.optim.Adam(policy.parameters(), lr=lr)
    obs_t = torch.as_tensor(np.asarray(obs), dtype=torch.float32)
    act_t = torch.as_tensor(np.asarray(acts), dtype=torch.long)
    mask_t = torch.as_tensor(np.asarray(masks), dtype=torch.bool)
    for epoch in range(epochs):
        opt.zero_grad()
        features = policy.extract_features(obs_t)
        latent_pi, _ = policy.mlp_extractor(features)
        logits = policy.action_net(latent_pi)
        logits = logits.masked_fill(~mask_t, -1e8)
        loss = torch.nn.functional.cross_entropy(logits, act_t)
        loss.backward()
        opt.step()
        if loss.item() < loss_target:
            log.info("[BC] 조기종료: epoch %s/%s, loss=%.4f", epoch + 1, epochs, loss.item())
            break
        if (epoch + 1) % max(1, epochs // 20) == 0 or epoch == 0:
            append_training_point("dispatch", {
                "phase": "bc",
                "timesteps": epoch + 1,
                "mean_reward": round(-float(loss.item()), 6),
                "loss": round(float(loss.item()), 6),
            })
    policy.set_training_mode(False)


def train_model(problems: list[ProblemInstance], ppo_steps: int = config.DEFAULT_PPO_STEPS,
                bc_epochs: int = config.BC_EPOCHS, lr: float = config.BC_LR,
                save_path: Path | None = None) -> MaskablePPO:
    save_path = Path(save_path) if save_path else config.MODEL_PATH
    save_path.parent.mkdir(parents=True, exist_ok=True)

    def _shape(p):
        e = DispatchEnv(p, max_tasks=config.MAX_TASKS, max_models=config.MAX_MODELS,
                        dwell_obs=config.DWELL_OBS)
        return (tuple(e.observation_space.shape), int(e.action_space.n))
    base = _shape(problems[0])
    same = [p for p in problems if _shape(p) == base]
    if len(same) < len(problems):
        log.info(
            "[train] shape가 다른 문제 %s개 제외 (단일 정책은 동일 shape만 학습). %s개로 학습.",
            len(problems) - len(same),
            len(same),
        )
    problems = same

    def _vec_env():
        return DummyVecEnv([lambda: make_env(random.choice(problems))])

    if config.USE_ALLOC_MODEL and config.ALLOC_LAMBDA > 0.0:
        train_alloc_model(problems, ppo_steps=max(2000, ppo_steps // 10))

    reset_training_log("dispatch")

    model = MaskablePPO("MlpPolicy", _vec_env(), verbose=0, n_steps=256, batch_size=64)
    obs, acts, masks = collect_teacher_dataset(problems)
    behavior_clone(model, obs, acts, masks, bc_epochs, lr)
    model.set_env(_vec_env())
    model.learn(
        total_timesteps=ppo_steps,
        progress_bar=False,
        callback=ConvergenceLogger("dispatch"),
    )
    model.save(save_path)
    return model


def load_problems_from_dir(directory: Path | None = None) -> list[ProblemInstance]:
    from src.utils.json_io import load_problem
    if directory is None:
        directory = config.TRAIN_DATA_DIR
    return [load_problem(p) for p in sorted(Path(directory).glob("*.json"))]
