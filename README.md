# count-yolo

固定机位路口视频 + YOLO 跟踪 + 几何规则，做 **L1 过线计数**（L3 转向为骨架）。现场调查脚本，不是产品。

## 能做什么

- **Web 控制台**（本机）：建 Job → 标定断面 → 试跑 30s / 全片计数 → 本机打开 debug 视频与 JSON
- **CLI**：`annotate` / `8m-all` / `run-job` / `compare`
- **多断面**：一次视频、多条计数线，每断面独立 JSON + debug 视频
- **离线单测**：几何、Job 解析、路径规则（不装 GPU / torch 也能 `pytest`）

未做：写 Excel、双模型单遍 fuse、L3 八区标定 GUI。

## 路径约定（重要）

**Job、config、文档里的路径一律相对仓库根目录**，例如：

```yaml
video: videos/文锦北路.MP4
config: configs/某路口.json
```

也支持绝对路径（本机专用），但 **不要写进要提交的 yaml/json**；仓库内示例只用相对路径。视频、权重、`output/` 已在 `.gitignore`。

解析逻辑见 `src/count_yolo/paths.py`：`resolve_path()` 把相对路径接到 `PROJECT_ROOT`。

## Quick start

Python ≥ 3.10。

```powershell
cd count_yolo
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python -m pytest tests/ -q
```

跑视频与 Web 控制台：

```powershell
pip install -e ".[runtime]"
copy .env.example .env
.\run.ps1 serve
```

浏览器打开 http://127.0.0.1:8765 。流程：新建 Job → 填 `videos/xxx.MP4` → 填断面名 → **标定断面**（弹出 OpenCV）→ 勾选 **试跑 30 秒** 验收 → 取消勾选后 **全量计数**。任务在跑时点 **停止**；重启 `serve` **不用重画线**（标定已写入 `configs/*.json`）。结果在 `output/jobs/<job_id>/`，页面可 **本机打开**（系统默认播放器）。

过线计数分两关：**几何**（中心点穿线）→ **运动方向**（挡对向潮汐）。Web 左侧可分别调 **「检测与跟踪」**（遮挡丢 ID）和 **「运动过滤」**（慢车过线不计）。详见 `交接说明.md` 与 `docs/input_config.md`。

CLI 等价：

```powershell
copy jobs\_template.yaml jobs\2026-路口_调查_0901.yaml
# 编辑 video / config / lines（相对路径）
.\run.ps1 annotate --config configs\某路口.json --lines "L1_主路,L1_匝道" --job 2026-路口_调查_0901
.\run.ps1 run-job --job 2026-路口_调查_0901 --device 0
```

`run.ps1` 会优先用项目 `.venv` 或 `.env` 里的 `COUNT_YOLO_PYTHON`（可指向已有 GPU 环境，如 `../uva/.venv`）。

## 仓库结构

```text
src/count_yolo/       计数、标定、Job、Web
jobs/_template.yaml     任务模板（复制后改名使用）
configs/                路口几何（line_counting）
output/jobs/<job_id>/   运行产物（gitignore）
docs/                   RFC、操作说明、测试约定
tests/                  离线单测
run.ps1                 Windows 入口
```

根目录 `count_traffic.py`、`annotate_line.py` 为兼容包装（内部 `sys.path` 注入 `src/`），**Web 子进程也走这两个入口**，不要假设已 `pip install` 包名 `count_yolo`。

## 精度与分层（摘要）

示例匝道远景素材：**只验 L1 近场过线**，不拿它证明四进口全矩阵。COCO yolov8m 漏摩托严重；四轮 + 电自权重拼接可接近人工表。详见 `阶段总结.md` 与 `examples/`。

## 文档

| 文件 | 读者 |
|------|------|
| [`交接说明.md`](交接说明.md) | 人接手 |
| [`AI交接说明.md`](AI交接说明.md) | AI / 自动化 |
| [`docs/input_config.md`](docs/input_config.md) | Job + config 字段 |
| [`docs/rfc_local_console.md`](docs/rfc_local_console.md) | Web 控制台设计 |

## Privacy

可公开仓形态：示例 JSON 不含本机绝对路径；权重与原始 MP4 不进 git。`docs/assets/` 内演示片除外。

## License

MIT
