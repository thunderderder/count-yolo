from pathlib import Path

import pytest

from count_yolo.compare import compare_counts, load_gt, pred_from_payload
from count_yolo.timeparse import parse_time_to_seconds

ROOT = Path(__file__).resolve().parents[1]


def test_parse_time():
    assert parse_time_to_seconds("12") == 12
    assert parse_time_to_seconds("1:30") == 90
    assert parse_time_to_seconds("1:02:03") == 3723


def test_l1_yolov8m_full_within_tolerance():
    gt = load_gt(ROOT / "ground_truth" / "文锦北路-草埔立交匝道_临时.csv")
    payload = {
        "counts": [
            {
                "entry_direction": "南",
                "movement": "直行",
                "total": 1304,
            }
        ]
    }
    pred = pred_from_payload(payload)
    result = compare_counts(gt, pred, level="L1", duration_sec=1346.01)
    assert result.rows[0].passed is True
    assert abs(result.rows[0].err_pct) <= 15.0
    assert result.rows[0].pred == 1304


def test_l1_partial_clip_is_scaled():
    gt = {("南", "直行"): 1533.0}
    pred = {("南", "直行"): 130}
    result = compare_counts(gt, pred, level="L1", duration_sec=120.0, full_video_sec=22 * 60)
    assert result.rows[0].pred == pytest.approx(130 * 22 * 60 / 120)


def test_l1_too_low_fails():
    gt = {("南", "直行"): 1533.0}
    pred = {("南", "直行"): 1000}
    result = compare_counts(gt, pred, level="L1", duration_sec=22 * 60)
    assert result.overall_pass is False
