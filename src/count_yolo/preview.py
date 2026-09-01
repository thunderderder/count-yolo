from __future__ import annotations

import json
import os
from pathlib import Path

try:
    import cv2
except ImportError:  # pragma: no cover
    cv2 = None

LINE_COLORS_BGR = [
    (0, 255, 255),
    (0, 165, 255),
    (255, 128, 0),
    (0, 255, 0),
    (255, 0, 255),
    (255, 255, 0),
]


def draw_saved_lines(vis, saved_lines: dict[str, list[tuple[int, int]]]) -> None:
    if cv2 is None:
        return
    for idx, (name, pts) in enumerate(saved_lines.items()):
        color = LINE_COLORS_BGR[idx % len(LINE_COLORS_BGR)]
        cv2.line(vis, pts[0], pts[1], color, 3)
        mid_x = (pts[0][0] + pts[1][0]) // 2
        mid_y = (pts[0][1] + pts[1][1]) // 2
        cv2.putText(vis, name, (mid_x, mid_y - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)


def write_calibration_preview(
    frame,
    lines: dict[str, list[tuple[int, int]]],
    output_mp4: Path,
    *,
    duration_sec: float = 10.0,
    fps: float | None = None,
) -> Path:
    if cv2 is None:
        raise ImportError("opencv-python is required")
    if not lines:
        raise ValueError("no lines to preview")

    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    height, width = frame.shape[:2]
    use_fps = fps or 24.0
    total_frames = max(1, int(duration_sec * use_fps))

    still = frame.copy()
    draw_saved_lines(still, lines)
    cv2.putText(
        still,
        "calibration preview",
        (20, 35),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (255, 255, 255),
        2,
    )

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(output_mp4), fourcc, use_fps, (width, height))
    for _ in range(total_frames):
        writer.write(still)
    writer.release()

    jpg = output_mp4.with_suffix(".jpg")
    cv2.imwrite(str(jpg), still)
    return output_mp4


def render_line_overlay(frame, line_entries: dict[str, dict]):
    vis = frame.copy()
    saved: dict[str, list[tuple[int, int]]] = {}
    for name, entry in line_entries.items():
        (x1, y1), (x2, y2) = entry["line"]
        saved[name] = [(int(x1), int(y1)), (int(x2), int(y2))]
    draw_saved_lines(vis, saved)
    return vis
