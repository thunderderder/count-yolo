#!/usr/bin/env python3
"""在第一帧上点两个端点，标定 L1 计数线并写回 config。"""

from __future__ import annotations

import argparse
import json
import os
import sys
from functools import lru_cache
from pathlib import Path

from count_yolo.paths import PROJECT_ROOT, default_config, default_video
from count_yolo.preview import LINE_COLORS_BGR, draw_saved_lines, write_calibration_preview

try:
    import cv2
except ImportError:  # pragma: no cover
    cv2 = None


def cv2_gui_available() -> bool:
    if cv2 is None:
        return False
    try:
        cv2.namedWindow("__annotate_test__", cv2.WINDOW_NORMAL)
        cv2.destroyWindow("__annotate_test__")
        return True
    except cv2.error:
        return False


def extract_frame(video: Path, frame_index: int):
    if cv2 is None:
        raise ImportError("opencv-python is required. Install extras: pip install -e '.[runtime]'")
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise RuntimeError(f"cannot open video: {video}")
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        raise RuntimeError(f"cannot read frame {frame_index}")
    return frame


def parse_line_names(lines_arg: str | None, single_line: str) -> list[str]:
    if lines_arg:
        names = [part.strip() for part in lines_arg.split(",") if part.strip()]
        if not names:
            raise ValueError("empty --lines")
        return names
    return [single_line]


def entry_direction_from_line_name(line_name: str) -> str:
    if line_name.startswith("L1_"):
        return line_name[3:]
    return line_name


def load_config(config_path: Path) -> dict:
    if config_path.is_file():
        with config_path.open(encoding="utf-8") as f:
            return json.load(f)
    return {"name": "", "zones": {"entry": {}, "exit": {}}, "movement_map": {}}


def build_line_entry(
    line_name: str,
    direction: str,
    entry_direction: str | None,
    movement: str,
    points: list[tuple[int, int]],
) -> dict:
    entry_dir = entry_direction or entry_direction_from_line_name(line_name)
    return {
        "evaluation_level": "L1",
        "note": "annotate_line.py 标定",
        "line": [[points[0][0], points[0][1]], [points[1][0], points[1][1]]],
        "direction": direction,
        "require_motion_direction": True,
        "maps_to": {
            "entry_direction": entry_dir,
            "movement": movement,
            "entry": f"{entry_dir}进口",
        },
    }


def save_lines(
    config_path: Path,
    line_entries: dict[str, dict],
    frame,
    save_preview: Path,
    calibration_mp4: Path | None = None,
) -> None:
    config = load_config(config_path)
    # Each annotate session replaces all L1 lines (no merge with stale names).
    config["line_counting"] = dict(line_entries)

    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    if cv2 is not None:
        save_preview.parent.mkdir(parents=True, exist_ok=True)
        preview = frame.copy()
        for idx, entry in enumerate(line_entries.values()):
            (x1, y1), (x2, y2) = entry["line"]
            color = LINE_COLORS_BGR[idx % len(LINE_COLORS_BGR)]
            cv2.line(preview, (int(x1), int(y1)), (int(x2), int(y2)), color, 3)

        cv2.imwrite(str(save_preview), preview)
        print(f"preview -> {save_preview}")

    print(f"saved {len(line_entries)} line(s) -> {config_path}")

    if calibration_mp4 is not None:
        pts = {
            name: [(int(entry["line"][0][0]), int(entry["line"][0][1])), (int(entry["line"][1][0]), int(entry["line"][1][1]))]
            for name, entry in line_entries.items()
        }
        write_calibration_preview(frame, pts, calibration_mp4)
        print(f"calibration preview -> {calibration_mp4}")


def save_line(
    config_path: Path,
    line_name: str,
    direction: str,
    entry_direction: str,
    movement: str,
    points: list[tuple[int, int]],
    frame,
    save_preview: Path,
) -> None:
    save_lines(
        config_path,
        {
            line_name: build_line_entry(
                line_name,
                direction,
                entry_direction,
                movement,
                points,
            )
        },
        frame,
        save_preview,
    )


ANNOTATE_HELP_LINES = [
    "标定说明：左键点两个端点画计数线",
    "n=确认保存  r=重置当前线  q/Esc=取消",
]

ANNOTATE_MULTI_HELP_LINES = [
    "标定说明：左键点两个端点画计数线",
    "n=确认当前线并进入下一条  r=重置  q/Esc=取消",
]

CV2_WINDOW_TITLE = "count-yolo annotate"


@lru_cache(maxsize=8)
def _cjk_font(size: int):
    from PIL import ImageFont

    env_font = os.environ.get("COUNT_YOLO_ANNOTATE_FONT")
    if env_font and Path(env_font).is_file():
        return ImageFont.truetype(env_font, size=size)

    font_dirs: list[Path] = []
    if sys.platform == "win32":
        font_dirs.append(Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts")
    font_dirs.extend(
        [
            Path("/usr/share/fonts/opentype/noto"),
            Path("/usr/share/fonts/truetype/noto"),
            Path("/System/Library/Fonts"),
        ]
    )
    names = [
        "msyh.ttc",
        "msyhbd.ttc",
        "simhei.ttf",
        "simsun.ttc",
        "NotoSansCJK-Regular.ttc",
        "PingFang.ttc",
    ]
    for root in font_dirs:
        for name in names:
            path = root / name
            if path.is_file():
                return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def _draw_text_block(
    img_bgr,
    lines: list[str],
    origin: tuple[int, int],
    *,
    font_size: int = 22,
    color_bgr: tuple[int, int, int] = (255, 255, 255),
    line_gap: int = 6,
    bg_bgr: tuple[int, int, int] | None = (20, 20, 20),
) -> None:
    if not lines:
        return
    try:
        import numpy as np
        from PIL import Image, ImageDraw
    except ImportError:
        y = origin[1]
        for line in lines:
            cv2.putText(img_bgr, line, (origin[0], y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color_bgr, 2)
            y += font_size + line_gap
        return

    font = _cjk_font(font_size)
    rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    pil = Image.fromarray(rgb)
    draw = ImageDraw.Draw(pil)
    color_rgb = (color_bgr[2], color_bgr[1], color_bgr[0])
    x, y = origin
    boxes: list[tuple[str, tuple[int, int, int, int]]] = []
    for line in lines:
        bbox = draw.textbbox((x, y), line, font=font)
        boxes.append((line, bbox))
        y = bbox[3] + line_gap
    if bg_bgr and boxes:
        bg_rgb = (bg_bgr[2], bg_bgr[1], bg_bgr[0])
        pad = 6
        x1 = min(b[0] for _, b in boxes) - pad
        y1 = boxes[0][1][1] - pad
        x2 = max(b[2] for _, b in boxes) + pad
        y2 = boxes[-1][1][3] + pad
        draw.rectangle([x1, y1, x2, y2], fill=bg_rgb)
    y = origin[1]
    for line in lines:
        draw.text((x, y), line, font=font, fill=color_rgb)
        bbox = draw.textbbox((x, y), line, font=font)
        y = bbox[3] + line_gap
    img_bgr[:] = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)


def _draw_help_text(vis, lines: list[str] | None = None, start_y: int = 100) -> None:
    _draw_text_block(
        vis,
        lines or ANNOTATE_HELP_LINES,
        (20, start_y),
        font_size=20,
        color_bgr=(180, 220, 255),
    )


def run_cv2_gui(frame, line_name: str, direction: str, on_save) -> bool:
    window = CV2_WINDOW_TITLE
    points: list[tuple[int, int]] = []

    def on_mouse(event: int, x: int, y: int, _flags: int, _userdata) -> None:
        nonlocal points
        if event != cv2.EVENT_LBUTTONDOWN:
            return
        if len(points) >= 2:
            points = []
        points.append((x, y))

    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window, 1280, 720)
    cv2.setMouseCallback(window, on_mouse)

    saved = False
    while True:
        vis = frame.copy()
        for i, (x, y) in enumerate(points):
            cv2.circle(vis, (x, y), 8, (0, 255, 255), -1)
            cv2.putText(vis, f"P{i+1}", (x + 10, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        if len(points) == 2:
            cv2.line(vis, points[0], points[1], (0, 255, 255), 3)
        _draw_text_block(vis, [f"断面: {line_name}"], (20, 20), font_size=24, color_bgr=(255, 255, 255))
        _draw_help_text(vis)
        cv2.imshow(window, vis)
        key = cv2.waitKey(20) & 0xFF
        if key in (ord("q"), 27):
            break
        if key == ord("r"):
            points = []
        if key == ord("n") and len(points) == 2:
            on_save(points)
            saved = True
            break

    cv2.destroyAllWindows()
    return saved


def run_cv2_multi_gui(frame, line_names: list[str], direction: str, on_save_all) -> bool:
    window = CV2_WINDOW_TITLE
    saved_lines: dict[str, list[tuple[int, int]]] = {}
    line_idx = 0
    points: list[tuple[int, int]] = []

    def on_mouse(event: int, x: int, y: int, _flags: int, _userdata) -> None:
        nonlocal points
        if event != cv2.EVENT_LBUTTONDOWN:
            return
        if len(points) >= 2:
            points = []
        points.append((x, y))

    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window, 1280, 720)
    cv2.setMouseCallback(window, on_mouse)

    saved = False
    while True:
        current_name = line_names[line_idx]
        color = LINE_COLORS_BGR[line_idx % len(LINE_COLORS_BGR)]
        vis = frame.copy()
        draw_saved_lines(vis, saved_lines)
        for i, (x, y) in enumerate(points):
            cv2.circle(vis, (x, y), 8, color, -1)
            cv2.putText(vis, f"P{i+1}", (x + 10, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        if len(points) == 2:
            cv2.line(vis, points[0], points[1], color, 3)
        _draw_text_block(
            vis,
            [f"断面 {line_idx + 1}/{len(line_names)}: {current_name}"],
            (20, 20),
            font_size=24,
            color_bgr=(255, 255, 255),
        )
        _draw_help_text(vis, ANNOTATE_MULTI_HELP_LINES)
        cv2.imshow(window, vis)
        key = cv2.waitKey(20) & 0xFF
        if key in (ord("q"), 27):
            break
        if key == ord("r"):
            points = []
        if key == ord("n") and len(points) == 2:
            saved_lines[current_name] = [points[0], points[1]]
            points = []
            line_idx += 1
            if line_idx >= len(line_names):
                on_save_all(saved_lines)
                saved = True
                break

    cv2.destroyAllWindows()
    return saved


def run_mpl_gui(frame, line_name: str, on_save) -> bool:
    import matplotlib.pyplot as plt

    points: list[tuple[int, int]] = []
    fig, ax = plt.subplots(figsize=(14, 8))
    ax.imshow(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    ax.set_title(f"{line_name} — 点两个端点，然后点 Save 或按 Enter")
    line_artist, = ax.plot([], [], color="cyan", linewidth=2)
    scatter = ax.scatter([], [], s=80)

    def refresh() -> None:
        if points:
            xs, ys = zip(*points)
            scatter.set_offsets(list(zip(xs, ys)))
            if len(points) == 2:
                line_artist.set_data([points[0][0], points[1][0]], [points[0][1], points[1][1]])
            else:
                line_artist.set_data([], [])
        fig.canvas.draw_idle()

    def onclick(event) -> None:
        nonlocal points
        if event.inaxes != ax or event.xdata is None or event.ydata is None:
            return
        if len(points) >= 2:
            points = []
        points.append((int(event.xdata), int(event.ydata)))
        refresh()

    def on_key(event) -> None:
        if event.key == "r":
            points.clear()
            refresh()
        if event.key in ("enter", "n") and len(points) == 2:
            on_save(points)
            plt.close(fig)

    def on_save_click(_event) -> None:
        if len(points) == 2:
            on_save(points)
            plt.close(fig)

    fig.canvas.mpl_connect("button_press_event", onclick)
    fig.canvas.mpl_connect("key_press_event", on_key)
    ax_btn = plt.axes([0.82, 0.02, 0.12, 0.05])
    btn = plt.Button(ax_btn, "Save")
    btn.on_clicked(on_save_click)
    refresh()
    plt.show()
    return len(points) == 2


def run_mpl_multi_gui(frame, line_names: list[str], on_save_all) -> bool:
    import matplotlib.pyplot as plt

    saved_lines: dict[str, list[tuple[int, int]]] = {}
    line_idx = 0
    points: list[tuple[int, int]] = []
    fig, ax = plt.subplots(figsize=(14, 8))
    ax.imshow(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    artists: list = []

    def refresh() -> None:
        nonlocal artists
        for artist in artists:
            artist.remove()
        artists = []
        for idx, (name, pts) in enumerate(saved_lines.items()):
            color = ["cyan", "orange", "lime", "magenta", "yellow", "white"][idx % 6]
            line, = ax.plot([pts[0][0], pts[1][0]], [pts[0][1], pts[1][1]], color=color, linewidth=2)
            artists.append(line)
            artists.append(ax.text((pts[0][0] + pts[1][0]) / 2, (pts[0][1] + pts[1][1]) / 2 - 8, name, color=color))
        if points:
            xs, ys = zip(*points)
            artists.append(ax.scatter(xs, ys, c="yellow", s=80))
            if len(points) == 2:
                artists.append(
                    ax.plot([points[0][0], points[1][0]], [points[0][1], points[1][1]], color="yellow", linewidth=2)[0]
                )
        current_name = line_names[line_idx]
        ax.set_title(f"{line_idx + 1}/{len(line_names)} {current_name} — 点两个端点，Enter 下一条")
        fig.canvas.draw_idle()

    def onclick(event) -> None:
        nonlocal points
        if event.inaxes != ax or event.xdata is None or event.ydata is None:
            return
        if len(points) >= 2:
            points = []
        points.append((int(event.xdata), int(event.ydata)))
        refresh()

    def advance_line() -> None:
        nonlocal line_idx, points
        if len(points) != 2:
            return
        saved_lines[line_names[line_idx]] = [points[0], points[1]]
        points = []
        line_idx += 1
        if line_idx >= len(line_names):
            on_save_all(saved_lines)
            plt.close(fig)
            return
        refresh()

    def on_key(event) -> None:
        if event.key == "r":
            points.clear()
            refresh()
        if event.key in ("enter", "n"):
            advance_line()

    fig.canvas.mpl_connect("button_press_event", onclick)
    fig.canvas.mpl_connect("key_press_event", on_key)
    ax_btn = plt.axes([0.82, 0.02, 0.12, 0.05])
    btn = plt.Button(ax_btn, "Next line")
    btn.on_clicked(lambda _event: advance_line())
    refresh()
    plt.show()
    return len(saved_lines) == len(line_names)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="交互标定 L1 计数线")
    parser.add_argument("--video", type=Path, default=default_video())
    parser.add_argument("--image", type=Path, default=None, help="直接用截图，不抽视频帧")
    parser.add_argument("--frame", type=int, default=1440, help="取第几帧（默认约 60s）")
    parser.add_argument("--config", type=Path, default=default_config())
    parser.add_argument("--line", type=str, default="L1_南直行", help="单条线名称")
    parser.add_argument(
        "--lines",
        type=str,
        default=None,
        help="多条线名称，逗号分隔，如 L1_主路,L1_匝道,L1_右路",
    )
    parser.add_argument("--direction", choices=["near_to_far", "far_to_near"], default="near_to_far")
    parser.add_argument("--entry-direction", type=str, default=None)
    parser.add_argument("--movement", type=str, default="断面")
    parser.add_argument("--job", type=str, default=None, help="写入 output/jobs/<job>/calibration_preview_10s.mp4")
    parser.add_argument("--save-preview", type=Path, default=PROJECT_ROOT / "output" / "line_preview.jpg")
    parser.add_argument("--backend", choices=["auto", "cv2", "mpl"], default="auto")
    args = parser.parse_args(argv)

    if cv2 is None:
        raise ImportError("opencv-python is required. Install extras: pip install -e '.[runtime]'")

    def calibration_mp4_path() -> Path:
        if args.job:
            from count_yolo.jobs import job_output_dir, load_job

            return job_output_dir(load_job(args.job)) / "calibration_preview_10s.mp4"
        return args.save_preview.parent / "calibration_preview_10s.mp4"

    calib_mp4 = calibration_mp4_path()

    line_names = parse_line_names(args.lines, args.line)
    multi = len(line_names) > 1

    if args.image and args.image.is_file():
        frame = cv2.imread(str(args.image))
    else:
        frame = extract_frame(args.video, args.frame)
    if frame is None:
        raise RuntimeError("no frame to annotate")

    saved_flag = {"ok": False}

    def handle_save(points: list[tuple[int, int]]) -> None:
        entry = build_line_entry(
            line_names[0],
            args.direction,
            args.entry_direction or entry_direction_from_line_name(line_names[0]),
            args.movement,
            points,
        )
        save_lines(
            args.config,
            {line_names[0]: entry},
            frame,
            args.save_preview,
            calibration_mp4=calib_mp4,
        )
        saved_flag["ok"] = True

    def handle_save_all(saved: dict[str, list[tuple[int, int]]]) -> None:
        entries = {
            name: build_line_entry(
                name,
                args.direction,
                args.entry_direction,
                args.movement,
                pts,
            )
            for name, pts in saved.items()
        }
        save_lines(args.config, entries, frame, args.save_preview, calibration_mp4=calib_mp4)
        saved_flag["ok"] = True

    backend = args.backend
    if backend == "auto":
        backend = "cv2" if cv2_gui_available() else "mpl"
        if backend == "mpl":
            print("OpenCV 窗口不可用，改用 matplotlib 标定（点两个点后 Save/Enter）")

    print("=" * 60)
    print("count-yolo 断面标定")
    print("  左键：点两个端点画计数线")
    print("  n：确认当前线（多线时进入下一条，全部画完自动保存到 config）")
    print("  r：重置当前正在画的线")
    print("  q / Esc：退出（未确认的不保存）")
    print("=" * 60)

    if multi:
        print(f"多线标定: {', '.join(line_names)}")
        if backend == "cv2":
            saved_flag["ok"] = run_cv2_multi_gui(frame, line_names, args.direction, handle_save_all)
        else:
            saved_flag["ok"] = run_mpl_multi_gui(frame, line_names, handle_save_all)
    elif backend == "cv2":
        saved_flag["ok"] = run_cv2_gui(frame, line_names[0], args.direction, handle_save)
    else:
        saved_flag["ok"] = run_mpl_gui(frame, line_names[0], handle_save)

    if not saved_flag["ok"]:
        print("未保存（需要两个点并确认）")


if __name__ == "__main__":
    main()
