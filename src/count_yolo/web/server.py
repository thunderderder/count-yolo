from __future__ import annotations

import mimetypes
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from count_yolo.jobs import Job, job_output_dir, list_job_ids, load_job, save_job
from count_yolo.paths import JOBS_DIR, PROJECT_ROOT, resolve_path, safe_output_path
from count_yolo.pipeline import load_config
from count_yolo.preview import render_line_overlay
from count_yolo.timeparse import probe_device

try:
    import cv2
except ImportError:  # pragma: no cover
    cv2 = None

WEB_DIR = Path(__file__).resolve().parent / "static"
_run_proc: subprocess.Popen | None = None
_run_log_path: Path | None = None
_annotate_proc: subprocess.Popen | None = None
_annotate_log_path: Path | None = None


def spawn_project_script(script_name: str, args: list[str], log_path: Path) -> subprocess.Popen:
    """Launch via repo-root compat scripts (same as run.ps1), not ``python -m count_yolo``."""
    script = PROJECT_ROOT / script_name
    if not script.is_file():
        raise FileNotFoundError(f"project script not found: {script}")
    log_f = log_path.open("w", encoding="utf-8")
    cmd = [sys.executable, "-u", str(script), *args]
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    return subprocess.Popen(
        cmd,
        cwd=str(PROJECT_ROOT),
        stdout=log_f,
        stderr=subprocess.STDOUT,
        env=env,
    )


class JobPayload(BaseModel):
    video: str = ""
    config: str = ""
    lines: list[str] = Field(default_factory=list)
    model: str = "8m"
    device: str = "auto"
    start: float = 0
    end: float | None = None
    output_dir: str | None = None
    ground_truth: str | None = None
    ebike_enabled: bool = False
    preview_seconds: int | None = None
    note: str = ""
    conf: float = 0.25
    iou: float = 0.7
    vid_stride: int = 1
    track_buffer: int = 30
    track_high_thresh: float = 0.25
    track_low_thresh: float = 0.1
    new_track_thresh: float = 0.25
    match_thresh: float = 0.8
    fuse_score: bool = True


class AnnotatePayload(BaseModel):
    lines: list[str] = Field(default_factory=list)
    frame: int = 1440
    video: str | None = None
    config: str | None = None


class OpenLocalPayload(BaseModel):
    name: str | None = None
    folder: bool = False


def create_app() -> FastAPI:
    app = FastAPI(title="count-yolo console", version="0.1.0")

    @app.get("/", response_class=HTMLResponse)
    def index() -> HTMLResponse:
        html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
        return HTMLResponse(html)

    @app.get("/api/device")
    def api_device() -> dict[str, Any]:
        return probe_device()

    @app.get("/api/jobs")
    def api_list_jobs() -> dict[str, list[str]]:
        return {"jobs": list_job_ids()}

    @app.get("/api/jobs/{job_id}")
    def api_get_job(job_id: str) -> dict[str, Any]:
        try:
            job = load_job(job_id)
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc
        return {"id": job.id, **job.to_dict()}

    @app.put("/api/jobs/{job_id}")
    def api_put_job(job_id: str, body: JobPayload) -> dict[str, Any]:
        job = Job.from_dict(job_id, body.model_dump())
        save_job(job)
        return {"id": job.id, **job.to_dict()}

    @app.get("/api/jobs/{job_id}/lines")
    def api_job_lines(job_id: str) -> dict[str, Any]:
        job = load_job(job_id)
        if not job.config:
            raise HTTPException(400, "job.config is empty")
        config_path = PROJECT_ROOT / job.config
        if not config_path.is_file():
            raise HTTPException(404, f"config not found: {job.config}")
        cfg = load_config(config_path)
        keys = list(cfg.get("line_counting", {}).keys())
        return {"lines": keys}

    @app.get("/api/jobs/{job_id}/artifacts")
    def api_artifacts(job_id: str) -> dict[str, Any]:
        job = load_job(job_id)
        out = job_output_dir(job)
        if not out.is_dir():
            return {
                "output_dir": str(out.relative_to(PROJECT_ROOT)),
                "output_dir_absolute": str(out.resolve()),
                "files": [],
            }
        files = []
        for path in sorted(out.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(PROJECT_ROOT).as_posix()
            kind = "other"
            low = path.name.lower()
            if low.endswith(".mp4"):
                kind = "video"
            elif low.endswith((".jpg", ".jpeg", ".png")):
                kind = "image"
            elif low.endswith(".json"):
                kind = "json"
            elif low.endswith((".yaml", ".yml")):
                kind = "yaml"
            files.append(
                {
                    "name": path.name,
                    "path": rel,
                    "absolute": str(path.resolve()),
                    "kind": kind,
                }
            )
        return {
            "output_dir": out.relative_to(PROJECT_ROOT).as_posix(),
            "output_dir_absolute": str(out.resolve()),
            "files": files,
        }

    @app.post("/api/jobs/{job_id}/open-local")
    def api_open_local(job_id: str, body: OpenLocalPayload) -> dict[str, str]:
        job = load_job(job_id)
        out = job_output_dir(job).resolve()
        if not out.is_dir():
            raise HTTPException(404, "output dir not found")
        if body.folder:
            target = out
        else:
            if not body.name:
                raise HTTPException(400, "name required")
            target = (out / body.name).resolve()
            if not target.is_file():
                raise HTTPException(404, f"file not found: {body.name}")
            if out not in target.parents and target != out:
                raise HTTPException(403, "forbidden")
        try:
            if sys.platform == "win32":
                os.startfile(str(target))  # noqa: S606
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(target)])  # noqa: S603
            else:
                subprocess.Popen(["xdg-open", str(target)])  # noqa: S603
        except OSError as exc:
            raise HTTPException(500, f"cannot open: {exc}") from exc
        return {"opened": str(target)}

    @app.get("/api/jobs/{job_id}/overlay.jpg")
    def api_overlay(job_id: str, frame: int = 1440):
        if cv2 is None:
            raise HTTPException(500, "opencv not installed")
        job = load_job(job_id)
        if not job.config:
            raise HTTPException(400, "job.config is empty")
        cfg_path = resolve_path(job.config)
        if not cfg_path.is_file():
            raise HTTPException(404, f"config not found: {job.config}")
        cfg = load_config(cfg_path)
        line_entries = cfg.get("line_counting", {})
        if not line_entries:
            raise HTTPException(400, "no line_counting in config; run annotate first")
        video_path = resolve_path(job.video)
        if not video_path.is_file():
            raise HTTPException(404, f"video not found: {job.video}")
        cap = cv2.VideoCapture(str(video_path))
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame)
        ok, img = cap.read()
        cap.release()
        if not ok:
            raise HTTPException(400, f"cannot read frame {frame}")
        vis = render_line_overlay(img, line_entries)
        out = job_output_dir(job) / "line_overlay.jpg"
        out.parent.mkdir(parents=True, exist_ok=True)
        encoded, buf = cv2.imencode(".jpg", vis)
        if not encoded:
            raise HTTPException(500, "failed to encode overlay image")
        out.write_bytes(buf.tobytes())
        return FileResponse(out, media_type="image/jpeg")

    @app.post("/api/jobs/{job_id}/annotate")
    def api_annotate_job(job_id: str, body: AnnotatePayload) -> dict[str, str]:
        global _annotate_proc, _annotate_log_path
        if _annotate_proc is not None and _annotate_proc.poll() is None:
            raise HTTPException(409, "annotate already in progress")
        if _run_proc is not None and _run_proc.poll() is None:
            raise HTTPException(409, "count run in progress")

        from count_yolo.annotate import cv2_gui_available

        if not cv2_gui_available():
            raise HTTPException(
                503,
                "OpenCV 窗口不可用（需在本机桌面环境运行 serve，且安装带 GUI 的 opencv）",
            )

        try:
            job = load_job(job_id)
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc

        if body.video is not None:
            job.video = body.video.strip()
        if body.config is not None:
            job.config = body.config.strip()
        if not job.video:
            raise HTTPException(400, "video path required")
        if not body.lines:
            raise HTTPException(400, "lines required (comma-separated line names)")
        if not job.config:
            job.config = f"configs/{job_id}.json"

        video_path = resolve_path(job.video)
        if not video_path.is_file():
            raise HTTPException(404, f"video not found: {job.video}")

        config_path = resolve_path(job.config)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        save_job(job)

        out = job_output_dir(job)
        out.mkdir(parents=True, exist_ok=True)
        _annotate_log_path = out / "annotate.log"
        lines_csv = ",".join(body.lines)
        cmd_args = [
            "--video",
            str(video_path),
            "--config",
            str(config_path),
            "--lines",
            lines_csv,
            "--job",
            job_id,
            "--frame",
            str(body.frame),
            "--backend",
            "cv2",
        ]
        _annotate_proc = spawn_project_script("annotate_line.py", cmd_args, _annotate_log_path)
        cmd = [sys.executable, str(PROJECT_ROOT / "annotate_line.py"), *cmd_args]
        return {
            "status": "started",
            "command": " ".join(cmd),
            "log": _annotate_log_path.relative_to(PROJECT_ROOT).as_posix(),
            "config": job.config,
        }

    @app.get("/api/annotate/status")
    def api_annotate_status() -> dict[str, Any]:
        global _annotate_proc, _annotate_log_path
        if _annotate_proc is None:
            return {"running": False, "exit_code": None, "log_tail": ""}
        code = _annotate_proc.poll()
        log = ""
        if _annotate_log_path and _annotate_log_path.is_file():
            log = _annotate_log_path.read_text(encoding="utf-8", errors="replace")
        if len(log) > 12000:
            log = log[-12000:]
        return {"running": code is None, "exit_code": code, "log_tail": log}

    @app.post("/api/run/stop")
    def api_run_stop() -> dict[str, Any]:
        global _run_proc, _run_log_path, _annotate_proc, _annotate_log_path
        stopped: list[str] = []
        if _run_proc is not None and _run_proc.poll() is None:
            _run_proc.terminate()
            try:
                _run_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                _run_proc.kill()
            stopped.append("run")
        if _annotate_proc is not None and _annotate_proc.poll() is None:
            _annotate_proc.terminate()
            try:
                _annotate_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                _annotate_proc.kill()
            stopped.append("annotate")
        code = _run_proc.poll() if _run_proc is not None else None
        return {"stopped": stopped, "exit_code": code}

    @app.post("/api/jobs/{job_id}/run")
    def api_run_job(job_id: str) -> dict[str, str]:
        global _run_proc, _run_log_path
        if _annotate_proc is not None and _annotate_proc.poll() is None:
            raise HTTPException(409, "annotate in progress")
        if _run_proc is not None and _run_proc.poll() is None:
            raise HTTPException(409, "another run is in progress")
        job = load_job(job_id)
        out = job_output_dir(job)
        out.mkdir(parents=True, exist_ok=True)
        _run_log_path = out / "run.log"
        _run_proc = spawn_project_script("count_traffic.py", ["run-job", "--job", job_id], _run_log_path)
        cmd = [sys.executable, str(PROJECT_ROOT / "count_traffic.py"), "run-job", "--job", job_id]
        return {"status": "started", "command": " ".join(cmd), "log": _run_log_path.relative_to(PROJECT_ROOT).as_posix()}

    @app.get("/api/run/status")
    def api_run_status() -> dict[str, Any]:
        global _run_proc, _run_log_path
        if _run_proc is None:
            return {"running": False, "exit_code": None, "log_tail": ""}
        code = _run_proc.poll()
        log = ""
        if _run_log_path and _run_log_path.is_file():
            log = _run_log_path.read_text(encoding="utf-8", errors="replace")
        if len(log) > 12000:
            log = log[-12000:]
        return {"running": code is None, "exit_code": code, "log_tail": log}

    @app.get("/media/{file_path:path}")
    def media(file_path: str):
        try:
            target = safe_output_path(PROJECT_ROOT / file_path)
        except ValueError as exc:
            raise HTTPException(403, str(exc)) from exc
        if not target.is_file():
            raise HTTPException(404, "not found")
        allowed_roots = [
            (PROJECT_ROOT / "output").resolve(),
            (PROJECT_ROOT / "jobs").resolve(),
        ]
        if not any(root == target or root in target.parents for root in allowed_roots):
            raise HTTPException(403, "forbidden")
        mime, _ = mimetypes.guess_type(str(target))
        return FileResponse(target, media_type=mime or "application/octet-stream")

    if WEB_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")

    return app


def main(host: str = "127.0.0.1", port: int = 8765) -> None:
    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover
        raise ImportError("install runtime extras: pip install -e '.[runtime]'") from exc

    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    app = create_app()
    print(f"count-yolo console: http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")
