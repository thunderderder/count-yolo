from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class MotionSettings:
    """过线后的运动方向过滤（挡对向/潮汐；慢车场景可放宽阈值）。"""

    require_motion_direction: bool = True
    motion_min_points: int = 3
    motion_min_dy_total: float = 1.5
    motion_min_dy_med: float = 0.25

    @classmethod
    def from_job_fields(cls, job: Any) -> MotionSettings:
        return cls(
            require_motion_direction=bool(getattr(job, "require_motion_direction", True)),
            motion_min_points=int(getattr(job, "motion_min_points", 3) or 3),
            motion_min_dy_total=float(getattr(job, "motion_min_dy_total", 1.5) or 1.5),
            motion_min_dy_med=float(getattr(job, "motion_min_dy_med", 0.25) or 0.25),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "require_motion_direction": self.require_motion_direction,
            "motion_min_points": self.motion_min_points,
            "motion_min_dy_total": self.motion_min_dy_total,
            "motion_min_dy_med": self.motion_min_dy_med,
        }

    def summary_lines(self) -> list[str]:
        if not self.require_motion_direction:
            return ["motion_filter=off (geometry crossing only)"]
        return [
            (
                f"motion_filter=on min_points={self.motion_min_points} "
                f"dy_total={self.motion_min_dy_total} dy_med={self.motion_min_dy_med}"
            )
        ]

    def line_requires_motion(self, line_cfg: dict[str, Any]) -> bool:
        """Job 级开关覆盖 config 里各断面的 require_motion_direction。"""
        if not self.require_motion_direction:
            return False
        return bool(line_cfg.get("require_motion_direction", True))
