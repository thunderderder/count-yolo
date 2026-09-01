from __future__ import annotations

import argparse
import json
from pathlib import Path

from count_yolo.compare import compare_counts, format_compare, load_gt, load_pred
from count_yolo.jobs import job_output_dir, load_job, resolve_job_config, resolve_job_video
from count_yolo.paths import PROJECT_ROOT, default_config, default_video, resolve_path
from count_yolo.pipeline import count_line_traffic, count_lines_traffic, count_od_traffic, load_config, resolve_model
from count_yolo.run_job import run_job as execute_job
from count_yolo.timeparse import parse_time_to_seconds, resolve_device


def _add_count_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--mode", choices=["line", "od"], default="line")
    parser.add_argument("--line", type=str, default="L1_南直行", help="line_counting key in config")
    parser.add_argument(
        "--lines",
        type=str,
        default=None,
        help="comma-separated line_counting keys; used by count-all",
    )
    parser.add_argument("--video", type=Path, default=default_video())
    parser.add_argument("--config", type=Path, default=default_config())
    parser.add_argument("--model", type=str, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--debug-video", type=Path, default=None)
    parser.add_argument("--start", type=str, default="0")
    parser.add_argument("--end", type=str, default=None)
    parser.add_argument("--max-seconds", type=float, default=None)
    parser.add_argument("--vid-stride", type=int, default=1)
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--device", type=str, default="auto", help="auto=CUDA if available, else cpu; or 0/cpu")
    parser.add_argument("--job", type=str, default=None, help="jobs/<name>.yaml task definition")


def _parse_line_names(lines_arg: str | None, config: dict, single_line: str | None = None) -> list[str]:
    if lines_arg:
        names = [part.strip() for part in lines_arg.split(",") if part.strip()]
        if not names:
            raise ValueError("empty --lines")
        return names
    line_counting = config.get("line_counting", {})
    if single_line:
        return [single_line]
    names = list(line_counting.keys())
    if not names:
        raise ValueError("no line_counting entries in config; pass --lines")
    return names


def _output_tag(model_path: str, explicit: str | None = None) -> str:
    if explicit:
        return explicit
    stem = Path(model_path).stem
    if stem == "yolov8m":
        return "8m"
    if "electri" in stem or "ebike" in stem:
        return "ebike"
    return stem


def _apply_job_defaults(args: argparse.Namespace) -> None:
    if not args.job:
        return
    job = load_job(args.job)
    if not getattr(args, "video", None) or args.video == default_video():
        if job.video:
            args.video = resolve_path(job.video)
    if not getattr(args, "config", None) or args.config == default_config():
        if job.config:
            args.config = resolve_path(job.config)
    if getattr(args, "lines", None) in (None, "") and job.lines:
        args.lines = ",".join(job.lines)
    if getattr(args, "device", None) == "auto" and job.device:
        args.device = job.device
    if getattr(args, "output_dir", None) == PROJECT_ROOT / "output":
        args.output_dir = job_output_dir(job)


def run_count_all(args: argparse.Namespace) -> int:
    _apply_job_defaults(args)
    start_sec = parse_time_to_seconds(args.start)
    end_sec = parse_time_to_seconds(args.end) if args.end else None
    if args.max_seconds is not None:
        end_sec = start_sec + args.max_seconds

    model_path = resolve_model(args.model)
    device = resolve_device(args.device)
    config = load_config(args.config)
    line_names = _parse_line_names(args.lines, config)
    output_dir = args.output_dir or (PROJECT_ROOT / "output")
    output_tag = _output_tag(model_path, args.output_tag)

    print("mode: line (count-all)")
    print(f"video: {args.video}")
    print(f"model: {model_path}")
    print(f"config: {args.config}")
    print(f"lines: {', '.join(line_names)}")
    print(f"window: {start_sec}s -> {end_sec}s, stride={args.vid_stride}, device={device}")
    print(f"separate_passes: {args.separate_passes}")

    per_line = bool(getattr(args, "per_line_debug", False) or args.job)
    payload = count_lines_traffic(
        video=args.video,
        config=config,
        line_names=line_names,
        model_path=model_path,
        output_dir=output_dir,
        output_tag=output_tag,
        debug_video=args.debug_video,
        start_sec=start_sec,
        end_sec=end_sec,
        vid_stride=args.vid_stride,
        conf=args.conf,
        device=device,
        separate_passes=args.separate_passes,
        per_line_debug=per_line,
    )

    print("counts:")
    for row in payload["results"]:
        print(f"  [{row['line_name']}]")
        for item in row["counts"]:
            print(f"    {item['entry']} {item['movement']}: {item['total']} {item['by_class']}")
    return 0


def run_count(args: argparse.Namespace) -> int:
    start_sec = parse_time_to_seconds(args.start)
    end_sec = parse_time_to_seconds(args.end) if args.end else None
    if args.max_seconds is not None:
        end_sec = start_sec + args.max_seconds

    model_path = resolve_model(args.model)
    device = resolve_device(args.device)
    config = load_config(args.config)

    output = args.output
    if output is None:
        if args.mode == "line":
            output = PROJECT_ROOT / "output" / f"counts_{args.line}.json"
        else:
            output = PROJECT_ROOT / "output" / "counts_od.json"

    print(f"mode: {args.mode}")
    print(f"video: {args.video}")
    print(f"model: {model_path}")
    print(f"config: {args.config}")
    print(f"window: {start_sec}s -> {end_sec}s, stride={args.vid_stride}, device={device}")

    if args.mode == "line":
        payload = count_line_traffic(
            video=args.video,
            config=config,
            line_name=args.line,
            model_path=model_path,
            output_json=output,
            debug_video=args.debug_video,
            start_sec=start_sec,
            end_sec=end_sec,
            vid_stride=args.vid_stride,
            conf=args.conf,
            device=device,
        )
    else:
        payload = count_od_traffic(
            video=args.video,
            config=config,
            model_path=model_path,
            output_json=output,
            debug_video=args.debug_video,
            start_sec=start_sec,
            end_sec=end_sec,
            vid_stride=args.vid_stride,
            conf=args.conf,
            device=device,
        )

    print(f"evaluation_level: {payload.get('evaluation_level')}")
    print(f"frames_processed: {payload['frames_processed']}")
    print(f"detections_total: {payload['detections_total']}")
    print("counts:")
    for row in payload["counts"]:
        print(f"  {row['entry']} {row['movement']}: {row['total']} {row['by_class']}")
    print(f"saved: {output}")
    return 0


def run_compare(args: argparse.Namespace) -> int:
    gt_all = load_gt(args.ground_truth)
    pred = load_pred(args.counts)
    with args.counts.open(encoding="utf-8") as f:
        meta = json.load(f)
    duration = float(meta.get("duration_sec") or 0)
    result = compare_counts(
        gt_all,
        pred,
        level=args.level,
        duration_sec=duration,
        full_video_sec=args.full_video_sec,
        scale_to_peak_hour=args.scale_to_peak_hour,
    )
    print(f"counts file: {args.counts} (mode={meta.get('mode')}, eval={meta.get('evaluation_level', args.level)})")
    print(format_compare(result))
    return 0 if result.overall_pass else 1


def run_job_cmd(args: argparse.Namespace) -> int:
    execute_job(args.job, video=args.video, config=args.config, conf=args.conf, vid_stride=args.vid_stride)
    return 0


def run_serve(args: argparse.Namespace) -> int:
    from count_yolo.web.server import main as serve_main

    serve_main(host=args.host, port=args.port)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Count intersection traffic from video")
    sub = parser.add_subparsers(dest="cmd")

    count_p = sub.add_parser("count", help="run YOLO counting")
    _add_count_args(count_p)

    count_all_p = sub.add_parser("count-all", help="count all configured L1 lines in one video pass")
    _add_count_args(count_all_p)
    count_all_p.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "output")
    count_all_p.add_argument("--output-tag", type=str, default=None, help="suffix for counts_<line>_<tag>.json")
    count_all_p.add_argument(
        "--separate-passes",
        action="store_true",
        help="decode video once per line (debug only; default is single pass)",
    )

    compare_p = sub.add_parser("compare", help="compare counts JSON with ground truth")
    compare_p.add_argument("--counts", type=Path, default=PROJECT_ROOT / "output" / "counts_L1_南直行.json")
    compare_p.add_argument(
        "--ground-truth",
        type=Path,
        default=PROJECT_ROOT / "ground_truth" / "文锦北路-草埔立交匝道_临时.csv",
    )
    compare_p.add_argument("--level", choices=["L1", "L2", "L3"], default="L1")
    compare_p.add_argument("--scale-to-peak-hour", action="store_true")
    compare_p.add_argument("--full-video-sec", type=float, default=22 * 60)

    sub.add_parser("annotate", help="calibrate an L1 counting line")

    run_job_p = sub.add_parser("run-job", help="run a jobs/*.yaml task (8m + optional ebike)")
    run_job_p.add_argument("--job", type=str, required=True)
    run_job_p.add_argument("--video", type=Path, default=None)
    run_job_p.add_argument("--config", type=Path, default=None)
    run_job_p.add_argument("--conf", type=float, default=0.25)
    run_job_p.add_argument("--vid-stride", type=int, default=1)

    serve_p = sub.add_parser("serve", help="local web console")
    serve_p.add_argument("--host", type=str, default="127.0.0.1")
    serve_p.add_argument("--port", type=int, default=8765)

    args, rest = parser.parse_known_args(argv)
    if args.cmd is None:
        # Compat: `python -m count_yolo --mode line ...` and root count_traffic.py
        count_parser = argparse.ArgumentParser(description="Count intersection traffic from video")
        _add_count_args(count_parser)
        return run_count(count_parser.parse_args(argv))

    if args.cmd == "count":
        return run_count(args)
    if args.cmd == "count-all":
        return run_count_all(args)
    if args.cmd == "compare":
        return run_compare(args)
    if args.cmd == "run-job":
        return run_job_cmd(args)
    if args.cmd == "serve":
        return run_serve(args)
    if args.cmd == "annotate":
        from count_yolo.annotate import main as annotate_main

        annotate_main(rest)
        return 0
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
