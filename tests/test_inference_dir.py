from pathlib import Path

from db.pipeline import clear_inference_dir
import config


def test_clear_inference_dir_removes_json_keeps_gitkeep(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "INFERENCE_DATA_DIR", tmp_path)
    (tmp_path / ".gitkeep").write_text("", encoding="utf-8")
    (tmp_path / "old.json").write_text("{}", encoding="utf-8")
    (tmp_path / "old_result.json").write_text("{}", encoding="utf-8")

    clear_inference_dir()

    assert (tmp_path / ".gitkeep").is_file()
    assert not (tmp_path / "old.json").exists()
    assert not (tmp_path / "old_result.json").exists()
