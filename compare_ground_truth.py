#!/usr/bin/env python3
"""Compat wrapper. Prefer: python -m count_yolo compare ..."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from count_yolo.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["compare", *sys.argv[1:]]))
