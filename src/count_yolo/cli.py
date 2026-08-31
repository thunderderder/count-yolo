from __future__ import annotations

import argparse
import json
from pathlib import Path

from count_yolo.compare import compare_counts, format_compare, load_gt, load_pred
from count_yolo.paths import PROJECT_ROOT, default_config, default_video
from count_yolo.pipeline import count_line_traffic, count_od_traffic, load_config, resolve_model
from count_yolo.timeparse import parse_time_to_seconds, resolve_device


def _add_count_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--mode", choices=["line", "od"], default="line")
    parser.add_argument("--line", type=str, default="L1_南直行", help="line_counting key in config")
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Count intersection traffic from video")
    sub = parser.add_subparsers(dest="cmd")

    count_p = sub.add_parser("count", help="run YOLO counting")
    _add_count_args(count_p)

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

    args, rest = parser.parse_known_args(argv)
    if args.cmd is None:
        # Compat: `python -m count_yolo --mode line ...` and root count_traffic.py
        count_parser = argparse.ArgumentParser(description="Count intersection traffic from video")
        _add_count_args(count_parser)
        return run_count(count_parser.parse_args(argv))

    if args.cmd == "count":
        return run_count(args)
    if args.cmd == "compare":
        return run_compare(args)
    if args.cmd == "annotate":
        from count_yolo.annotate import main as annotate_main

        annotate_main(rest)
        return 0
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
