from __future__ import annotations


def build_summary(counts: dict[str, dict[str, int]], line_meta: dict | None = None) -> list[dict]:
    rows = []
    for key, by_cls in sorted(counts.items()):
        if "|" in key:
            entry, movement = key.split("|", 1)
            entry_dir = entry.replace("进口", "")
        else:
            entry_dir = line_meta.get("entry_direction", "") if line_meta else ""
            movement = line_meta.get("movement", "") if line_meta else ""
            entry = line_meta.get("entry", "") if line_meta else ""
        total = sum(by_cls.values())
        rows.append(
            {
                "entry_direction": entry_dir,
                "movement": movement,
                "entry": entry or f"{entry_dir}进口",
                "total": total,
                "by_class": dict(by_cls),
            }
        )
    return rows
