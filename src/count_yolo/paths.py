from __future__ import annotations

from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parents[1]


def default_video() -> Path:
    named = PROJECT_ROOT / "文锦北路-草埔立交匝道临时.MP4"
    if named.is_file():
        return named
    for pattern in ("*.MP4", "*.mp4"):
        found = sorted(PROJECT_ROOT.glob(pattern))
        if found:
            return found[0]
    return named


def default_config() -> Path:
    return PROJECT_ROOT / "configs" / "文锦北路-草埔立交匝道_临时.json"


def default_model() -> Path:
    return PROJECT_ROOT / "models" / "yolov8m.pt"
