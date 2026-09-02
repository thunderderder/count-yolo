from count_yolo.geometry import (
    crossed_line,
    crossing_transition,
    is_before_line,
    motion_matches_direction,
    point_in_polygon,
)


def test_motion_near_to_far():
    hist = [800.0, 780.0, 760.0, 740.0, 720.0, 700.0]
    assert motion_matches_direction(hist, "near_to_far") is True
    assert motion_matches_direction(hist, "far_to_near") is False


def test_motion_far_to_near():
    hist = [200.0, 230.0, 260.0, 290.0, 320.0, 350.0]
    assert motion_matches_direction(hist, "far_to_near") is True
    assert motion_matches_direction(hist, "near_to_far") is False


def test_motion_slow_congestion_near_to_far():
    """拥堵慢车：每帧约 -0.4px，旧阈值会漏计。"""
    hist = [812.0, 811.6, 811.2, 810.8, 810.4, 810.0, 809.6, 799.0]
    assert motion_matches_direction(hist, "near_to_far") is True


def test_motion_rejects_wrong_direction_despite_noise():
  hist = [700.0, 705.0, 710.0, 715.0, 720.0, 725.0]
  assert motion_matches_direction(hist, "near_to_far") is False


def test_motion_rejects_short_history():
    assert motion_matches_direction([800.0, 790.0], "near_to_far") is False


def test_crossed_line():
    assert crossed_line(810, 790, 800, "near_to_far") is True
    assert crossed_line(790, 810, 800, "near_to_far") is False
    assert crossed_line(790, 810, 800, "far_to_near") is True


def test_crossing_transition_on_line():
    assert crossing_transition(801, 800, 800, "near_to_far") is True
    assert crossing_transition(800, 799, 800, "near_to_far") is False
    assert is_before_line(800, 800, "near_to_far") is False


def test_point_in_polygon_square():
    square = [[0, 0], [10, 0], [10, 10], [0, 10]]
    assert point_in_polygon(5, 5, square) is True
    assert point_in_polygon(20, 5, square) is False
    assert point_in_polygon(0, 0, square) is True
