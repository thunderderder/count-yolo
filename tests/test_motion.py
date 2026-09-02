from count_yolo.geometry import motion_matches_direction
from count_yolo.motion import MotionSettings


def test_motion_settings_off():
    settings = MotionSettings(require_motion_direction=False)
    assert settings.line_requires_motion({"require_motion_direction": True}) is False


def test_motion_settings_respects_line_when_on():
    settings = MotionSettings(require_motion_direction=True)
    assert settings.line_requires_motion({"require_motion_direction": True}) is True
    assert settings.line_requires_motion({"require_motion_direction": False}) is False


def test_motion_custom_thresholds():
    hist = [812.0, 811.8, 811.6, 811.4, 811.2, 810.9]
    strict = MotionSettings(motion_min_dy_total=2.0, motion_min_dy_med=0.5)
    loose = MotionSettings(motion_min_dy_total=1.0, motion_min_dy_med=0.1, motion_min_points=2)
    assert motion_matches_direction(hist, "near_to_far", strict) is False
    assert motion_matches_direction(hist, "near_to_far", loose) is True
