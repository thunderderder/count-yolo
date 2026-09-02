from __future__ import annotations

from pathlib import Path

from count_yolo.jobs import (
    Job,
    job_output_dir,
    load_job,
    resolve_count_window,
    resolve_job_config,
    resolve_job_video,
    resolve_model_preset,
)
from count_yolo.paths import PROJECT_ROOT
from count_yolo.pipeline import count_lines_traffic, load_config
from count_yolo.motion import MotionSettings
from count_yolo.timeparse import resolve_device
from count_yolo.tracking import TrackSettings


def _model_tag(model_path: Path) -> str:
    stem = model_path.stem
    if stem == "yolov8m":
        return "8m"
    if "electri" in stem or "ebike" in stem:
        return "ebike"
    return stem


def run_job(
    job_id: str,
    *,
    video: Path | None = None,
    config: Path | None = None,
    conf: float | None = None,
    vid_stride: int | None = None,
) -> dict:
    job = load_job(job_id)
    video_path = resolve_job_video(job, video)
    config_path = resolve_job_config(job, config)
    intersection = load_config(config_path)
    output_dir = job_output_dir(job)
    output_dir.mkdir(parents=True, exist_ok=True)

    line_names = list(intersection.get("line_counting", {}).keys()) or job.lines
    if not line_names:
        raise ValueError("job has no lines and config has no line_counting")

    device = resolve_device(job.device)
    start_sec, end_sec = resolve_count_window(job)
    track = TrackSettings.from_job_fields(job)
    motion = MotionSettings.from_job_fields(job)
    if conf is not None:
        track.conf = conf
    if vid_stride is not None:
        track.vid_stride = vid_stride
    tracker_yaml = track.write_tracker_yaml(output_dir / "tracker.yaml")

    print(f"job: {job.id}", flush=True)
    print(f"video: {video_path}", flush=True)
    print(f"config: {config_path}", flush=True)
    print(f"output: {output_dir}", flush=True)
    print(f"lines: {', '.join(line_names)}", flush=True)
    print(f"device: {device}", flush=True)
    for line in track.summary_lines():
        print(f"track: {line}", flush=True)
    for line in motion.summary_lines():
        print(f"motion: {line}", flush=True)
    print(f"tracker_yaml: {tracker_yaml.relative_to(PROJECT_ROOT).as_posix()}", flush=True)
    if job.preview_seconds:
        print(f"preview_run: {job.preview_seconds}s (start={start_sec}, end={end_sec})", flush=True)
    else:
        print(f"window: start={start_sec}, end={'full' if end_sec is None else end_sec}", flush=True)
    print(f"ebike_enabled: {job.ebike_enabled}", flush=True)

    primary_model = resolve_model_preset(job.model if job.model not in {"", "ebike"} else "8m")
    primary_tag = _model_tag(primary_model)

    primary = count_lines_traffic(
        video=video_path,
        config=intersection,
        line_names=line_names,
        model_path=str(primary_model),
        output_dir=output_dir,
        output_tag=primary_tag,
        debug_video=None,
        start_sec=start_sec,
        end_sec=end_sec,
        vid_stride=track.vid_stride,
        conf=track.conf,
        device=device,
        iou=track.iou,
        tracker_yaml=tracker_yaml,
        motion_settings=motion,
        per_line_debug=True,
    )

    payload: dict = {
        "job_id": job.id,
        "output_dir": output_dir.relative_to(PROJECT_ROOT).as_posix(),
        "primary": primary,
    }

    if job.ebike_enabled:
        ebike_model = resolve_model_preset("ebike")
        ebike = count_lines_traffic(
            video=video_path,
            config=intersection,
            line_names=line_names,
            model_path=str(ebike_model),
            output_dir=output_dir,
            output_tag="ebike",
            debug_video=None,
            start_sec=start_sec,
            end_sec=end_sec,
            vid_stride=track.vid_stride,
            conf=track.conf,
            device=device,
            iou=track.iou,
            tracker_yaml=tracker_yaml,
            motion_settings=motion,
            per_line_debug=True,
            debug_show_class=True,
        )
        payload["ebike"] = ebike

    snapshot = job.to_dict()
    snapshot_path = output_dir / "job.snapshot.yaml"
    import yaml

    with snapshot_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(snapshot, f, allow_unicode=True, sort_keys=False)
    print(f"saved: {snapshot_path}")
    return payload
