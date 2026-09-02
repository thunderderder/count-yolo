from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from count_yolo.classify import map_vehicle_class, resolve_vehicle_class_ids
from count_yolo.geometry import crossed_line, motion_matches_direction, point_in_polygon
from count_yolo.motion import MotionSettings
from count_yolo.paths import default_model
from count_yolo.summary import build_summary

try:
    import cv2
except ImportError:  # pragma: no cover - runtime extra
    cv2 = None


@dataclass
class TrackState:
    entry: str | None = None
    exit: str | None = None
    counted: bool = False
    vehicle_class: str = "car"
    last_cy: float | None = None


@dataclass
class LineTrackState:
    last_cy: float | None = None
    counted: bool = False
    vehicle_class: str = "car"
    cy_hist: list[float] = field(default_factory=list)


def load_config(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def resolve_model(path: str | None) -> str:
    if path:
        return path
    default = default_model()
    if default.is_file():
        return str(default)
    return "yolov8m.pt"


def _model_track_stream(
    model,
    video: Path,
    *,
    vehicle_class_ids: dict[int, str],
    conf: float,
    iou: float,
    vid_stride: int,
    device: str,
    tracker_yaml: str | Path | None = None,
):
    tracker = str(tracker_yaml) if tracker_yaml is not None else "bytetrack.yaml"
    return model.track(
        source=str(video),
        stream=True,
        persist=True,
        tracker=tracker,
        classes=list(vehicle_class_ids.keys()),
        conf=conf,
        iou=iou,
        vid_stride=vid_stride,
        device=device,
        verbose=False,
    )


def _require_cv2() -> None:
    if cv2 is None:
        raise ImportError("opencv-python is required to run counting. Install extras: pip install -e '.[runtime]'")


def _video_window(video: Path, start_sec: float, end_sec: float | None) -> tuple[float, int, int, int, int]:
    _require_cv2()
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise RuntimeError(f"cannot open video: {video}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    start_frame = int(start_sec * fps)
    end_frame = int(end_sec * fps) if end_sec is not None else total_frames - 1
    cap.release()
    return fps, width, height, start_frame, end_frame


@dataclass
class MultiLineTrackState:
    last_cy: float | None = None
    vehicle_class: str = "car"
    cy_hist: list[float] = field(default_factory=list)
    counted_lines: set[str] = field(default_factory=set)


def _parse_line_cfg(line_cfg: dict[str, Any], motion_settings: MotionSettings | None = None) -> dict[str, Any]:
    (x1, y1), (x2, y2) = line_cfg["line"]
    x_min, x_max = min(x1, x2), max(x1, x2)
    if "x_min" in line_cfg:
        x_min = max(x_min, float(line_cfg["x_min"]))
    if "x_max" in line_cfg:
        x_max = min(x_max, float(line_cfg["x_max"]))
    if motion_settings is not None:
        require_motion = motion_settings.line_requires_motion(line_cfg)
    else:
        require_motion = bool(line_cfg.get("require_motion_direction", True))
    return {
        "line": line_cfg["line"],
        "line_y": (y1 + y2) / 2,
        "x_min": x_min,
        "x_max": x_max,
        "direction": line_cfg.get("direction", "near_to_far"),
        "require_motion": require_motion,
        "maps_to": line_cfg["maps_to"],
        "evaluation_level": line_cfg.get("evaluation_level", "L1"),
    }


def _render_line_debug_frame(
    frame,
    line_name: str,
    line_info: dict[str, Any],
    boxes,
    ids,
    clss,
    vehicle_class_ids: dict[int, str],
    tracks: dict[int, MultiLineTrackState],
    *,
    line_total: int = 0,
    show_class: bool = False,
):
    vis = frame.copy()
    (lx1, ly1), (lx2, ly2) = line_info["line"]
    cv2.line(vis, (int(lx1), int(ly1)), (int(lx2), int(ly2)), (0, 255, 255), 3)
    visible_counted = 0
    tracking_n = 0
    x_min, x_max = line_info["x_min"], line_info["x_max"]

    for box, tid, cls_id in zip(boxes, ids, clss):
        if cls_id not in vehicle_class_ids:
            continue
        x1b, y1b, x2b, y2b = map(int, box)
        cx_i = (x1b + x2b) // 2
        if not (x_min <= cx_i <= x_max):
            continue
        cy_i = (y1b + y2b) // 2
        st = tracks.get(int(tid))
        counted = bool(st and line_name in st.counted_lines)
        if counted:
            visible_counted += 1
            color = (0, 165, 255)
            label = f"{tid} OK"
        else:
            tracking_n += 1
            color = (0, 255, 0)
            label = str(tid)
        if show_class and st:
            label = f"{label} {st.vehicle_class}"
        cv2.rectangle(vis, (x1b, y1b), (x2b, y2b), color, 2)
        cv2.circle(vis, (cx_i, cy_i), 4, color, -1)
        cv2.putText(vis, label, (x1b, max(15, y1b - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

    # line_total = cumulative crossings (monotonic). visible_counted only counts OK boxes still on screen.
    cv2.putText(
        vis,
        f"{line_name} counted={line_total} tracking={tracking_n}",
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (0, 255, 255),
        2,
    )
    return vis


def count_lines_traffic(
    video: Path,
    config: dict[str, Any],
    line_names: list[str],
    model_path: str,
    output_dir: Path,
    output_tag: str,
    debug_video: Path | None,
    start_sec: float,
    end_sec: float | None,
    vid_stride: int,
    conf: float,
    device: str,
    iou: float = 0.7,
    tracker_yaml: str | Path | None = None,
    motion_settings: MotionSettings | None = None,
    separate_passes: bool = False,
    per_line_debug: bool = False,
    debug_show_class: bool = False,
) -> dict[str, Any]:
    if separate_passes:
        results = []
        for line_name in line_names:
            out = output_dir / f"counts_{line_name}_{output_tag}.json"
            results.append(
                count_line_traffic(
                    video=video,
                    config=config,
                    line_name=line_name,
                    model_path=model_path,
                    output_json=out,
                    debug_video=debug_video,
                    start_sec=start_sec,
                    end_sec=end_sec,
                    vid_stride=vid_stride,
                    conf=conf,
                    device=device,
                    iou=iou,
                    tracker_yaml=tracker_yaml,
                    motion_settings=motion_settings,
                )
            )
        combined = {
            "intersection": config.get("name"),
            "mode": "line",
            "evaluation_level": "L1",
            "video": Path(video).name,
            "model": Path(model_path).name,
            "line_names": line_names,
            "separate_passes": True,
            "results": results,
        }
        combined_path = output_dir / f"counts_all_lines_{output_tag}.json"
        combined_path.parent.mkdir(parents=True, exist_ok=True)
        with combined_path.open("w", encoding="utf-8") as f:
            json.dump(combined, f, ensure_ascii=False, indent=2)
        return combined

    from ultralytics import YOLO

    _require_cv2()
    parsed_lines: dict[str, dict[str, Any]] = {}
    for line_name in line_names:
        line_cfg = config.get("line_counting", {}).get(line_name)
        if not line_cfg:
            raise KeyError(f"line_counting.{line_name} not in config")
        parsed_lines[line_name] = _parse_line_cfg(line_cfg, motion_settings)

    fps, width, height, start_frame, end_frame = _video_window(video, start_sec, end_sec)
    frame_area = width * height

    model = YOLO(model_path)
    vehicle_class_ids = resolve_vehicle_class_ids(getattr(model, "names", None))
    print(f"device: {device}", flush=True)
    print(f"vehicle_classes: {vehicle_class_ids}", flush=True)
    print(f"counting lines: {', '.join(line_names)}", flush=True)
    print(f"video window: frames {start_frame}..{end_frame} (fps={fps})", flush=True)

    tracks: dict[int, MultiLineTrackState] = {}
    counts_by_line: dict[str, dict[str, dict[str, int]]] = {
        name: defaultdict(lambda: defaultdict(int)) for name in line_names
    }
    detections_total = 0
    frames_processed = 0
    frame_idx = -1

    writers: dict[str, Any] = {}
    if per_line_debug:
        output_dir.mkdir(parents=True, exist_ok=True)
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out_fps = fps / max(vid_stride, 1)
        for line_name in line_names:
            debug_path = output_dir / f"debug_{line_name}_{output_tag}.mp4"
            writers[line_name] = cv2.VideoWriter(str(debug_path), fourcc, out_fps, (width, height))
            print(f"debug video: {debug_path}", flush=True)
    elif debug_video:
        debug_video.parent.mkdir(parents=True, exist_ok=True)
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writers["__combined__"] = cv2.VideoWriter(
            str(debug_video), fourcc, fps / max(vid_stride, 1), (width, height)
        )

    stream = _model_track_stream(
        model,
        video,
        vehicle_class_ids=vehicle_class_ids,
        conf=conf,
        iou=iou,
        vid_stride=vid_stride,
        device=device,
        tracker_yaml=tracker_yaml,
    )

    for result in stream:
        frame_idx += 1
        if frame_idx < start_frame:
            continue
        if frame_idx > end_frame:
            break

        frames_processed += 1
        if frames_processed == 1 or frames_processed % 300 == 0:
            pct = 100.0 * (frame_idx - start_frame + 1) / max(end_frame - start_frame + 1, 1)
            print(
                f"progress: frame {frame_idx}/{end_frame} ({pct:.1f}%), detections={detections_total}",
                flush=True,
            )
        frame = result.orig_img

        if result.boxes is None or result.boxes.id is None:
            if writers:
                for w in writers.values():
                    w.write(frame)
            continue

        boxes = result.boxes.xyxy.cpu().numpy()
        ids = result.boxes.id.cpu().numpy().astype(int)
        clss = result.boxes.cls.cpu().numpy().astype(int)

        for box, tid, cls_id in zip(boxes, ids, clss):
            if cls_id not in vehicle_class_ids:
                continue
            detections_total += 1
            x1b, y1b, x2b, y2b = box
            cx, cy = (x1b + x2b) / 2, (y1b + y2b) / 2
            area = (x2b - x1b) * (y2b - y1b)
            cls_name = vehicle_class_ids[cls_id]
            state = tracks.setdefault(tid, MultiLineTrackState())
            state.vehicle_class = map_vehicle_class(cls_name, area, frame_area)
            state.cy_hist.append(float(cy))
            if len(state.cy_hist) > 16:
                state.cy_hist.pop(0)

            if state.last_cy is not None:
                for line_name, line_info in parsed_lines.items():
                    if line_name in state.counted_lines:
                        continue
                    if not (line_info["x_min"] <= cx <= line_info["x_max"]):
                        continue
                    direction = line_info["direction"]
                    if crossed_line(state.last_cy, cy, line_info["line_y"], direction):
                        if (not line_info["require_motion"]) or motion_matches_direction(
                            state.cy_hist, direction, motion_settings
                        ):
                            maps_to = line_info["maps_to"]
                            key = f"{maps_to['entry']}|{maps_to['movement']}"
                            counts_by_line[line_name][key][state.vehicle_class] += 1
                            state.counted_lines.add(line_name)

            state.last_cy = cy

        if writers:
            if per_line_debug:
                for line_name, w in writers.items():
                    line_info = parsed_lines[line_name]
                    line_total = sum(sum(v.values()) for v in counts_by_line[line_name].values())
                    vis = _render_line_debug_frame(
                        frame,
                        line_name,
                        line_info,
                        boxes,
                        ids,
                        clss,
                        vehicle_class_ids,
                        tracks,
                        line_total=line_total,
                        show_class=debug_show_class,
                    )
                    w.write(vis)
            else:
                vis = frame.copy()
                for line_name, line_info in parsed_lines.items():
                    (lx1, ly1), (lx2, ly2) = line_info["line"]
                    cv2.line(vis, (int(lx1), int(ly1)), (int(lx2), int(ly2)), (0, 255, 255), 2)
                    total_line = sum(sum(v.values()) for v in counts_by_line[line_name].values())
                    cv2.putText(
                        vis,
                        f"{line_name}={total_line}",
                        (int(lx1), max(20, int(min(ly1, ly2)) - 10)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.55,
                        (0, 255, 255),
                        2,
                    )
                for box, tid, cls_id in zip(boxes, ids, clss):
                    if cls_id not in vehicle_class_ids:
                        continue
                    x1b, y1b, x2b, y2b = map(int, box)
                    cx_i, cy_i = (x1b + x2b) // 2, (y1b + y2b) // 2
                    st = tracks.get(int(tid))
                    counted = bool(st and st.counted_lines)
                    color = (0, 165, 255) if counted else (0, 255, 0)
                    cv2.rectangle(vis, (x1b, y1b), (x2b, y2b), color, 2)
                    cv2.circle(vis, (cx_i, cy_i), 4, color, -1)
                writers["__combined__"].write(vis)

    for w in writers.values():
        w.release()

    duration_sec = (min(frame_idx, end_frame) - start_frame + 1) / fps if frames_processed else 0.0
    per_line_payloads: list[dict[str, Any]] = []
    output_dir.mkdir(parents=True, exist_ok=True)

    for line_name in line_names:
        line_info = parsed_lines[line_name]
        maps_to = line_info["maps_to"]
        counts = counts_by_line[line_name]
        summary_rows = build_summary(counts, maps_to)
        payload = {
            "intersection": config.get("name"),
            "mode": "line",
            "evaluation_level": line_info["evaluation_level"],
            "line_name": line_name,
            "video": Path(video).name,
            "model": Path(model_path).name,
            "vehicle_classes": {str(k): v for k, v in vehicle_class_ids.items()},
            "start_sec": start_sec,
            "end_sec": end_sec,
            "duration_sec": round(duration_sec, 2),
            "fps": fps,
            "vid_stride": vid_stride,
            "frames_processed": frames_processed,
            "detections_total": detections_total,
            "line": line_info["line"],
            "direction": line_info["direction"],
            "counts": summary_rows,
            "counts_raw": {k: dict(v) for k, v in counts.items()},
        }
        out = output_dir / f"counts_{line_name}_{output_tag}.json"
        with out.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"saved: {out}")
        per_line_payloads.append(payload)

    combined = {
        "intersection": config.get("name"),
        "mode": "line",
        "evaluation_level": "L1",
        "video": Path(video).name,
        "model": Path(model_path).name,
        "line_names": line_names,
        "separate_passes": False,
        "start_sec": start_sec,
        "end_sec": end_sec,
        "duration_sec": round(duration_sec, 2),
        "fps": fps,
        "vid_stride": vid_stride,
        "frames_processed": frames_processed,
        "detections_total": detections_total,
        "results": per_line_payloads,
    }
    combined_path = output_dir / f"counts_all_lines_{output_tag}.json"
    with combined_path.open("w", encoding="utf-8") as f:
        json.dump(combined, f, ensure_ascii=False, indent=2)
    print(f"saved: {combined_path}")
    return combined


def count_line_traffic(
    video: Path,
    config: dict[str, Any],
    line_name: str,
    model_path: str,
    output_json: Path,
    debug_video: Path | None,
    start_sec: float,
    end_sec: float | None,
    vid_stride: int,
    conf: float,
    device: str,
    iou: float = 0.7,
    tracker_yaml: str | Path | None = None,
    motion_settings: MotionSettings | None = None,
) -> dict[str, Any]:
    from ultralytics import YOLO

    _require_cv2()
    line_cfg = config.get("line_counting", {}).get(line_name)
    if not line_cfg:
        raise KeyError(f"line_counting.{line_name} not in config")

    parsed = _parse_line_cfg(line_cfg, motion_settings)
    (x1, y1), (x2, y2) = parsed["line"]
    line_y = parsed["line_y"]
    x_min, x_max = parsed["x_min"], parsed["x_max"]
    direction = parsed["direction"]
    maps_to = parsed["maps_to"]
    require_motion = parsed["require_motion"]

    fps, width, height, start_frame, end_frame = _video_window(video, start_sec, end_sec)
    frame_area = width * height

    model = YOLO(model_path)
    vehicle_class_ids = resolve_vehicle_class_ids(getattr(model, "names", None))
    print(f"vehicle_classes: {vehicle_class_ids}")
    tracks: dict[int, LineTrackState] = {}
    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    key = f"{maps_to['entry']}|{maps_to['movement']}"
    detections_total = 0
    frames_processed = 0
    frame_idx = -1

    writer = None
    if debug_video:
        debug_video.parent.mkdir(parents=True, exist_ok=True)
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(debug_video), fourcc, fps / max(vid_stride, 1), (width, height))

    stream = _model_track_stream(
        model,
        video,
        vehicle_class_ids=vehicle_class_ids,
        conf=conf,
        iou=iou,
        vid_stride=vid_stride,
        device=device,
        tracker_yaml=tracker_yaml,
    )

    for result in stream:
        frame_idx += 1
        if frame_idx < start_frame:
            continue
        if frame_idx > end_frame:
            break

        frames_processed += 1
        frame = result.orig_img

        if result.boxes is None or result.boxes.id is None:
            if writer is not None:
                writer.write(frame)
            continue

        boxes = result.boxes.xyxy.cpu().numpy()
        ids = result.boxes.id.cpu().numpy().astype(int)
        clss = result.boxes.cls.cpu().numpy().astype(int)

        for box, tid, cls_id in zip(boxes, ids, clss):
            if cls_id not in vehicle_class_ids:
                continue
            detections_total += 1
            x1b, y1b, x2b, y2b = box
            cx, cy = (x1b + x2b) / 2, (y1b + y2b) / 2
            if not (x_min <= cx <= x_max):
                continue

            area = (x2b - x1b) * (y2b - y1b)
            cls_name = vehicle_class_ids[cls_id]
            state = tracks.setdefault(tid, LineTrackState())
            state.vehicle_class = map_vehicle_class(cls_name, area, frame_area)
            state.cy_hist.append(float(cy))
            if len(state.cy_hist) > 16:
                state.cy_hist.pop(0)

            if state.last_cy is not None and not state.counted:
                if crossed_line(state.last_cy, cy, line_y, direction):
                    if (not require_motion) or motion_matches_direction(
                        state.cy_hist, direction, motion_settings
                    ):
                        counts[key][state.vehicle_class] += 1
                        state.counted = True

            state.last_cy = cy

        if writer is not None:
            vis = frame.copy()
            cv2.line(vis, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 255), 3)
            total_now = sum(sum(v.values()) for v in counts.values())
            cv2.putText(
                vis,
                f"L1:{line_name} counted={total_now}",
                (30, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                (0, 255, 255),
                2,
            )
            for box, tid, cls_id in zip(boxes, ids, clss):
                if cls_id not in vehicle_class_ids:
                    continue
                x1b, y1b, x2b, y2b = map(int, box)
                cx_i, cy_i = (x1b + x2b) // 2, (y1b + y2b) // 2
                st = tracks.get(int(tid))
                counted = bool(st and st.counted)
                color = (0, 165, 255) if counted else (0, 255, 0)
                label = f"{tid}" + (" OK" if counted else "")
                cv2.rectangle(vis, (x1b, y1b), (x2b, y2b), color, 2)
                cv2.circle(vis, (cx_i, cy_i), 4, color, -1)
                cv2.putText(vis, label, (x1b, max(15, y1b - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
            writer.write(vis)

    if writer is not None:
        writer.release()

    duration_sec = (min(frame_idx, end_frame) - start_frame + 1) / fps if frames_processed else 0.0
    summary_rows = build_summary(counts, maps_to)

    payload = {
        "intersection": config.get("name"),
        "mode": "line",
        "evaluation_level": line_cfg.get("evaluation_level", "L1"),
        "line_name": line_name,
        "video": Path(video).name,
        "model": Path(model_path).name,
        "vehicle_classes": {str(k): v for k, v in vehicle_class_ids.items()},
        "start_sec": start_sec,
        "end_sec": end_sec,
        "duration_sec": round(duration_sec, 2),
        "fps": fps,
        "vid_stride": vid_stride,
        "frames_processed": frames_processed,
        "detections_total": detections_total,
        "line": line_cfg["line"],
        "direction": direction,
        "counts": summary_rows,
        "counts_raw": {k: dict(v) for k, v in counts.items()},
    }

    output_json.parent.mkdir(parents=True, exist_ok=True)
    with output_json.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return payload


def count_od_traffic(
    video: Path,
    config: dict[str, Any],
    model_path: str,
    output_json: Path,
    debug_video: Path | None,
    start_sec: float,
    end_sec: float | None,
    vid_stride: int,
    conf: float,
    device: str,
    iou: float = 0.7,
    tracker_yaml: str | Path | None = None,
) -> dict[str, Any]:
    from ultralytics import YOLO

    _require_cv2()
    entry_zones = config["zones"]["entry"]
    exit_zones = config["zones"]["exit"]
    movement_map: dict[str, dict[str, str]] = config["movement_map"]

    fps, width, height, start_frame, end_frame = _video_window(video, start_sec, end_sec)
    frame_area = width * height

    model = YOLO(model_path)
    vehicle_class_ids = resolve_vehicle_class_ids(getattr(model, "names", None))
    print(f"vehicle_classes: {vehicle_class_ids}")
    tracks: dict[int, TrackState] = {}
    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    detections_total = 0
    frames_processed = 0
    frame_idx = -1

    writer = None
    if debug_video:
        debug_video.parent.mkdir(parents=True, exist_ok=True)
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(debug_video), fourcc, fps / max(vid_stride, 1), (width, height))

    def zone_trigger(cx: float, cy: float, zones: dict[str, list]) -> str | None:
        for name, poly in zones.items():
            if point_in_polygon(cx, cy, poly):
                return name
        return None

    def finalize_track(state: TrackState) -> None:
        if state.counted or not state.entry or not state.exit:
            return
        movement_lut = movement_map.get(state.entry, {})
        movement = movement_lut.get(state.exit)
        if not movement:
            return
        key = f"{state.entry}|{movement}"
        counts[key][state.vehicle_class] += 1
        state.counted = True

    stream = _model_track_stream(
        model,
        video,
        vehicle_class_ids=vehicle_class_ids,
        conf=conf,
        iou=iou,
        vid_stride=vid_stride,
        device=device,
        tracker_yaml=tracker_yaml,
    )

    for result in stream:
        frame_idx += 1
        if frame_idx < start_frame:
            continue
        if frame_idx > end_frame:
            break

        frames_processed += 1
        frame = result.orig_img
        if result.boxes is None or result.boxes.id is None:
            if writer is not None:
                writer.write(frame)
            continue

        boxes = result.boxes.xyxy.cpu().numpy()
        ids = result.boxes.id.cpu().numpy().astype(int)
        clss = result.boxes.cls.cpu().numpy().astype(int)

        for box, tid, cls_id in zip(boxes, ids, clss):
            if cls_id not in vehicle_class_ids:
                continue
            detections_total += 1
            x1, y1, x2, y2 = box
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            area = (x2 - x1) * (y2 - y1)
            cls_name = vehicle_class_ids[cls_id]

            state = tracks.setdefault(tid, TrackState())
            state.vehicle_class = map_vehicle_class(cls_name, area, frame_area)

            hit_entry = zone_trigger(cx, cy, entry_zones)
            if state.entry is None and hit_entry:
                state.entry = hit_entry

            hit_exit = zone_trigger(cx, cy, exit_zones)
            if state.entry and hit_exit and state.exit is None:
                state.exit = hit_exit
                finalize_track(state)

        if writer is not None:
            vis = frame.copy()
            for name, poly in entry_zones.items():
                pts = np.array(poly, np.int32)
                cv2.polylines(vis, [pts], True, (0, 255, 255), 2)
            for name, poly in exit_zones.items():
                pts = np.array(poly, np.int32)
                cv2.polylines(vis, [pts], True, (255, 128, 0), 2)
            for box, tid, cls_id in zip(boxes, ids, clss):
                if cls_id not in vehicle_class_ids:
                    continue
                x1, y1, x2, y2 = map(int, box)
                cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 255, 0), 2)
            writer.write(vis)

    if writer is not None:
        writer.release()

    duration_sec = (min(frame_idx, end_frame) - start_frame + 1) / fps if frames_processed else 0.0
    summary_rows = build_summary(counts)

    payload = {
        "intersection": config.get("name"),
        "mode": "od",
        "evaluation_level": "L3",
        "video": Path(video).name,
        "model": Path(model_path).name,
        "start_sec": start_sec,
        "end_sec": end_sec,
        "duration_sec": round(duration_sec, 2),
        "fps": fps,
        "vid_stride": vid_stride,
        "frames_processed": frames_processed,
        "detections_total": detections_total,
        "counts": summary_rows,
        "counts_raw": {k: dict(v) for k, v in counts.items()},
    }

    output_json.parent.mkdir(parents=True, exist_ok=True)
    with output_json.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return payload
