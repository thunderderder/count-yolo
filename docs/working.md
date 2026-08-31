# working.md

## Changelog

### 2026-08-31

- 按 project_scaffold 把目录收成可公开的独立项目：`src/`、`scripts/`、`tests/`、`docs/`、CI、`.env.example`
- 切断对其它项目 venv / 权重路径的硬编码；Python 只认本目录 `.venv` 或 `COUNT_YOLO_PYTHON`
- 计数 JSON 改为只写视频和权重的文件名，不再写本机绝对路径
- 离线单测覆盖过线几何、车型映射、L1 误差带；全片对照不再把 1346s 素材缩放到名义 22:00
- CI 不安装 torch
- 离线单测 14 passed；GPU 全片计数 skipped（依赖本地视频与权重）
- 隐私扫描：tracked 文件无本机绝对路径、无 1Password 引用；`alice@example.com` 为 pyproject 占位作者邮箱
- 视频、权重、xlsx、debug mp4 纳入 gitignore，全片结果以 `examples/` 作为发表合同
- 将 120 秒 L1 debug 画面收入 `docs/assets/`，README 用作过线链路的可视化验证（非全片精度合同）

### 2026-07-28

- L1 全片实验：yolov8m 1304（-14.9%），ebike 1112（-27.5%），四轮+摩托拼接 1520（-0.8%）
- 确认 conf 0.15 与 0.25 全片结果相同
- 方向过滤替代收窄 x，避免潮汐车道漏计

## Lessons Learned

- 根目录三个 `.py` 是兼容包装，逻辑在 `src/count_yolo/`。不要把 YOLO 循环写回根目录。
- 示例匝道视频只是 L1 素材。L3 在这段视频上轨迹为 0 是机位问题，不是「再调阈值就能好」。
- `truck_small` 不是模型类别，是面积启发式。改映射时单测 `test_classify.py`。
- 发表数字以 `examples/` 为准。`output/` 里的 JSON 往往带本机路径，不能直接提交。
- 全片 JSON 的 duration 可能是 1346s，名义对照窗口是 22:00。误差带按同一段素材的原始辆次算，只有明显短于全片的冒烟才外推。
- 本机若要复用已有 CUDA 环境，只通过 `.env` 指过去，不要把那个路径写进 README。
