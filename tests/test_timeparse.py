from count_yolo.timeparse import probe_device, resolve_device


def test_resolve_device_explicit():
    assert resolve_device("cpu") == "cpu"
    assert resolve_device("0") == "0"


def test_probe_device_shape():
    info = probe_device()
    assert "recommended" in info
    assert "cuda_available" in info
    assert "message" in info
    assert info["recommended"] in ("cpu", "0")
    if info["cuda_available"]:
        assert info["device_count"] >= 1
        assert info["devices"][0]["id"] == "0"
