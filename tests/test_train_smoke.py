from src.utils.json_io import load_problem
from config import BENCHMARKS_DIR
from src.training.dispatch import collect_teacher_dataset, train_model


def test_collect_teacher_dataset_nonempty():
    p = load_problem(BENCHMARKS_DIR / "benchmark_02.json")
    obs, acts, masks = collect_teacher_dataset([p])
    assert len(obs) == len(acts) == len(masks)
    assert len(obs) > 0


def test_train_smoke_runs_and_saves(tmp_path):
    p = load_problem(BENCHMARKS_DIR / "benchmark_01.json")
    out = tmp_path / "m.zip"
    model = train_model([p], ppo_steps=200, bc_epochs=5, save_path=out)
    assert out.exists()
