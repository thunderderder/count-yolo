from __future__ import annotations

import numpy as np

from count_yolo.motion import MotionSettings


def is_before_line(cy: float, line_y: float, direction: str) -> bool:
    """过线前的一侧：near_to_far 为线下方（y 较大）。"""
    if direction == "near_to_far":
        return cy > line_y
    if direction == "far_to_near":
        return cy < line_y
    return False


def crossing_transition(last_cy: float, cy: float, line_y: float, direction: str) -> bool:
    """轨迹从过线前一侧进入另一侧（比逐帧比较更耐慢速/压线）。"""
    return is_before_line(last_cy, line_y, direction) and not is_before_line(cy, line_y, direction)


def crossed_line(last_cy: float, cy: float, line_y: float, direction: str) -> bool:
    return crossing_transition(last_cy, cy, line_y, direction)


def motion_matches_direction(
    cy_hist: list[float],
    direction: str,
    settings: MotionSettings | None = None,
) -> bool:
    """近期轨迹是否与过线方向一致。near_to_far = 画面向上（y 变小）。

    阈值刻意放低，避免拥堵慢车每帧位移 <1px 时在过线窗口内永远过不了运动过滤。
    仍用总位移符号 + 步长中位数/多数表决挡对向潮汐。
    """
    min_points = 3 if settings is None else settings.motion_min_points
    dy_total_thresh = 1.5 if settings is None else settings.motion_min_dy_total
    dy_med_thresh = 0.25 if settings is None else settings.motion_min_dy_med

    if len(cy_hist) < min_points:
        return False
    dy_total = cy_hist[-1] - cy_hist[0]
    step = max(1, len(cy_hist) // 4)
    partial = [cy_hist[i + step] - cy_hist[i] for i in range(0, len(cy_hist) - step, step)]
    if not partial:
        return False
    dy_med = float(np.median(partial))
    if direction == "near_to_far":
        correct = sum(1 for d in partial if d < 0)
        return dy_total < -dy_total_thresh and (
            dy_med < -dy_med_thresh or correct >= max(2, (len(partial) + 1) // 2)
        )
    if direction == "far_to_near":
        correct = sum(1 for d in partial if d > 0)
        return dy_total > dy_total_thresh and (
            dy_med > dy_med_thresh or correct >= max(2, (len(partial) + 1) // 2)
        )
    return False


def point_in_polygon(x: float, y: float, polygon: list[list[float]]) -> bool:
    """射线法。顶点视为在多边形内。"""
    n = len(polygon)
    if n < 3:
        return False
    for px, py in polygon:
        if abs(px - x) < 1e-9 and abs(py - y) < 1e-9:
            return True
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        intersects = ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi
        )
        if intersects:
            inside = not inside
        j = i
    return inside
