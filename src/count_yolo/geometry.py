from __future__ import annotations

import numpy as np


def motion_matches_direction(cy_hist: list[float], direction: str, min_points: int = 5) -> bool:
    """近期轨迹是否与过线方向一致。near_to_far = 画面向上（y 变小）。"""
    if len(cy_hist) < min_points:
        return False
    dy_total = cy_hist[-1] - cy_hist[0]
    step = max(1, len(cy_hist) // 4)
    partial = [cy_hist[i + step] - cy_hist[i] for i in range(0, len(cy_hist) - step, step)]
    if not partial:
        return False
    dy_med = float(np.median(partial))
    if direction == "near_to_far":
        return dy_total < -6.0 and dy_med < -1.0
    if direction == "far_to_near":
        return dy_total > 6.0 and dy_med > 1.0
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


def crossed_line(last_cy: float, cy: float, line_y: float, direction: str) -> bool:
    if direction == "near_to_far":
        return last_cy > line_y >= cy
    if direction == "far_to_near":
        return last_cy < line_y <= cy
    return False
