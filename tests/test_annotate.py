from count_yolo.annotate import build_line_entry, entry_direction_from_line_name, parse_line_names, save_lines


def test_save_lines_replaces_stale(tmp_path):
    import json

    import numpy as np

    cfg = tmp_path / "c.json"
    cfg.write_text(
        json.dumps({"line_counting": {"STALE": {"line": [[0, 0], [1, 1]]}}}),
        encoding="utf-8",
    )
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    entry = build_line_entry("L1_NEW", "near_to_far", None, "断面", [(1, 2), (3, 4)])
    save_lines(cfg, {"L1_NEW": entry}, frame, tmp_path / "preview.jpg")
    data = json.loads(cfg.read_text(encoding="utf-8"))
    assert list(data["line_counting"]) == ["L1_NEW"]


def test_parse_line_names_single():
    assert parse_line_names(None, "L1_南直行") == ["L1_南直行"]


def test_parse_line_names_multi():
    assert parse_line_names("L1_主路,L1_匝道,L1_右路", "L1_南直行") == ["L1_主路", "L1_匝道", "L1_右路"]


def test_entry_direction_from_line_name():
    assert entry_direction_from_line_name("L1_主路") == "主路"


def test_build_line_entry_defaults():
    entry = build_line_entry("L1_主路", "near_to_far", None, "断面", [(1, 2), (3, 4)])
    assert entry["line"] == [[1, 2], [3, 4]]
    assert entry["maps_to"]["entry_direction"] == "主路"
    assert entry["require_motion_direction"] is True
