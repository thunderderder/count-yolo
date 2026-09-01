# 输入视频与任务（Job）配置

换视频、换调查项时**不要改代码**。用 **Job 文件** 描述「这一次跑什么」；用 **config JSON** 描述「线画在哪」。

详细设计见 [`rfc_local_console.md`](rfc_local_console.md)。

---

## 两层分别管什么

| 层 | 文件 | 何时改 |
|----|------|--------|
| **几何** | `configs/<场景>.json` | 机位变了、要新画线、左转/右转/远端来车等不同断面 |
| **任务** | `jobs/<年>-<场景>_<调查项>_<MMDD>.yaml` | 每个视频、每次调查一条 |

命名示例：

- `2026-文锦北路_南直行_0901` — 单调查项
- `2026-文锦北路_三断面_0901` — 同视频三条线各计一次

模板：[`jobs/_template.yaml`](../jobs/_template.yaml)

---

## 路径优先级（实现目标）

| 项 | 顺序 |
|----|------|
| 视频 | `--video` → **job.video** → `COUNT_YOLO_VIDEO` → config.`video_file`（可选） |
| config | `--config` → **job.config** → `COUNT_YOLO_CONFIG` |
| 任务 | `--job jobs/xxx.yaml` → `COUNT_YOLO_JOB` |

路径可为**相对仓库根**（如 `videos/foo.MP4`）或**绝对路径**。视频默认 gitignore。

---

## 推荐流程

### 1. 新建任务

```powershell
copy jobs\_template.yaml jobs\2026-文锦北路_三断面_0901.yaml
# 编辑 video、config、lines
```

```yaml
video: videos/2026-文锦北路.MP4
config: configs/文锦北路.json
lines:
  - L1_主路
  - L1_匝道
  - L1_右路
model: 8m
device: auto
```

### 2. 标定（OpenCV，不进 Web）

```powershell
.\run.ps1 annotate --config configs\文锦北路.json --lines "L1_主路,L1_匝道,L1_右路"
```

保存后自动生成 **`calibration_preview_10s.mp4`**（静帧 + 叠线 10 秒），用于验收线位。

### 3. 全量计数

```powershell
.\run.ps1 8m-all --job jobs\2026-文锦北路_三断面_0901.yaml --device 0
```

输出目录（默认）：`output/jobs/2026-文锦北路_三断面_0901/`

- 每个 `lines` 一项：`counts_<线名>_8m.json`
- **每个断面一条全片 debug 视频**：`debug_<线名>_8m.mp4`（已计数 / 跟踪中 / 未计入等分色，见 RFC）

进度在**命令行**查看；精度用 `compare`，不在 Web 里评判。

### 4. Web 控制台

```powershell
.\run.ps1 serve
```

浏览器 http://127.0.0.1:8765 ：建 Job、Web 触发标定（本机 OpenCV）、试跑 30s / 全片计数、本机打开输出文件。设计见 [`rfc_local_console.md`](rfc_local_console.md)。

---

## 临时覆盖（不改 job 文件）

```powershell
.\run.ps1 8m-all --video "D:\data\新素材.MP4" --config configs\新路口.json --lines "L1_主路" --device 0
```

## 标定只用截图

```powershell
.\run.ps1 annotate --image output\frame_ref.jpg --config configs\某路口.json
```

## 常见错误

| 现象 | 处理 |
|------|------|
| `video not found` | 检查 job.video、文件是否在本机 |
| 跑错视频 | 看命令行 `video:` 行；确认 `--job` 指向的文件 |
| PowerShell `--lines` | 逗号列表须加引号：`"L1_主路,L1_匝道"` |
| 以为 Web 能判断准不准 | 用 `compare` + GT，见 `ground_truth/` |

计数 JSON 只保存**视频文件名**（无盘符）。本机绝对路径只出现在 job / `.env`（gitignore）。
