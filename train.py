"""모방학습(BC) → MaskablePPO 학습.

teacher(휴리스틱) 궤적을 환경 위에서 재현하며 (obs, action, mask)를 모아
정책망을 교차엔트로피로 사전학습한 뒤 PPO로 강화한다.
"""
from __future__ import annotations
import copy
import random
from pathlib import Path
import numpy as np
import torch

from sb3_contrib import MaskablePPO
from sb3_contrib.common.wrappers import ActionMasker

from simulator import ProblemInstance, Simulator, heuristic_actions
from env import DispatchEnv
import config


def _mask_fn(env) -> np.ndarray:
    return env.action_masks()


def make_env(problem: ProblemInstance) -> ActionMasker:
    return ActionMasker(DispatchEnv(problem, max_tasks=config.MAX_TASKS, max_models=config.MAX_MODELS), _mask_fn)


def collect_teacher_dataset(problems: list[ProblemInstance]):
    """teacher가 두는 액션 시퀀스를 env 인덱스로 변환해 (obs, action, mask) 수집."""
    obs_buf, act_buf, mask_buf = [], [], []
    for p in problems:
        env = DispatchEnv(p, max_tasks=config.MAX_TASKS, max_models=config.MAX_MODELS)
        sim = Simulator(p)
        obs, _ = env.reset()
        move_to_idx = {mv: i + 1 for i, mv in enumerate(env.move_list)}
        done = False
        guard = 0
        max_guard = p.horizon_hours * (sum(p.eqp_qty.values()) + 2) + 5
        while not done and guard < max_guard:
            # teacher가 이번 시간에 둘 이동들을 비파괴적으로 계산 (상태 깊은복제)
            planned = heuristic_actions(sim, copy.deepcopy(env._state))
            action_seq = [move_to_idx[m] for m in planned if m in move_to_idx] + [0]
            for a in action_seq:
                mask = env.action_masks()
                if not mask[a]:
                    a = 0  # 유효하지 않으면 commit으로 대체
                obs_buf.append(obs.copy())
                act_buf.append(a)
                mask_buf.append(mask.copy())
                obs, r, term, trunc, info = env.step(a)
                guard += 1
                if term or trunc:
                    done = True
                    break
    return np.array(obs_buf, dtype=np.float32), np.array(act_buf), np.array(mask_buf)


def behavior_clone(model: MaskablePPO, obs, acts, masks, epochs: int, lr: float):
    """정책망을 teacher 액션에 대해 마스킹된 교차엔트로피로 사전학습."""
    if len(obs) == 0:
        return
    policy = model.policy
    policy.set_training_mode(True)
    opt = torch.optim.Adam(policy.parameters(), lr=lr)
    obs_t = torch.as_tensor(np.asarray(obs), dtype=torch.float32)
    act_t = torch.as_tensor(np.asarray(acts), dtype=torch.long)
    mask_t = torch.as_tensor(np.asarray(masks), dtype=torch.bool)
    for _ in range(epochs):
        opt.zero_grad()
        features = policy.extract_features(obs_t)
        latent_pi, _ = policy.mlp_extractor(features)
        logits = policy.action_net(latent_pi)
        logits = logits.masked_fill(~mask_t, -1e8)
        loss = torch.nn.functional.cross_entropy(logits, act_t)
        loss.backward()
        opt.step()
    policy.set_training_mode(False)


def train_model(problems: list[ProblemInstance], ppo_steps: int = config.DEFAULT_PPO_STEPS,
                bc_epochs: int = config.BC_EPOCHS, lr: float = config.BC_LR,
                save_path: Path | None = None) -> MaskablePPO:
    save_path = Path(save_path) if save_path else config.MODEL_PATH
    save_path.parent.mkdir(parents=True, exist_ok=True)

    # 단일 정책은 동일 (관측/액션) shape만 학습 가능 → 첫 문제 기준으로 필터
    def _shape(p):
        e = DispatchEnv(p, max_tasks=config.MAX_TASKS, max_models=config.MAX_MODELS)
        return (tuple(e.observation_space.shape), int(e.action_space.n))
    base = _shape(problems[0])
    same = [p for p in problems if _shape(p) == base]
    if len(same) < len(problems):
        print(f"[train] shape가 다른 문제 {len(problems) - len(same)}개 제외 "
              f"(단일 정책은 동일 shape만 학습). {len(same)}개로 학습.")
    problems = same

    def env_fn():
        return make_env(random.choice(problems))

    model = MaskablePPO("MlpPolicy", env_fn(), verbose=0, n_steps=256, batch_size=64)
    # 1) 행동복제
    obs, acts, masks = collect_teacher_dataset(problems)
    behavior_clone(model, obs, acts, masks, bc_epochs, lr)
    # 2) PPO 강화
    model.set_env(env_fn())
    model.learn(total_timesteps=ppo_steps, progress_bar=False)
    model.save(save_path)
    return model


def load_problems_from_dir(directory: Path | None = None) -> list[ProblemInstance]:
    from simulator import load_problem
    if directory is None:
        directory = config.BENCHMARKS_TRAIN_DIR
    return [load_problem(p) for p in sorted(Path(directory).glob("benchmark_*.json"))]
