from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path

LEVEL_KEYS: dict[str, list[tuple[str, str]] | None] = {
    "L1": [("南", "直行")],
    "L2": [("东", "左转")],
    "L3": None,
}

LEVEL_TOLERANCE: dict[str, float] = {
    "L1": 15.0,
    "L2": 15.0,
    "L3": 10.0,
}


@dataclass
class CompareRow:
    entry: str
    movement: str
    gt: float
    pred: float
    diff: float
    err_pct: float
    passed: bool


@dataclass
class CompareResult:
    level: str
    rows: list[CompareRow] = field(default_factory=list)
    total_gt: float = 0.0
    total_pred: float = 0.0
    overall_pass: bool = True
    tolerance_pct: float = 15.0
    duration_sec: float = 0.0


def load_gt(csv_path: Path) -> dict[tuple[str, str], float]:
    out: dict[tuple[str, str], float] = {}
    with csv_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (row["entry_direction"], row["movement"])
            out[key] = float(row["implied_count_22min"])
    return out


def load_pred(json_path: Path) -> dict[tuple[str, str], int]:
    with json_path.open(encoding="utf-8") as f:
        data = json.load(f)
    return pred_from_payload(data)


def pred_from_payload(data: dict) -> dict[tuple[str, str], int]:
    out: dict[tuple[str, str], int] = {}
    for row in data.get("counts", []):
        key = (row["entry_direction"], row["movement"])
        out[key] = int(row["total"])
    return out


def compare_counts(
    gt_all: dict[tuple[str, str], float],
    pred: dict[tuple[str, str], int],
    level: str,
    duration_sec: float = 0.0,
    full_video_sec: float = 22 * 60,
    scale_to_peak_hour: bool = False,
) -> CompareResult:
    keys_filter = LEVEL_KEYS[level]
    gt = gt_all if keys_filter is None else {k: gt_all[k] for k in keys_filter if k in gt_all}
    tol = LEVEL_TOLERANCE[level]
    result = CompareResult(level=level, tolerance_pct=tol, duration_sec=duration_sec)

    for key, gt_val in sorted(gt.items()):
        raw = float(pred.get(key, 0))
        # Full-clip runs should not be rescaled onto a nominal 22:00 window.
        same_clip = duration_sec <= 0 or duration_sec >= full_video_sec * 0.95
        if same_clip:
            p_show = raw
        else:
            p_show = raw * full_video_sec / duration_sec
        if scale_to_peak_hour:
            p_show = p_show * (60 / 22)
            gt_val = gt_val * (60 / 22)
        diff = p_show - gt_val
        err = (diff / gt_val * 100) if gt_val else float("nan")
        passed = abs(err) <= tol if gt_val else False
        if not passed:
            result.overall_pass = False
        result.total_gt += gt_val
        result.total_pred += p_show
        entry, movement = key
        result.rows.append(
            CompareRow(
                entry=entry,
                movement=movement,
                gt=gt_val,
                pred=p_show,
                diff=diff,
                err_pct=err,
                passed=passed,
            )
        )
    return result


def format_compare(result: CompareResult) -> str:
    lines = [
        f"comparison level: {result.level}",
        f"processed duration: {result.duration_sec:.1f}s",
        f"tolerance: ±{result.tolerance_pct:.0f}%",
        "",
        f"{'进口':<4} {'转向':<4} {'GT(22min)':>10} {'Pred':>8} {'Diff':>8} {'Err%':>8} {'Pass':>6}",
        "-" * 58,
    ]
    for row in result.rows:
        mark = "OK" if row.passed else "FAIL"
        lines.append(
            f"{row.entry:<4} {row.movement:<4} {row.gt:>10.1f} {row.pred:>8.1f} {row.diff:>+8.1f} {row.err_pct:>7.1f}% {mark:>6}"
        )
    lines.append("-" * 58)
    total_diff = result.total_pred - result.total_gt
    total_err = (total_diff / result.total_gt * 100) if result.total_gt else float("nan")
    lines.append(
        f"{'合计':<9} {result.total_gt:>10.1f} {result.total_pred:>8.1f} {total_diff:>+8.1f} {total_err:>7.1f}%"
    )
    lines.append("")
    lines.append(f"overall: {'PASS' if result.overall_pass else 'FAIL'} (level {result.level})")
    return "\n".join(lines)
