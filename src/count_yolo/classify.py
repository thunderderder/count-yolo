from __future__ import annotations

COCO_VEHICLE_CLASS_IDS = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}

CUSTOM_NAME_ALIASES = {
    "electric-bicycle": "motorcycle",
    "electric_bicycle": "motorcycle",
    "ebike": "motorcycle",
    "bicycle": "motorcycle",
    "motorcycle": "motorcycle",
    "motorbike": "motorcycle",
    "car": "car",
    "van": "van",
    "truck": "truck",
    "bus": "bus",
}


def classify_truck(area: float, frame_area: float) -> str:
    ratio = area / frame_area if frame_area else 0.0
    return "truck_large" if ratio > 0.012 else "truck_small"


def map_vehicle_class(name: str, bbox_area: float, frame_area: float) -> str:
    if name == "motorcycle":
        return "motorcycle"
    if name == "car":
        return "car"
    if name == "bus":
        return "bus"
    if name == "van":
        return "truck_small"
    if name == "truck":
        return classify_truck(bbox_area, frame_area)
    return "car"


def resolve_vehicle_class_ids(names: dict | None) -> dict[int, str]:
    """从模型 names 解析可计数车辆类别；无法识别时回退 COCO 映射。"""
    if not names:
        return dict(COCO_VEHICLE_CLASS_IDS)

    resolved: dict[int, str] = {}
    for cls_id, raw in names.items():
        key = str(raw).strip().lower().replace(" ", "-")
        if key in {"person", "pedestrian"}:
            continue
        if key in CUSTOM_NAME_ALIASES:
            resolved[int(cls_id)] = CUSTOM_NAME_ALIASES[key]
        elif key in COCO_VEHICLE_CLASS_IDS.values():
            resolved[int(cls_id)] = key

    name_set = {str(v).lower() for v in names.values()}
    if not resolved or ("truck" in name_set and 7 in names):
        if set(COCO_VEHICLE_CLASS_IDS).issubset(set(int(k) for k in names.keys())):
            return dict(COCO_VEHICLE_CLASS_IDS)
    if not resolved:
        return dict(COCO_VEHICLE_CLASS_IDS)
    return resolved
