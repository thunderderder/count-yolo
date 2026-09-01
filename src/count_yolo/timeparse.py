from __future__ import annotations


def parse_time_to_seconds(text: str) -> float:
    parts = text.strip().split(":")
    if len(parts) == 1:
        return float(parts[0])
    if len(parts) == 2:
        m, s = parts
        return int(m) * 60 + float(s)
    if len(parts) == 3:
        h, m, s = parts
        return int(h) * 3600 + int(m) * 60 + float(s)
    raise ValueError(f"invalid time: {text}")


def resolve_device(requested: str) -> str:
    if requested != "auto":
        return requested
    return probe_device()["recommended"]


def probe_device() -> dict:
    """Return CUDA/GPU availability for CLI and web console."""
    result: dict = {
        "torch_installed": False,
        "cuda_available": False,
        "device_count": 0,
        "devices": [],
        "recommended": "cpu",
        "message": "未安装 PyTorch，将使用 CPU（全片计数较慢）",
    }
    try:
        import torch
    except ImportError:
        return result

    result["torch_installed"] = True
    if not torch.cuda.is_available():
        result["message"] = "PyTorch 已安装但未检测到可用 CUDA，将使用 CPU（全片计数较慢）"
        return result

    count = torch.cuda.device_count()
    result["cuda_available"] = True
    result["device_count"] = count
    for idx in range(count):
        result["devices"].append({"id": str(idx), "name": torch.cuda.get_device_name(idx)})
    result["recommended"] = "0"
    if count == 1:
        result["message"] = f"检测到 GPU：{result['devices'][0]['name']}"
    else:
        names = "、".join(d["name"] for d in result["devices"])
        result["message"] = f"检测到 {count} 块 GPU：{names}"
    return result
