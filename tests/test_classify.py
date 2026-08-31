from count_yolo.classify import (
    classify_truck,
    map_vehicle_class,
    resolve_vehicle_class_ids,
)


def test_classify_truck_splits_on_area_ratio():
    frame = 1920 * 1080
    assert classify_truck(0.011 * frame, frame) == "truck_small"
    assert classify_truck(0.013 * frame, frame) == "truck_large"


def test_map_vehicle_class_aliases():
    frame = 1000.0
    assert map_vehicle_class("motorcycle", 10, frame) == "motorcycle"
    assert map_vehicle_class("car", 10, frame) == "car"
    assert map_vehicle_class("bus", 10, frame) == "bus"
    assert map_vehicle_class("van", 10, frame) == "truck_small"
    assert map_vehicle_class("unknown", 10, frame) == "car"


def test_resolve_coco_names():
    names = {0: "person", 2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}
    resolved = resolve_vehicle_class_ids(names)
    assert resolved[2] == "car"
    assert resolved[7] == "truck"
    assert 0 not in resolved


def test_resolve_custom_ebike_names():
    names = {
        0: "Electric-bicycle",
        1: "bicycle",
        2: "car",
        3: "van",
        4: "bus",
        5: "person",
    }
    resolved = resolve_vehicle_class_ids(names)
    assert resolved[0] == "motorcycle"
    assert resolved[1] == "motorcycle"
    assert resolved[3] == "van"
    assert 5 not in resolved
