from pathlib import Path

from count_yolo.jobs import Job, job_output_dir, load_job, save_job


def test_job_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr("count_yolo.jobs.JOBS_DIR", tmp_path)
    job = Job(
        id="2026-测试_南直行_0901",
        video="videos/a.MP4",
        config="configs/x.json",
        lines=["L1_主路", "L1_匝道"],
        ebike_enabled=True,
    )
    save_job(job)
    loaded = load_job(job.id)
    assert loaded.video == job.video
    assert loaded.lines == job.lines
    assert loaded.ebike_enabled is True


def test_job_output_dir_default():
    job = Job(id="2026-文锦北路_三断面_0901", video="a.mp4", config="c.json")
    out = job_output_dir(job)
    assert out.name == job.id
    assert out.parent.name == "jobs"


def test_resolve_count_window_preview():
    from count_yolo.jobs import resolve_count_window

    job = Job(id="x", video="a.mp4", config="c.json", start=0, preview_seconds=30)
    start, end = resolve_count_window(job)
    assert start == 0
    assert end == 30


def test_resolve_count_window_full():
    from count_yolo.jobs import resolve_count_window

    job = Job(id="x", video="a.mp4", config="c.json", start=10, end=120)
    start, end = resolve_count_window(job)
    assert start == 10
    assert end == 120
