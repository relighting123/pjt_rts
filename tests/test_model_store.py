import config
from agents.model_store import alloc_model_matches
from src.utils.json_io import load_problem


def test_alloc_model_matches_shape():
    p = load_problem(config.TRAIN_DATA_DIR / "benchmark_train_01.json")
    assert alloc_model_matches(None, p) is False


def test_train_model_raises_when_no_problems():
    from src.training.dispatch import train_model

    try:
        train_model([], ppo_steps=64, bc_epochs=1)
        assert False, "expected ValueError"
    except ValueError as e:
        assert "학습 가능한 문제가 없습니다" in str(e)
