# 测试策略

## Unit（CI 默认，必须绿）

覆盖不依赖视频、权重、GPU 的纯逻辑：

- `tests/test_geometry.py`：过线判定、运动方向、点在多边形内
- `tests/test_classify.py`：truck 面积分流、自定义类别名、行人丢弃
- `tests/test_compare.py`：时间解析、L1 误差带、失败阈值

命令：`python -m pytest tests/ -q`

没有 YOLO 推理测试。把 ultralytics 放进 CI 会把 runner 变成装 torch 的作业，和这个仓库的附件定位不匹配。

## Integration（本机 opt-in）

有 GPU、有示例 MP4、有 `yolov8m.pt` 时：

```powershell
.\run.ps1 8m --mode line --line L1_南直行 --device 0 --max-seconds 120
.\run.ps1 compare --counts output\counts_L1_南直行_8m.json --level L1
```

冒烟看 JSON 能否写出、debug 视频黄线是否压在近场车道上。120 秒结果不能外推成全片精度。

全片对照合同是 `examples/counts_L1_south_through_yolov8m.json`（1304）。复现墙钟在 RTX 4080 Super 上大约 11–15 分钟。

## E2E

没有浏览器或服务端。标定 GUI 只能本机手工看：两点、保存、`output/line_preview.jpg`。

## 怎样算验证完成

1. `pytest tests/` 全过。
2. 若改了过线或方向逻辑：至少 120 秒 debug 视频，确认对向车不被计。
3. 若改了发表口径：同步 `examples/` 与 `阶段总结.md` §7，并说明是否重新跑了全片。
4. 公开提交前：仓库内无本机绝对路径、无 `.env`、无 `.pt` / `.mp4` / `.xlsx`。
