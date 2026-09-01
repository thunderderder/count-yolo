from __future__ import annotations

import json
from pathlib import Path

import pytest

from count_yolo.paths import PROJECT_ROOT, resolve_config, resolve_path, resolve_video


def test_resolve_path_relative_to_project_root():
    assert resolve_path("configs/foo.json") == (PROJECT_ROOT / "configs/foo.json").resolve()


def test_resolve_path_absolute_unchanged(tmp_path: Path):
    abs_path = tmp_path / "clip.mp4"
    assert resolve_path(abs_path) == abs_path.resolve()


def test_resolve_video_prefers_explicit(tmp_path: Path):
    explicit = tmp_path / "a.mp4"
    explicit.touch()
    got = resolve_video(explicit, config_path=PROJECT_ROOT / "missing.json")
    assert got == explicit.resolve()


def test_resolve_video_prefers_env_over_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    env_video = tmp_path / "from_env.mp4"
    env_video.touch()
    monkeypatch.setenv("COUNT_YOLO_VIDEO", str(env_video))
    got = resolve_video(config_path=PROJECT_ROOT / "configs/文锦北路-草埔立交匝道_临时.json")
    assert got == env_video.resolve()


def test_resolve_video_from_config_field(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("COUNT_YOLO_VIDEO", raising=False)
    video = tmp_path / "from_config.mp4"
    video.touch()
    cfg = tmp_path / "site.json"
    cfg.write_text(json.dumps({"video_file": str(video)}), encoding="utf-8")
    assert resolve_video(config_path=cfg) == video.resolve()


def test_resolve_video_relative_in_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("COUNT_YOLO_VIDEO", raising=False)
    video = tmp_path / "videos" / "clip.mp4"
    video.parent.mkdir(parents=True)
    video.touch()
    cfg = tmp_path / "site.json"
    cfg.write_text(json.dumps({"video_file": "videos/clip.mp4"}), encoding="utf-8")
    monkeypatch.setattr("count_yolo.paths.PROJECT_ROOT", tmp_path)
    assert resolve_video(config_path=cfg) == video.resolve()


def test_resolve_config_prefers_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("COUNT_YOLO_CONFIG", "configs/custom.json")
    assert resolve_config() == (PROJECT_ROOT / "configs/custom.json").resolve()
