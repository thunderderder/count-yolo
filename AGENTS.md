# AGENTS.md — count_yolo

交叉口视频流量计数的局部规则。接手本目录时先读本文；**AI 会话**另读 [`AI交接说明.md`](AI交接说明.md)，再读 `README.md`。

## 这个项目是什么

给交通调查赋能的脚本：YOLO 检测 + ByteTrack 跟踪 + 几何规则，把固定机位视频数成「进口 × 转向 × 车型」辆次。不是产品，不训练模型。当前稳定交付 **L1 近场过线计数** + **本机 Web 控制台**（`.\run.ps1 serve`）。

公开仓库定位是个人项目库里的附件证据，不是主打作品。

## 目录约定

| 路径 | 用途 | 能否删改 |
|------|------|----------|
| `src/count_yolo/` | 可复用源码 | 改逻辑主要在这里 |
| `scripts/` | 启动包装（`run.ps1` / `run.sh`） | 保持子命令稳定 |
| `tests/` | 离线单测，不碰 GPU / 视频 | 改纯逻辑必须带测 |
| `configs/` / `ground_truth/` | 示例路口标定与人工对照 | 可增样本，勿改已发表口径除非同步 examples |
| `examples/` | 已发表全片结果（无本机绝对路径） | 当合同，勿随手改数字 |
| `docs/` | prd / rfc / working / test | 改完代码更新 `working.md` |
| `count_traffic.py` 等根目录脚本 | 兼容入口 | **薄包装，不要把逻辑写回去** |
| `models/*.pt`、`*.mp4`、`output/` | 本地权重、视频、运行产物 | gitignore，不要提交 |

## 环境

Python ≥ 3.10。离线测试只需要 `pip install -e ".[dev]"`。跑视频计数再装 `".[runtime]"`（含 CUDA 版 PyTorch 时体积很大，不要在仓库根再装一份）。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python -m pytest tests/ -q
```

本机已有 GPU 环境时，可把可执行文件写进 `.env` 的 `COUNT_YOLO_PYTHON`，不要把路径写进代码。

## 硬规则

1. 改完代码更新 `docs/working.md` 当日 Changelog。
2. 频繁小 commit，不要把文档、搬家、测通混成一次提交。
3. 公开文件禁止本机绝对路径、真实邮箱、真实手机号、内部服务器、1Password 引用。计数 JSON 只写文件名，不写盘符路径。
4. 示例视频只验 L1。不要用它宣称 L3 全矩阵可用。
5. 对向 / 潮汐车道靠 `require_motion_direction`（Job + config），阈值在 Job 的 `motion_min_dy_*`；不要靠收窄 x 裁线。
6. CI 只跑离线单测。不要把 ultralytics / torch 塞进默认 `dev` 依赖。

## 兼容入口（勿删）

| 入口 | 说明 |
|------|------|
| `.\run.ps1 serve \| run-job \| 8m \| 8m-all \| annotate \| compare` | 日常入口 |
| `python count_traffic.py` | 计数兼容入口 |
| `python annotate_line.py` | 标定兼容入口 |
| `python compare_ground_truth.py` | GT 比对兼容入口 |

## 相关文档

- 对外说明：`README.md`
- 需求：`docs/prd.md`
- 架构：`docs/rfc.md`
- **本地 Web / Job**：[`docs/rfc_local_console.md`](docs/rfc_local_console.md)（v1 已实现）、[`docs/input_config.md`](docs/input_config.md)
- changelog：`docs/working.md`
- 测试策略：`docs/test.md`
- 搁置恢复：`阶段总结.md`
- 人类接手：`交接说明.md`
- **AI 接手：`AI交接说明.md`**
