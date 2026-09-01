from __future__ import annotations

import json
import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parents[1]
JOBS_DIR = PROJECT_ROOT / "jobs"


def resolve_path(path: str | Path) -> Path:
    p = Path(path)
    if p.is_absolute():
        return p
    return (PROJECT_ROOT / p).resolve()


def default_video() -> Path:
    named = PROJECT_ROOT / "文锦北路-草埔立交匝道临时.MP4"
    if named.is_file():
        return named
    for pattern in ("*.MP4", "*.mp4"):
        found = sorted(PROJECT_ROOT.glob(pattern))
        if found:
            return found[0]
    videos = sorted((PROJECT_ROOT / "videos").glob("*.mp*")) if (PROJECT_ROOT / "videos").is_dir() else []
    if videos:
        return videos[0]
    return named


def default_config() -> Path:
    return PROJECT_ROOT / "configs" / "文锦北路-草埔立交匝道_临时.json"


def resolve_config(config_path: Path | str | None = None) -> Path:
    if config_path is not None:
        return resolve_path(config_path)
    env = os.environ.get("COUNT_YOLO_CONFIG")
    if env:
        return resolve_path(env)
    return default_config()


def default_model() -> Path:
    return PROJECT_ROOT / "models" / "yolov8m.pt"


def default_ebike_model() -> Path:
    env = os.environ.get("COUNT_YOLO_EBIKE_MODEL")
    if env:
        candidate = resolve_path(env)
        if candidate.is_file():
            return candidate
    local = PROJECT_ROOT / "models" / "electri_bike_and_vehicle.pt"
    if local.is_file():
        return local
    uva = PROJECT_ROOT.parent / "uva" / "model" / "yolo" / "electri_bike_and_vehicle_200.pt"
    if uva.is_file():
        return uva
    return local


def default_job_id() -> str | None:
    env = os.environ.get("COUNT_YOLO_JOB")
    if not env:
        return None
    return Path(env).stem


def resolve_video(
    video: Path | str | None = None,
    *,
    config_path: Path | str | None = None,
) -> Path:
    if video is not None:
        return resolve_path(video)
    env = os.environ.get("COUNT_YOLO_VIDEO")
    if env:
        return resolve_path(env)
    cfg_path = resolve_config(config_path) if config_path is not None else None
    if cfg_path and cfg_path.is_file():
        with cfg_path.open(encoding="utf-8") as f:
            data = json.load(f)
        vf = data.get("video_file")
        if vf:
            return resolve_path(vf)
    return default_video()


def safe_output_path(path: Path) -> Path:
    resolved = path.resolve()
    root = PROJECT_ROOT.resolve()
    if resolved == root or root in resolved.parents:
        return resolved
    raise ValueError(f"path outside project: {path}")
