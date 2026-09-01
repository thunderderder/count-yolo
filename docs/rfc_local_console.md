# RFC — 本地 Web 控制台与任务（Job）模型

> 状态：**已定稿，待实现**。与 [`input_config.md`](input_config.md)、[`rfc.md`](rfc.md) 配套阅读。

## 1. 目标

为懂命令行的本机用户（如本科生）提供：

| 能力 | 载体 |
|------|------|
| 换视频、换调查项、换几何 | `jobs/*.yaml` + `configs/*.json` |
| 标定画线 | **OpenCV**（现有 `annotate`，不进 Web） |
| 标定验收：线对不对 | 自动生成 **10s 静帧+线** 预览片；Web 播放 |
| 全量计数 + 观测 | **每条断面单独一条全片 debug MP4**，框分状态 |
| 跑进度 | **命令行** stdout |
| 准不准 | **compare + GT + 报告**（不进 Web 观测台） |

Web 是**配置与播放台**，不是精度评判台。

---

## 2. 两层配置

### 2.1 几何层 — `configs/<场景>.json`

- 同一机位可长期复用；机位/分辨率变了就新建。
- `line_counting` 可含**多条线**（主路、匝道、右路、某进口左转…）。
- **不绑定**具体 MP4 文件名（避免一 config 一视频的死结）。
- 标定：`run.ps1 annotate --config configs/xxx.json --lines "..."`

### 2.2 任务层 — `jobs/<任务名>.yaml`

- **一个视频 × 一次调查 × 一个日期 = 一个 job 文件**。
- 命名约定：**`{年}-{场景}_{调查项}_{MMDD}`**  
  示例：`2026-文锦北路_南直行_0901`、`2026-文锦北路_三断面_0901`
- 字段见 [`jobs/_template.yaml`](../jobs/_template.yaml)。

### 2.3 路径优先级（实现时统一进 `paths.resolve_*`）

| 项 | 优先级 |
|----|--------|
| 视频 | CLI `--video` → `job.video` → `COUNT_YOLO_VIDEO` → config.`video_file`（可选）→ 根目录兜底 |
| config | CLI `--config` → `job.config` → `COUNT_YOLO_CONFIG` → 内置示例 |
| job | CLI `--job` → `COUNT_YOLO_JOB` → 无则要求显式传参 |

---

## 3. Job 输出目录（一次全量跑一个文件夹）

```
output/jobs/2026-文锦北路_三断面_0901/
├── job.yaml                    # 本次运行快照（可选，便于复现）
├── calibration_preview_10s.mp4 # 标定后自动生成，静帧+线 10s
├── counts_all_lines_8m.json    # 汇总
├── counts_L1_主路_8m.json
├── counts_L1_匝道_8m.json
├── counts_L1_右路_8m.json
├── debug_L1_主路_8m.mp4        # 全片观测视频（见 §5）
├── debug_L1_匝道_8m.mp4
├── debug_L1_右路_8m.mp4
└── line_overlay.jpg            # 叠线静帧（annotate 已有 line_preview 可对齐）
```

**默认全量跑**：`job` 不设 `max_seconds`（或 `end: null`）即整段 MP4。不再以 120s 冒烟作为常规流程；开发调试可临时加 `max_seconds`。

---

## 4. 标定后自动生成「静帧 + 线 10s」

**触发**：`annotate` 保存成功（单线或多线）。

**行为**：

1. 取标定所用帧（与 annotate 同一 `frame` / `--image`）。
2. 在帧上绘制本次保存的所有 `line_counting` 线（颜色与多线标定一致）。
3. 用 `cv2.VideoWriter` 写 **10s、与源视频相同 fps** 的 MP4（画面不变，仅便于播放器打开验收）。
4. 写入路径：若已有 `COUNT_YOLO_JOB` / `--job`，进 `output/jobs/<job_id>/`；否则 `output/calibration_preview_10s.mp4`。

Web 控制台第一屏：**选 job → 播 `calibration_preview_10s.mp4` + 静帧 JPG**。

---

## 5. 全片 debug 视频（观测核心）

### 5.1 三条路 → 三个全片 MP4

`count-all`（或 job 里 `lines: [L1_主路, L1_匝道, L1_右路]`）时：

- **每条线单独编码一个全片 debug 视频**（不是一条视频里画三条线）。
- 文件名：`debug_<line_name>_<model_tag>.mp4`（如 `debug_L1_主路_8m.mp4`）。
- 实现：可在**一次 YOLO 解码**中写三个 `VideoWriter`（与单遍多线计数同次推理），避免跑三遍全片。

### 5.2 画面上必须区分的状态

仅对 **YOLO 已检出且有关联 track_id** 的目标画框（真正「未识别」的漏检在画面上不可见，靠 GT compare 评估）。

| 状态 | 含义 | 建议样式 |
|------|------|----------|
| **counted** 已计数 | 该中心轨迹已过本线且方向校验通过 | 橙框 + `OK` / track_id |
| **tracking** 跟踪中 | 在本线 x 范围内，尚未过线或未满足方向 | 绿框 + track_id |
| **filtered** 未计入 | 过线但方向失败；或曾在本线 x 外；或运动方向与 `direction` 不符 | 灰框或红框 + 简短原因（`dir` / `x`） |
| **ended** 轨迹结束未计 | track 丢失/离开画面前仍未 counted | 紫框或虚线框（**漏计候选**，供人工扫一眼） |

每条 debug 视频只突出**当前断面**：

- 当前线：粗黄线。
- 仅强调落在该线 `x_min`–`x_max` 内的轨迹（其它 track 可淡化或不画，实现时二选一，默认**只画范围内**以免画面太乱）。

左上角 OSD：`line=<name> counted=<n> tracking=<m> filtered=<k>`。

### 5.3 与 JSON 的关系

`counts_<line>_*.json` 仍只存**已计数**汇总；debug 状态机细节可选写入 `debug_stats_<line>.json`（帧数、各状态 track 数）供 Web 列表，非必须 v1。

---

## 6. 本地 Web 控制台（v1 范围）

```text
python -m count_yolo serve [--port 8765]
→ http://127.0.0.1:8765
```

### 6.1 页面

1. **Job 列表**：扫描 `jobs/*.yaml`（排除 `_template`）。
2. **Job 编辑**：表单编辑 video、config、lines[]、model、device；保存回 yaml。
3. **标定验收**：播 `calibration_preview_10s.mp4`，显示 `line_overlay.jpg`。
4. **结果观测**：列出该 job 输出目录下各 `debug_*.mp4`，内嵌 `<video controls>`。
5. **等价 CLI**：折叠显示 `run.ps1 8m-all --job jobs/....yaml` 等（用户可自行复制）。

### 6.2 不做

- 浏览器画线、全片进度条、GT 误差图表、在线改 YOLO 权重。

### 6.3 API（草案）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/jobs` | 列表 |
| GET/PUT | `/api/jobs/{id}` | 读/写 job yaml |
| GET | `/api/jobs/{id}/artifacts` | 输出目录文件清单 |
| GET | `/media/...` | 安全映射 `output/jobs/` 下 mp4/jpg（禁止路径穿越） |

启动计数：**v1 仍用 CLI**；Web「运行」按钮可作为 v2（子进程 + 日志 tail）。

---

## 7. 精度评估（与 Web 分离）

```powershell
.\run.ps1 compare --counts output/jobs/<job_id>/counts_L1_主路_8m.json --ground-truth ground_truth/xxx.csv --level L1
```

后续：`reports/<job_id>_eval.md` 由 compare 扩展生成即可。

---

## 8. 典型工作流

```powershell
# 1. 新建任务
copy jobs\_template.yaml jobs\2026-文锦北路_三断面_0901.yaml
# 编辑 video、config、lines

# 2. 标定（OpenCV）
.\run.ps1 annotate --config configs\文锦北路.json --lines "L1_主路,L1_匝道,L1_右路" --job jobs\2026-文锦北路_三断面_0901.yaml
# → 自动写出 calibration_preview_10s.mp4

# 3. Web 验收线位
.\run.ps1 serve
# 浏览器播预览片

# 4. 全量计数（三断面、三个 debug 全片）
.\run.ps1 8m-all --job jobs\2026-文锦北路_三断面_0901.yaml --device 0

# 5. Web 或本地播放器看三条 debug 全片；CLI 看 compare
```

---

## 9. 实现顺序建议

1. `paths.resolve_video/config/job` + `jobs/_template.yaml` + 更新 `input_config.md`
2. `annotate` 结束写 `calibration_preview_10s.mp4`
3. `count_lines_traffic` 多 `VideoWriter` + 状态机样式（§5）
4. CLI `--job` / `8m-all --job`
5. `serve` + 静态页播片与 job 表单
6. compare 报告（可选）

---

## 10. 未决（实现前可再确认）

- `filtered` 与 `ended` 是否在 v1 就画进视频，还是先只做 counted/tracking 两色。
- 三个 debug 视频是否只画 x 范围内 track（推荐是）。
