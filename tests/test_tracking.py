from pathlib import Path

from count_yolo.tracking import TrackSettings


def test_track_settings_write_yaml(tmp_path: Path):
    settings = TrackSettings(conf=0.2, track_buffer=90, track_low_thresh=0.05)
    path = settings.write_tracker_yaml(tmp_path / "tracker.yaml")
    text = path.read_text(encoding="utf-8")
    assert "track_buffer: 90" in text
    assert "tracker_type: bytetrack" in text


def test_track_settings_from_job_fields():
    class FakeJob:
        conf = 0.2
        track_buffer = 60

    settings = TrackSettings.from_job_fields(FakeJob())
    assert settings.conf == 0.2
    assert settings.track_buffer == 60
    assert settings.iou == 0.7
