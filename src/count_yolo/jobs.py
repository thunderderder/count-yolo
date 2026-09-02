from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from count_yolo.paths import JOBS_DIR, PROJECT_ROOT, default_config, default_ebike_model, default_video, resolve_path


@dataclass
class Job:
    id: str
    video: str
    config: str
    lines: list[str] = field(default_factory=list)
    model: str = "8m"
    device: str = "auto"
    start: float = 0.0
    end: float | None = None
    output_dir: str | None = None
    ground_truth: str | None = None
    ebike_enabled: bool = False
    preview_seconds: int | None = None
    note: str = ""
    # 检测 / ByteTrack（遮挡调试见 Web「检测与跟踪」）
    conf: float = 0.25
    iou: float = 0.7
    vid_stride: int = 1
    track_buffer: int = 30
    track_high_thresh: float = 0.25
    track_low_thresh: float = 0.1
    new_track_thresh: float = 0.25
    match_thresh: float = 0.8
    fuse_score: bool = True

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "video": self.video,
            "config": self.config,
            "lines": self.lines,
            "model": self.model,
            "device": self.device,
            "start": self.start,
            "ebike_enabled": self.ebike_enabled,
        }
        if self.end is not None:
            data["end"] = self.end
        if self.preview_seconds is not None:
            data["preview_seconds"] = self.preview_seconds
        if self.output_dir:
            data["output_dir"] = self.output_dir
        if self.ground_truth:
            data["ground_truth"] = self.ground_truth
        if self.note:
            data["note"] = self.note
        data.update(
            {
                "conf": self.conf,
                "iou": self.iou,
                "vid_stride": self.vid_stride,
                "track_buffer": self.track_buffer,
                "track_high_thresh": self.track_high_thresh,
                "track_low_thresh": self.track_low_thresh,
                "new_track_thresh": self.new_track_thresh,
                "match_thresh": self.match_thresh,
                "fuse_score": self.fuse_score,
            }
        )
        return data

    @classmethod
    def from_dict(cls, job_id: str, data: dict[str, Any]) -> Job:
        lines = data.get("lines") or []
        if isinstance(lines, str):
            lines = [part.strip() for part in lines.split(",") if part.strip()]
        return cls(
            id=job_id,
            video=str(data.get("video") or ""),
            config=str(data.get("config") or ""),
            lines=list(lines),
            model=str(data.get("model") or "8m"),
            device=str(data.get("device") or "auto"),
            start=float(data.get("start") or 0),
            end=float(data["end"]) if data.get("end") is not None else None,
            output_dir=str(data["output_dir"]) if data.get("output_dir") else None,
            ground_truth=str(data["ground_truth"]) if data.get("ground_truth") else None,
            ebike_enabled=bool(data.get("ebike_enabled", False)),
            preview_seconds=int(data["preview_seconds"]) if data.get("preview_seconds") is not None else None,
            note=str(data.get("note") or ""),
            conf=float(data.get("conf", 0.25) or 0.25),
            iou=float(data.get("iou", 0.7) or 0.7),
            vid_stride=int(data.get("vid_stride", 1) or 1),
            track_buffer=int(data.get("track_buffer", 30) or 30),
            track_high_thresh=float(data.get("track_high_thresh", 0.25) or 0.25),
            track_low_thresh=float(data.get("track_low_thresh", 0.1) or 0.1),
            new_track_thresh=float(data.get("new_track_thresh", 0.25) or 0.25),
            match_thresh=float(data.get("match_thresh", 0.8) or 0.8),
            fuse_score=bool(data.get("fuse_score", True)),
        )


def resolve_count_window(job: Job) -> tuple[float, float | None]:
    """Return (start_sec, end_sec). preview_seconds overrides job.end for short test runs."""
    start_sec = float(job.start or 0)
    if job.preview_seconds is not None and job.preview_seconds > 0:
        return start_sec, start_sec + float(job.preview_seconds)
    return start_sec, job.end


def job_path(job_id: str) -> Path:
    name = job_id if job_id.endswith(".yaml") else f"{job_id}.yaml"
    return JOBS_DIR / name


def list_job_ids() -> list[str]:
    if not JOBS_DIR.is_dir():
        return []
    ids: list[str] = []
    for path in sorted(JOBS_DIR.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        ids.append(path.stem)
    return ids


def load_job(job_id: str) -> Job:
    path = job_path(job_id)
    if not path.is_file():
        raise FileNotFoundError(f"job not found: {path}")
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return Job.from_dict(path.stem, data)


def save_job(job: Job) -> Path:
    path = job_path(job.id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(job.to_dict(), f, allow_unicode=True, sort_keys=False)
    return path


def resolve_job_video(job: Job, cli_video: Path | None = None) -> Path:
    if cli_video is not None:
        return resolve_path(cli_video)
    if job.video:
        return resolve_path(job.video)
    env_video = os.environ.get("COUNT_YOLO_VIDEO")
    if env_video:
        return resolve_path(env_video)
    return default_video()


def resolve_job_config(job: Job, cli_config: Path | None = None) -> Path:
    if cli_config is not None:
        return resolve_path(cli_config)
    env_config = os.environ.get("COUNT_YOLO_CONFIG")
    if job.config:
        return resolve_path(job.config)
    if env_config:
        return resolve_path(env_config)
    return default_config()


def job_output_dir(job: Job) -> Path:
    if job.output_dir:
        return resolve_path(job.output_dir)
    return PROJECT_ROOT / "output" / "jobs" / job.id


def resolve_model_preset(preset: str) -> Path:
    preset = preset.strip()
    if preset in {"8m", "yolov8m"}:
        from count_yolo.paths import default_model

        return default_model()
    if preset in {"ebike", "electri"}:
        return default_ebike_model()
    path = resolve_path(preset)
    if path.is_file():
        return path
    raise FileNotFoundError(f"model not found: {preset}")
