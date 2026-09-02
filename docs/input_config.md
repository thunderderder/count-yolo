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

浏览器 http://127.0.0.1:8765 ：建 Job、Web 触发标定（本机 OpenCV）、试跑 30s / 全片计数、**停止**、本机打开输出文件。设计见 [`rfc_local_console.md`](rfc_local_console.md)。

**标定落盘**：坐标写入 `configs/<场景>.json`；重启 `serve` **不用重画线**。任务进行中点 **停止**（「试跑」旁）。

---

## config 里 `line_counting` 字段

| 字段 | 层 | 说明 |
|------|-----|------|
| `line` | 几何 | `[[x1,y1],[x2,y2]]` 计数线端点 |
| `direction` | 几何+运动 | `near_to_far`（y 减小）或 `far_to_near`；穿线方向与运动过滤共用 |
| `x_min` / `x_max` | 几何 | 可选，限制这条线只管哪个横向车道 |
| `require_motion_direction` | 运动 | 默认 `true`；过线后再验轨迹方向，挡对向潮汐 |
| `maps_to` | 统计 | 写入 JSON 的进口/转向键，不参与判定 |

计数流程：**几何穿线** →（若 `require_motion_direction`）**运动方向** → +1。两道都写在同一条线配置里，但不是一回事。

拥堵慢车若大量过线不计：2026-09-02 起运动阈值已放宽（`dy_total < -1.5` 等）；仍漏可对该线试 `require_motion_direction: false` 对比（会放宽，可能多计对向）。**不要用收窄 x 代替运动过滤。**

---

## Job 检测与跟踪参数（遮挡 / 丢 ID）

写在 **job yaml**（Web「检测与跟踪」面板保存），运行时生成 `output/jobs/<id>/tracker.yaml` 供 ByteTrack 使用。

| 字段 | 默认 | 遮挡时建议 | 作用 |
|------|------|------------|------|
| `conf` | 0.25 | 0.15–0.2 | 检测置信度；略降可检出部分遮挡框 |
| `iou` | 0.7 | 0.7 | NMS 重叠抑制 |
| `vid_stride` | 1 | **保持 1** | 跳帧；>1 会加重遮挡丢轨 |
| `track_buffer` | 30 | 60–120 | 丢失后保留轨迹的帧数；**最关键** |
| `track_low_thresh` | 0.1 | 0.05 | ByteTrack 第二阶段低分框关联 |
| `match_thresh` | 0.8 | 0.7–0.75 | 重现时 IoU 匹配松紧 |
| `track_high_thresh` | 0.25 | 0.25 | 第一阶段高分匹配 |
| `new_track_thresh` | 0.25 | 0.25 | 新开轨迹门槛 |

Web 一键 **抗遮挡预设**：`track_buffer=90`、`conf=0.2`、`track_low_thresh=0.05`、`match_thresh=0.75`。

注意：遮挡后 ID 彻底丢失会分配**新 ID**，过线计数仍按 track 计一次；调参目标是减少丢 ID，无法 100% 消除。

---

## Job 运动过滤参数（过线方向 / 慢车）

写在 **job yaml**（Web「运动过滤」面板保存）。计数时：**几何穿线** →（若启用）**运动方向** → +1。断面 `direction` 仍在 config 标定里，此处只调门槛松紧。

| 字段 | 默认 | 慢车/漏计时 | 作用 |
|------|------|-------------|------|
| `require_motion_direction` | `true` | 对比试跑可关 | 是否启用运动关；关=纯几何过线 |
| `motion_min_points` | 3 | 2 | 判方向前最少轨迹帧数 |
| `motion_min_dy_total` | 1.5 | 1.0–0.8 | 过线窗口内 y 总位移（像素，near_to_far 为减小） |
| `motion_min_dy_med` | 0.25 | 0.15–0.1 | 步长中位数门槛（或多数步长方向正确也可过） |

Web 预设：**慢车更宽松**（2 / 1.0 / 0.15）、**关闭运动过滤**（仅几何）。有对向/潮汐时勿长期关闭。

config 里每条线仍有 `require_motion_direction`；Job 总开关为关时全部断面跳过运动关。

---

## 临时覆盖（不改 job 文件）

```powershell
.\run.ps1 8m-all --video "videos/新素材.MP4" --config configs\新路口.json --lines "L1_主路" --device 0
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
| 慢车过线不计 | 运动过滤过严 | Web「运动过滤」→ 慢车更宽松；或略降 `motion_min_dy_*` |
| 重启 serve 后要不要重画 | 标定在 config 文件 | **不用** |

计数 JSON 只保存**视频文件名**（无盘符）。本机绝对路径只出现在 job / `.env`（gitignore）。
