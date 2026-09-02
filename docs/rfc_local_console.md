# RFC — 本地 Web 控制台与任务（Job）模型

> 状态：**v1 已实现**（2026-09）。与 [`input_config.md`](input_config.md)、[`rfc.md`](rfc.md)、[`交接说明.md`](../交接说明.md) 配套阅读。

## 1. 目标

为懂命令行的本机用户（如本科生）提供：

| 能力 | 载体 |
|------|------|
| 换视频、换调查项、换几何 | `jobs/*.yaml` + `configs/*.json` |
| 标定画线 | **OpenCV**（Web 触发子进程 `annotate_line.py`） |
| 标定验收：线对不对 | `calibration_preview_10s.mp4` + 叠线静帧 |
| 试跑 / 全量计数 + 观测 | 每断面 `debug_<line>_8m.mp4`；Web **本机打开** |
| 调参 | Web「检测与跟踪」「运动过滤」面板 → 写入 job yaml |
| 跑进度 | Web 日志区 + `output/jobs/<id>/run.log` |
| 准不准 | **compare + GT**（不进 Web） |

Web 是**配置、调参、播放台**，不是精度评判台。

---

## 2. 两层配置

### 2.1 几何层 — `configs/<场景>.json`

- 同一机位可长期复用；机位/分辨率变了就新建。
- `line_counting` 可含**多条线**；标定**覆盖**整表，不 merge 旧线名。
- 标定：`run.ps1 annotate` 或 Web「标定断面」。

### 2.2 任务层 — `jobs/<任务名>.yaml`

- 命名：**`{年}-{场景}_{调查项}_{MMDD}`**
- 除 video/config/lines 外，还可存 **检测、ByteTrack、运动过滤** 参数（见 `jobs/_template.yaml`）。
- 用户 `jobs/*.yaml` 默认 gitignore；模板 `_template.yaml` 进仓。

### 2.3 路径优先级

见 [`input_config.md`](input_config.md)。相对仓库根路径优先。

---

## 3. Job 输出目录

```
output/jobs/<job_id>/
├── job.snapshot.yaml           # 本次运行快照（含全部调参）
├── tracker.yaml                # ByteTrack 配置快照
├── calibration_preview_10s.mp4
├── counts_all_lines_8m.json
├── counts_<断面>_8m.json
├── debug_<断面>_8m.mp4
├── run.log
└── line_overlay.jpg            # Web 叠线静帧 API
```

试跑：`preview_seconds: 30`（Web 勾选「试跑 30 秒」）。全片：取消勾选。

---

## 4. 标定后预览片

`annotate` 保存成功 → 写 `calibration_preview_10s.mp4` 到 job 输出目录（或 `output/`）。

**重启 `serve` 不必重画线**；坐标在 `configs/*.json`。

---

## 5. 全片 debug 视频

### 5.1 每断面一条 MP4

单遍 YOLO 推理，每线一个 `VideoWriter`：`debug_<line_name>_8m.mp4`。

### 5.2 v1 已实现样式

| 状态 | 样式 |
|------|------|
| **counted** | 橙框 + `OK` + track_id |
| **tracking** | 绿框 + track_id |

OSD：`counted=` 为**累计过线数**（单调），`tracking=` 为画面内未计数的跟踪数。

编码 **mp4v**，浏览器常无法播放 → Web「本机打开」。

### 5.3 未实现（RFC 原案）

- `filtered` / `ended` 分色与原因标注
- 浏览器内嵌可靠播放 h264

---

## 6. 本地 Web 控制台（已实现）

```powershell
.\run.ps1 serve
→ http://127.0.0.1:8765
```

### 6.1 页面能力

1. Job 列表 / 新建 / 保存
2. Web 触发标定（OpenCV 弹窗）
3. 标定验收：叠线静帧
4. **试跑 30s / 全量计数**、**停止**
5. 输出列表 + **本机打开** / 打开输出文件夹
6. **检测与跟踪**（YOLO + ByteTrack）：`conf`、`track_buffer` 等；抗遮挡预设
7. **运动过滤**（过线方向）：`motion_min_dy_*` 等；慢车 / 关闭预设
8. 各参数字段旁有「是什么 / 怎么调」说明（`index.html`）

### 6.2 仍不做

- 浏览器画线、GT 图表、在线改权重路径

### 6.3 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/jobs` | 列表 |
| GET/PUT | `/api/jobs/{id}` | 读/写 job（含调参字段） |
| GET | `/api/jobs/{id}/lines` | config 中断面名 |
| GET | `/api/jobs/{id}/artifacts` | 输出清单 |
| GET | `/api/jobs/{id}/overlay.jpg` | 叠线静帧 |
| POST | `/api/jobs/{id}/annotate` | 启动标定子进程 |
| GET | `/api/annotate/status` | 标定状态 |
| POST | `/api/jobs/{id}/run` | 启动 `run-job` |
| POST | `/api/run/stop` | 停止计数/标定 |
| GET | `/api/run/status` | 运行日志 tail |
| POST | `/api/jobs/{id}/open-local` | 本机打开文件/文件夹 |
| GET | `/api/device` | GPU 检测 |

子进程入口：`annotate_line.py` / `count_traffic.py`（非 `python -m count_yolo`）。

---

## 7. 精度评估

```powershell
.\run.ps1 compare --counts output/jobs/<job_id>/counts_*.json --level L1
```

---

## 8. 典型工作流

```powershell
.\run.ps1 serve
# 浏览器：新建 Job → 视频路径 → 标定 → 试跑 30s
# 遮挡丢 ID →「检测与跟踪」抗遮挡预设
# 慢车过线不计 →「运动过滤」慢车更宽松
# 保存 Job → 全量计数 → 本机打开 debug
```

---

## 9. 实现状态（2026-09-02）

| 项 | 状态 |
|----|------|
| Job yaml + `run-job` | ✅ |
| 标定 10s 预览片 | ✅ |
| 每断面 debug 全片 | ✅ |
| `serve` + Job CRUD | ✅ |
| Web 跑数 / 停止 | ✅ |
| 检测与跟踪 Web 调参 | ✅ |
| 运动过滤 Web 调参 | ✅ |
| filtered/ended 分色 | ❌ |
| compare 报告 markdown | ❌ |
| h264 debug / 浏览器播放 | ❌ |

---

## 10. 调参分工（速查）

| 现象 | 调哪 | 关键字段 |
|------|------|----------|
| 遮挡后 ID 断了 | 检测与跟踪 | `track_buffer`、`conf` |
| 过了线仍绿框 | 运动过滤 | `motion_min_dy_total`、`motion_min_dy_med` |
| 对向车误计 | 运动过滤 | 保持 `require_motion_direction: true` |
| 线画错了 | 标定 | 重绘，不改 job 调参 |
