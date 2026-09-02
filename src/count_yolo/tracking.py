from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

# Ultralytics ByteTrack defaults (cfg/trackers/bytetrack.yaml)
DEFAULT_TRACK_BUFFER = 30
DEFAULT_TRACK_HIGH_THRESH = 0.25
DEFAULT_TRACK_LOW_THRESH = 0.1
DEFAULT_NEW_TRACK_THRESH = 0.25
DEFAULT_MATCH_THRESH = 0.8

# 拥堵 / 遮挡场景：更长缓冲 + 更低检测/关联阈值，换轨风险略升
OCCLUSION_PRESET = {
    "conf": 0.2,
    "track_buffer": 90,
    "track_low_thresh": 0.05,
    "match_thresh": 0.75,
    "vid_stride": 1,
}


@dataclass
class TrackSettings:
    """YOLO 检测 + ByteTrack 关联参数（可写入 job yaml / Web 调试）。"""

    conf: float = 0.25
    iou: float = 0.7
    vid_stride: int = 1
    track_buffer: int = DEFAULT_TRACK_BUFFER
    track_high_thresh: float = DEFAULT_TRACK_HIGH_THRESH
    track_low_thresh: float = DEFAULT_TRACK_LOW_THRESH
    new_track_thresh: float = DEFAULT_NEW_TRACK_THRESH
    match_thresh: float = DEFAULT_MATCH_THRESH
    fuse_score: bool = True

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None) -> TrackSettings:
        if not data:
            return cls()
        return cls(
            conf=float(data.get("conf", 0.25)),
            iou=float(data.get("iou", 0.7)),
            vid_stride=int(data.get("vid_stride", 1)),
            track_buffer=int(data.get("track_buffer", DEFAULT_TRACK_BUFFER)),
            track_high_thresh=float(data.get("track_high_thresh", DEFAULT_TRACK_HIGH_THRESH)),
            track_low_thresh=float(data.get("track_low_thresh", DEFAULT_TRACK_LOW_THRESH)),
            new_track_thresh=float(data.get("new_track_thresh", DEFAULT_NEW_TRACK_THRESH)),
            match_thresh=float(data.get("match_thresh", DEFAULT_MATCH_THRESH)),
            fuse_score=bool(data.get("fuse_score", True)),
        )

    @classmethod
    def from_job_fields(cls, job: Any) -> TrackSettings:
        return cls(
            conf=float(getattr(job, "conf", 0.25) or 0.25),
            iou=float(getattr(job, "iou", 0.7) or 0.7),
            vid_stride=int(getattr(job, "vid_stride", 1) or 1),
            track_buffer=int(getattr(job, "track_buffer", DEFAULT_TRACK_BUFFER) or DEFAULT_TRACK_BUFFER),
            track_high_thresh=float(getattr(job, "track_high_thresh", DEFAULT_TRACK_HIGH_THRESH) or DEFAULT_TRACK_HIGH_THRESH),
            track_low_thresh=float(getattr(job, "track_low_thresh", DEFAULT_TRACK_LOW_THRESH) or DEFAULT_TRACK_LOW_THRESH),
            new_track_thresh=float(getattr(job, "new_track_thresh", DEFAULT_NEW_TRACK_THRESH) or DEFAULT_NEW_TRACK_THRESH),
            match_thresh=float(getattr(job, "match_thresh", DEFAULT_MATCH_THRESH) or DEFAULT_MATCH_THRESH),
            fuse_score=bool(getattr(job, "fuse_score", True)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
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

    def write_tracker_yaml(self, path: Path) -> Path:
        payload = {
            "tracker_type": "bytetrack",
            "track_high_thresh": self.track_high_thresh,
            "track_low_thresh": self.track_low_thresh,
            "new_track_thresh": self.new_track_thresh,
            "track_buffer": self.track_buffer,
            "match_thresh": self.match_thresh,
            "fuse_score": self.fuse_score,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(payload, f, allow_unicode=True, sort_keys=False)
        return path

    def summary_lines(self) -> list[str]:
        return [
            f"conf={self.conf}, iou={self.iou}, vid_stride={self.vid_stride}",
            (
                f"track_buffer={self.track_buffer}, match_thresh={self.match_thresh}, "
                f"low={self.track_low_thresh}, high={self.track_high_thresh}"
            ),
        ]
