# count_yolo — AI 交接说明

> 给接手本项目的 **AI Agent** 用。人类接手请看 [`交接说明.md`](交接说明.md)。  
> 接手后先读本文，再读 [`AGENTS.md`](AGENTS.md)，需要细节再查 [`阶段总结.md`](阶段总结.md) / [`README.md`](README.md)。

---

## 0. 你的角色

接手人可能自己跑，也可能让你跑。无论哪种，你都要能：

1. **定位**代码与配置，不盲目 glob 全仓  
2. **区分**能自主执行的步骤 vs 必须用户在本机完成的步骤（标定 GUI）  
3. **遵守**分层验收：示例匝道视频只验 L1，不宣称 L3  
4. **不破坏**已发表合同（`examples/`）和隐私规则（无本机绝对路径进 git）

---

## 1. 先读什么（顺序）

```
AI交接说明.md（本文）
    → AGENTS.md（硬规则、目录约定）
    → docs/working.md（最近改了什么）
    → configs/<路口>.json（当前标定了哪些线）
    → 若要改逻辑：src/count_yolo/pipeline.py + geometry.py
    → 若要查历史结论：阶段总结.md
```

人类向的叙事与安装细节在 `交接说明.md`；产品/架构背景在 `docs/prd.md`、`docs/rfc.md`。

---

## 2. 项目状态快照（截至 2026-09-01）

| 项 | 状态 |
|----|------|
| **定位** | 交通调查脚本，非产品；YOLO 检测 + ByteTrack + 几何规则 |
| **稳定能力** | L1 近场过线计数（`--mode line`） |
| **不稳定/未验** | L3 全矩阵（`--mode od`），示例视频上 entry→exit 常为 0 |
| **未实现** | `write_excel.py`、单遍 `--mode fuse`、L3 八区标定 GUI |
| **示例视频** | 根目录 `文锦北路-草埔立交匝道临时.MP4`（gitignore，本机需自备） |
| **已发表全片结果** | `examples/counts_L1_south_through_yolov8m.json` → **1304**（GT 1533，-14.9%） |
| **多断面** | config 内已有 4 条线：`L1_南直行`、`L1_主路`、`L1_匝道`、`L1_右路`（后三条为用户新标） |
| **多线标定** | `annotate --lines "A,B,C"` 一次画多条 |
| **多线计数** | `8m-all` / `count-all` 单遍视频计所有 `line_counting` |

---

## 3. 架构一图

```
MP4 + configs/*.json
        │
        ▼
run.ps1 ──► count_traffic.py（薄包装）
        │         │
        │         ▼
        │   src/count_yolo/cli.py
        │         │
        ├─ annotate ──► annotate.py（OpenCV/matplotlib GUI，需用户操作）
        ├─ count ─────► pipeline.count_line_traffic（单线）
        ├─ count-all ─► pipeline.count_lines_traffic（多线，默认单遍）
        └─ compare ───► compare.py ↔ ground_truth/*.csv
        │
        ▼
output/counts_*.json   （本地产物，勿当发表合同）
examples/*.json        （发表合同，改数字要慎重）
```

**逻辑归属**：只在 `src/count_yolo/` 改；根目录 `count_traffic.py`、`annotate_line.py`、`compare_ground_truth.py` 是兼容入口，禁止把 YOLO 循环写回去。

---

## 4. 关键文件速查

| 路径 | Agent 何时读/改 |
|------|----------------|
| `src/count_yolo/pipeline.py` | 计数主循环；多线 `count_lines_traffic` |
| `src/count_yolo/geometry.py` | 过线、方向过滤、点在多边形内 |
| `src/count_yolo/classify.py` | YOLO 类 → 表列；`truck_small` 是面积启发式 |
| `src/count_yolo/annotate.py` | 标定 GUI；`--lines` 多线流程 |
| `src/count_yolo/cli.py` | 子命令 `count` / `count-all` / `compare` |
| `src/count_yolo/paths.py` | 默认视频、config、模型路径 |
| `configs/文锦北路-草埔立交匝道_临时.json` | `line_counting` 各线坐标与 `maps_to` |
| `ground_truth/*.csv` | L1 比对用 GT |
| `examples/*.json` | 全片精度合同 |
| `run.ps1` | Windows 入口；`8m`/`8m-all`/`ebike-all` 预设 |
| `.env` | 本机 `COUNT_YOLO_PYTHON`（gitignore，勿提交） |

---

## 5. 命令：你能跑什么

工作目录：`adhoc_jobs/count_yolo`

### 5.1 可自主执行（无需 GUI）

```powershell
# 离线单测（不装 torch 也行，CI 同此）
$env:PYTHONPATH="src"
python -m pytest tests/ -q

# 单线计数（冒烟）
.\run.ps1 8m --mode line --line L1_南直行 --device 0 --max-seconds 120

# 多线计数（config 里所有 line_counting，单遍视频）
.\run.ps1 8m-all --device 0

# 指定多线
.\run.ps1 count-all --model models\yolov8m.pt --lines "L1_主路,L1_匝道,L1_右路" --device 0

# 与 GT 比对
.\run.ps1 compare --counts examples\counts_L1_south_through_yolov8m.json --level L1

# debug 叠加视频
.\run.ps1 8m-all --device 0 --max-seconds 120 --debug-video output\debug_all.mp4
```

**注意**：

- PowerShell 下 `--lines` **必须加引号**：`"L1_主路,L1_匝道,L1_右路"`，否则逗号会拆成多个参数  
- 无 GPU 时用 `--device cpu`，全片很慢；优先建议用户用 GPU 或只跑 `--max-seconds 120`  
- 用户明确说「不要冒烟/不要跑计数」时，**不要**后台启动 `8m` / `8m-all`  
- 全片 22 分钟 + 4080 约 11–15 分钟；不要在用户未要求时默认跑全片

### 5.2 需用户在本机完成（你不要代替点鼠标）

```powershell
# 标定（弹窗，必须本机显示器）
.\run.ps1 annotate --lines "L1_主路,L1_匝道,L1_右路" --direction near_to_far --frame 1440
```

操作：`LMB` 点两端 → `n` 下一条 → 全部画完自动保存 → 预览 `output/line_preview.jpg`  
若窗口打不开：检查 `opencv-python` vs `headless` 冲突（见下文坑表）。

### 5.3 环境

- 优先：本目录 `.venv` + `pip install -e ".[runtime]"`  
- 或：`.env` 里 `COUNT_YOLO_PYTHON=` 指向已有 CUDA 环境（**只写 .env，不写进代码/README**）  
- 权重：`models/yolov8m.pt`；电自 `COUNT_YOLO_EBIKE_MODEL` 或 `models/electri_bike_and_vehicle.pt`

---

## 6. 硬约束（违反即错）

1. **改代码** → 同步 `docs/working.md` Changelog  
2. **公开文件** → 无本机绝对路径、无真实密钥/手机/内网地址  
3. **计数 JSON** → `video`/`model` 只写文件名，不写 `D:\...`  
4. **示例匝道视频** → 只验 L1；**禁止**用其证明 L3 或四进口全矩阵  
5. **对向/潮汐** → 用 `require_motion_direction`，**禁止**靠收窄 `x_min`/`x_max` 裁掉同向潮汐道  
6. **发表数字** → 以 `examples/` 为准；`output/` 不可直接当合同提交  
7. **根目录 .py** → 保持薄包装，逻辑进 `src/count_yolo/`  
8. **CI** → 不把 ultralytics/torch 塞进默认 `dev` 依赖  
9. **用户说只看界面** → 只 `annotate`，不偷偷 `count`  
10. **git** → 不提交 `.env`、`*.mp4`、`models/*.pt`、`output/`（已在 gitignore）

---

## 7. 业务口径（避免答错）

| 概念 | 说明 |
|------|------|
| **L1** | 单方向过线；误差先比**转向合计辆次**，车型后置 |
| **L3** | 四进口 × 左/直/右；要标准十字口 + 好机位 |
| **多断面** | 左/中/右三条线各出一个数；**不要**把三个数简单相加当总流量 |
| **8m vs ebike** | 8m 主四轮；ebike 补摩托；单 ebike 出总表会偏低 |
| **最佳已知口径** | 8m 四轮 + ebike 摩托事后拼接 ≈ 1520（-0.8%），fuse 未实现 |
| **truck_small** | 非 YOLO 类，是 truck 框面积 >1.2% 画面时的规则 |
| **GT** | `ground_truth/*.csv`；南直行 22min ≈ **1533** |

---

## 8. 待办优先级（接手后建议）

1. **P0** — 用户有新视频/GT 时：标定线 → `8m-all` → 与 GT 比对  
2. **P1** — `write_excel.py`：JSON → `统计表.xlsx`  
3. **P1** — `--mode fuse`：单遍 8m+ebike，复现 1520  
4. **P2** — `annotate_zones.py` + L3 在**新十字口视频**上验收  
5. **P2** — 多断面 GT 与分车型对照（当前 GT 只有南直行等少量项）

---

## 9. 坑表（Agent 高频翻车）

| 现象 | 原因 | 处理 |
|------|------|------|
| `unrecognized arguments: L1_匝道` | PowerShell 拆逗号 | `--lines "A,B,C"` 加引号 |
| `No module named torch` | `run.ps1` 落到系统 Python | 建 `.venv` 或配 `.env` 的 `COUNT_YOLO_PYTHON` |
| `cuda: False` | 驱动/环境 | 提醒用户检查 GPU；可 `--device cpu` 冒烟 |
| 标定无窗口 | opencv headless | 卸 `opencv-python-headless`，留 `opencv-python` |
| ByteTrack 报缺 `lap` | 首次跟踪 | `pip install lap` 后**重跑同命令** |
| L3 全 0 | 机位/遮挡 | 换 L1，别调阈值到死 |
| 降 conf 无效 | 已验证 0.15=0.25 | 别建议用户再降 conf |
| 全片 duration 1346s | 素材实际时长 | compare 按实际秒数，别硬缩到 22:00 |
| 后台跑计数被用户打断 | 未确认就跑全片/冒烟 | 先问或只听「启动/标定」 |

---

## 10. 改代码时的测试

```powershell
$env:PYTHONPATH="src"
python -m pytest tests/ -q
```

| 改了什么 | 至少跑 |
|----------|--------|
| `geometry.py` | `tests/test_geometry.py` |
| `classify.py` | `tests/test_classify.py` |
| `compare.py` | `tests/test_compare.py` |
| `annotate.py` 解析 | `tests/test_annotate.py` |
| 发布前 | 全量 `tests/` + `tests/test_publishable.py`（若存在） |

有 GPU + 视频时，再跑 `--max-seconds 120` 冒烟；**不要**把全片结果写进 `examples/` 除非用户明确要求更新合同。

---

## 11. 与用户沟通模板

**用户要「启动」** → 先确认：标定界面 / 冒烟 120s / 全片计数 / 仅检查环境  

**用户要「三条断面」** → `annotate --lines "..."` + `8m-all`；提醒三数不相加  

**用户要「交接给同事」** → 指 `交接说明.md`；自己继续会话指本文 + `AGENTS.md`  

**用户要「精度不够」** → 先查 L1 层级、线位、GT 口径；摩托查 ebike/fuse；**不要**先上 L3  

---

## 12. 文档分工

| 文档 | 读者 |
|------|------|
| **AI交接说明.md**（本文） | AI Agent |
| `AGENTS.md` | AI（仓库内常驻规则） |
| `交接说明.md` | 人类接手人 |
| `阶段总结.md` | 原作者搁置后恢复 |
| `README.md` | 对外 / 技术全貌 |
| `docs/working.md` | 变更日志（你改代码要写） |

---

*代码与配置以仓库为准；本文随功能演进更新，重大变更请同步 `docs/working.md`。*
