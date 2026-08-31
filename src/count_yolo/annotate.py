#!/usr/bin/env python3
"""在第一帧上点两个点，标定 L1 计数线并写回 config。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from count_yolo.paths import PROJECT_ROOT, default_config, default_video

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
    line = [[points[0][0], points[0][1]], [points[1][0], points[1][1]]]
    if config_path.is_file():
        with config_path.open(encoding="utf-8") as f:
            config = json.load(f)
    else:
        config = {"name": "", "zones": {"entry": {}, "exit": {}}, "movement_map": {}}

    config.setdefault("line_counting", {})
    config["line_counting"][line_name] = {
        "evaluation_level": "L1",
        "note": "annotate_line.py 标定",
        "line": line,
        "direction": direction,
        "maps_to": {
            "entry_direction": entry_direction,
            "movement": movement,
            "entry": f"{entry_direction}进口",
        },
    }

    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    save_preview.parent.mkdir(parents=True, exist_ok=True)
    preview = frame.copy()
    cv2.line(preview, points[0], points[1], (0, 255, 255), 3)
    cv2.imwrite(str(save_preview), preview)
    print(f"saved line {line} -> {config_path}")
    print(f"preview -> {save_preview}")


def run_cv2_gui(frame, line_name: str, direction: str, on_save) -> bool:
    window = "annotate_line — 左键点两个端点，n=确认 r=重置 q=退出"
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
        cv2.putText(vis, f"line: {line_name}", (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
        cv2.putText(vis, "LMB x2 | n=save r=reset q=quit", (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (220, 220, 220), 2)
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


def run_mpl_gui(frame, line_name: str, on_save) -> bool:
    import matplotlib.pyplot as plt

    points: list[tuple[int, int]] = []
    fig, ax = plt.subplots(figsize=(14, 8))
    ax.imshow(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    ax.set_title(f"{line_name} — 点两个端点，然后点 Save 或按 Enter")
    line_artist, = ax.plot([], [], color="cyan", linewidth=2)
    scatter = ax.scatter([], [], c="yellow", s=80)

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


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="交互标定 L1 计数线")
    parser.add_argument("--video", type=Path, default=default_video())
    parser.add_argument("--image", type=Path, default=None, help="直接用截图，不抽视频帧")
    parser.add_argument("--frame", type=int, default=1440, help="取第几帧（默认约 60s）")
    parser.add_argument("--config", type=Path, default=default_config())
    parser.add_argument("--line", type=str, default="L1_南直行")
    parser.add_argument("--direction", choices=["near_to_far", "far_to_near"], default="near_to_far")
    parser.add_argument("--entry-direction", type=str, default="南")
    parser.add_argument("--movement", type=str, default="直行")
    parser.add_argument("--save-preview", type=Path, default=PROJECT_ROOT / "output" / "line_preview.jpg")
    parser.add_argument("--backend", choices=["auto", "cv2", "mpl"], default="auto")
    args = parser.parse_args(argv)

    if cv2 is None:
        raise ImportError("opencv-python is required. Install extras: pip install -e '.[runtime]'")

    if args.image and args.image.is_file():
        frame = cv2.imread(str(args.image))
    else:
        frame = extract_frame(args.video, args.frame)
    if frame is None:
        raise RuntimeError("no frame to annotate")

    saved_flag = {"ok": False}

    def handle_save(points: list[tuple[int, int]]) -> None:
        save_line(
            args.config,
            args.line,
            args.direction,
            args.entry_direction,
            args.movement,
            points,
            frame,
            args.save_preview,
        )
        saved_flag["ok"] = True

    backend = args.backend
    if backend == "auto":
        backend = "cv2" if cv2_gui_available() else "mpl"
        if backend == "mpl":
            print("OpenCV 窗口不可用，改用 matplotlib 标定（点两个点后 Save 或 Enter）")

    if backend == "cv2":
        saved_flag["ok"] = run_cv2_gui(frame, args.line, args.direction, handle_save)
    else:
        saved_flag["ok"] = run_mpl_gui(frame, args.line, handle_save)

    if not saved_flag["ok"]:
        print("未保存（需要两个点并确认）")


if __name__ == "__main__":
    main()
