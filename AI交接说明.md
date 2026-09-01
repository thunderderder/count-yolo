# count_yolo — AI 交接说明

> 给接手本项目的 **AI Agent** 用。人类接手请看 [`交接说明.md`](交接说明.md)。  
> 接手后先读本文，再读 [`AGENTS.md`](AGENTS.md)，需要细节再查 [`docs/input_config.md`](docs/input_config.md) / [`docs/rfc_local_console.md`](docs/rfc_local_console.md)。

---

## 0. 你的角色

接手人可能自己跑，也可能让你跑。无论哪种，你都要能：

1. **定位**代码与配置，不盲目 glob 全仓  
2. **区分**能自主执行的步骤 vs 必须用户在本机完成的步骤（OpenCV 标定弹窗）  
3. **遵守**分层验收：示例匝道视频只验 L1，不宣称 L3  
4. **不破坏**已发表合同（`examples/`）和隐私规则（无本机绝对路径进 git）  
5. **优先 Web 工作流**：`serve` → Job → 标定 → 试跑 30s → 全片；CLI 仍可用

---

## 1. 先读什么（顺序）

```
AI交接说明.md（本文）
    → AGENTS.md（硬规则）
    → docs/working.md（最近改了什么）
    → jobs/_template.yaml + 用户 jobs/*.yaml（gitignore，本机才有）
    → configs/<路口>.json（line_counting）
    → docs/rfc_local_console.md（Web 设计）
    → 改逻辑：pipeline.py / jobs.py / web/server.py / annotate.py
```

人类向安装与流程：`交接说明.md`。产品背景：`docs/prd.md`、`docs/rfc.md`。

---

## 2. 项目状态快照（截至 2026-09-01）

| 项 | 状态 |
|----|------|
| **定位** | 交通调查脚本；YOLO + ByteTrack + 几何规则 |
| **主入口** | **Web 控制台** `.\run.ps1 serve` → http://127.0.0.1:8765 |
| **任务模型** | `jobs/<job_id>.yaml` + `configs/*.json`；`run-job` / Web「试跑/全量」 |
| **稳定能力** | L1 多断面过线；单遍视频 `count_lines_traffic` |
| **Web 已实现** | Job CRUD、Web 触发标定子进程、GPU 检测、`preview_seconds: 30` 试跑、停止任务、输出 **本机打开**（`os.startfile`） |
| **Web 未做** | 浏览器内画线、Web 内嵌播放 mp4v（用本机播放器） |
| **未实现** | `write_excel.py`、单遍 `--mode fuse`、L3 八区标定 GUI |
| **标定** | 每次 `save_lines` **整表覆盖** `line_counting`，不 merge 旧线名 |
| **计数范围** | **config 里全部断面**，无勾选子集；标定后自动同步 `job.lines` |
| **路径** | Job/config **相对仓库根**；计数 JSON 的 `video` **仅文件名** |
| **子进程** | Web 用 `annotate_line.py` / `count_traffic.py`（勿用 `python -m count_yolo`，venv 可能未装包名） |
| **已发表合同** | `examples/counts_L1_south_through_yolov8m.json` → 1304（GT 1533） |

---

## 3. 架构一图

```
MP4 + jobs/*.yaml + configs/*.json
        │
        ├─ run.ps1 serve ──► web/server.py (FastAPI)
        │       │                 ├─ POST .../annotate → subprocess annotate_line.py
        │       │                 ├─ POST .../run      → subprocess count_traffic.py run-job
        │       │                 └─ POST .../open-local → 本机打开文件/文件夹
        │
        └─ run.ps1 ──► count_traffic.py / annotate_line.py（薄包装，注入 src/）
                  │
                  ▼
            src/count_yolo/cli.py
                  ├─ annotate ──► annotate.py（OpenCV GUI）
                  ├─ run-job ───► run_job.py → pipeline.count_lines_traffic
                  ├─ count-all ─► pipeline（多线单遍）
                  └─ compare ───► compare.py

output/jobs/<job_id>/     counts_*.json, debug_*_8m.mp4, run.log, calibration_preview_10s.mp4
examples/*.json           发表合同（勿随手改）
```

**逻辑归属**：只在 `src/count_yolo/` 改；根目录 `*.py` 保持薄包装。

---

## 4. 关键文件速查

| 路径 | Agent 何时读/改 |
|------|----------------|
| `src/count_yolo/web/server.py` | Web API、子进程、`open-local`、`-u` 无缓冲日志 |
| `src/count_yolo/web/static/index.html` | 控制台 UI |
| `src/count_yolo/jobs.py` | Job yaml、`resolve_count_window`（`preview_seconds`） |
| `src/count_yolo/run_job.py` | `run-job`；计数用 config 全部 `line_counting` |
| `src/count_yolo/pipeline.py` | 多线 `count_lines_traffic`；debug 叠字 `line_total` 为累计 |
| `src/count_yolo/annotate.py` | 标定；`save_lines` 覆盖 `line_counting`；PIL 中文叠字 |
| `src/count_yolo/preview.py` | 标定预览片、叠线静帧 |
| `src/count_yolo/paths.py` | `resolve_path`、默认视频/config |
| `src/count_yolo/timeparse.py` | `probe_device`、`resolve_device` |
| `jobs/_template.yaml` | Job 模板（进 git）；用户 `jobs/*.yaml` **gitignore** |
| `configs/_empty.json` | 空标定模板 |
| `run.ps1` | `serve` / `run-job` / `8m-all` / `annotate` |

---

## 5. 命令：你能跑什么

工作目录：`adhoc_jobs/count_yolo`

### 5.1 推荐流程（Web）

```powershell
.\run.ps1 serve
# 用户：新建 Job → video: videos/xxx.MP4（相对路径）
# → 填断面名 → 标定断面（OpenCV 弹窗，用户点鼠标）
# → 勾选试跑 30s → 验收 debug / JSON → 取消勾选 → 全量计数
# → 右侧「本机打开」debug 视频
```

Agent 可：`curl` 测 API、`pytest`、读 `output/jobs/<id>/run.log`。  
**不要**代替用户点标定窗口；**不要**未确认就跑全片。

### 5.2 CLI（与 Web 等价）

```powershell
python -m pytest tests/ -q

.\run.ps1 annotate --config configs\x.json --lines "L1_A,L1_B" --job <job_id>
.\run.ps1 run-job --job <job_id> --device 0

# 传统（无 job 文件）
.\run.ps1 8m-all --device 0 --max-seconds 30
.\run.ps1 compare --counts examples\counts_L1_south_through_yolov8m.json --level L1
```

Job 里 `preview_seconds: 30` 时只处理 `start..start+30` 秒；删除该字段则全片。

### 5.3 环境

- `pip install -e ".[runtime]"`（Web 需 fastapi/uvicorn）  
- `.env` 的 `COUNT_YOLO_PYTHON` 可指向 GPU venv（如 `../uva/.venv/Scripts/python.exe`）  
- 标定需本机显示器；`opencv-python` 与 `headless` **不能共存**

---

## 6. 硬约束（违反即错）

1. 改代码 → 同步 `docs/working.md` Changelog  
2. 公开文件 → 无本机绝对路径；Job 模板用 `videos/...` 相对路径  
3. 计数 JSON → `video` 只写文件名（`pipeline` 已 `Path(video).name`）  
4. 示例匝道 → 只验 L1；禁止用其证明 L3  
5. 对向/潮汐 → `require_motion_direction`，禁止靠收窄 x 裁线  
6. `examples/` 为发表合同；`output/` 不是  
7. 根目录 `.py` 薄包装；逻辑在 `src/count_yolo/`  
8. Web 子进程 → `annotate_line.py` / `count_traffic.py`，不是 `-m count_yolo`  
9. 标定 → **覆盖** `line_counting`，不 `update` 残留旧 key  
10. 多断面 → 各线独立数字，**不要**把三数相加当总流量  
11. git → 不提交 `.env`、`*.mp4`、`models/*.pt`、`output/`、`jobs/*.yaml`（除 `_template`、`_archive`）

---

## 7. debug 视频与计数显示（易误解）

| 显示 | 含义 |
|------|------|
| 橙框 + `OK` | 该 track 已在**该断面**计过一次（状态保持） |
| 绿框 | 跟踪中，尚未过线 |
| 左上角 `counted=N` | **累计过线总数**（与 JSON 一致，单调不减） |
| `tracking=M` | 当前帧断面横向范围内、尚未过线的车数 |

debug 编码为 **mp4v**，浏览器常无法播放 → 用 Web「本机打开」或进 `output/jobs/<job_id>/`。

---

## 8. 业务口径（避免答错）

| 概念 | 说明 |
|------|------|
| **L1** | 单方向过线；先比转向合计，车型后置 |
| **L3** | 四进口×左直右；示例远景素材不适合验收 |
| **8m vs ebike** | Job `ebike_enabled: true` 时第二遍权重，每断面多 `debug_*_ebike.mp4` |
| **fuse** | 单遍 8m+ebike 未实现；已知拼接 ≈1520（-0.8%） |
| **GT 南直行** | 22min ≈ **1533** |

---

## 9. 待办优先级

1. **P0** — 用户有新视频：Web 标定 → 试跑 30s → 全片 → `compare`  
2. **P1** — `write_excel.py`  
3. **P1** — `--mode fuse`  
4. **P2** — L3 新十字口视频验收  
5. **P2** — debug 视频改 h264 便于浏览器（可选）

---

## 10. 坑表（Agent 高频翻车）

| 现象 | 原因 | 处理 |
|------|------|------|
| 标定秒退、无窗口 | Web 用了 `-m count_yolo` | 已改 `annotate_line.py`；仍失败查 `annotate.log` |
| `counted` 数字来回跳 | 旧版叠字统计**画面内** OK 数 | 已改累计；需重跑才有新 debug |
| config 里 6 条旧+新线名 | 旧版 `update` merge | 已改覆盖；重标定或手删 config |
| PowerShell `--lines` 拆参 | 逗号 | 必须引号 `"L1_A,L1_B"` |
| 全片跑很久 / 用户打断 | 未勾试跑 | 建议 `preview_seconds: 30` |
| `409` 重复点运行 | 上次子进程未停 | `POST /api/run/stop` 或杀 python |
| 日志不刷新 | stdout 缓冲 | 子进程已 `-u` + `PYTHONUNBUFFERED` |
| `run_job` 结束报错 | 曾缺 `PROJECT_ROOT` import | 已修；看 `run.log` 尾部 |
| OpenCV 中文乱码 | `putText` 不支持中文 | 已用 PIL + `msyh.ttc` |
| 标定无窗口 | opencv headless | 卸 headless，留 `opencv-python` |
| Web 显示 running 但进程已死 | 子进程被外部 kill | 重启 `serve` 或调 stop API |

---

## 11. 改代码时的测试

```powershell
python -m pytest tests/ -q
```

| 改了什么 | 至少跑 |
|----------|--------|
| `geometry.py` | `test_geometry.py` |
| `jobs.py` / `run_job.py` | `test_jobs.py` |
| `paths.py` | `test_paths.py` |
| `annotate.py` | `test_annotate.py` |
| `timeparse.py` | `test_timeparse.py` |
| 发布前 | 全量 `tests/` |

有 GPU 时：Web 试跑 30s 或 CLI `--max-seconds 30`。**不要**把 `output/` 写进 `examples/` 除非用户明确要求更新合同。

---

## 12. 与用户沟通模板

| 用户说 | 你做 |
|--------|------|
| 启动 / 试试 | 确认：`serve` 已开？标定 / 试跑 30s / 全片？ |
| 三条断面 | 标定一次画三条；计数自动全计；**三数不相加** |
| 结果视频看不到 | 指 `output/jobs/<id>/` +「本机打开」；非浏览器内嵌 |
| 数和画面不一致 | 先区分 JSON 累计 vs 旧 debug 叠字；再查线位/GT |
| 交接给人 | `交接说明.md`；AI 继续用本文 |
| 推 GitHub | 仓库是 **独立** `thunderderder/count-yolo`，不是 `context-infrastructure` monorepo |

---

## 13. 文档分工

| 文档 | 读者 |
|------|------|
| **AI交接说明.md**（本文） | AI Agent |
| `AGENTS.md` | AI 常驻规则 |
| `交接说明.md` | 人类 |
| `docs/input_config.md` | Job/config 字段 |
| `docs/rfc_local_console.md` | Web RFC |
| `docs/working.md` | Changelog |
| `README.md` | 对外全貌 |

---

*以仓库为准；重大变更同步 `docs/working.md` 与本文 §2 快照。*
