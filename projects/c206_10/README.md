# c206_10 —— C206-10 环境控制器(HIL 测试迁移)

一个项目 = 一套 VeriStand 工程,下含多个 `.seq` 模块。目录名规范成合法 Python 包名
(`C206-10环境控制器 → c206_10`,正式名见 `project.yaml` 的 `name`),与 p2546 同构。

**状态:2026-11-07 建项,sdf 待接入**(放入 `samples/` 后告知路径即可)。

## 接入步骤(sdf 到位后)

1. `python tools/analyze_sdf.py "projects/c206_10/samples/<sdf文件>" reports/c206_10_analysis`
   → 出本项目通道登记表(三层归层)
2. 与 `docs/bench_io_registry.csv`(p2546 版)diff:台架层通道(FIU/电源/RES/DAQ/CAN1)
   应大面积复用 → 通道分层方案 D2(相对标识+拼前缀)的直接验证
3. 视 diff 结果拍板:沿用 p2546 的 `common/` 模式,或等 bench_io/ 分层落地后按新结构建
4. 存量 `.seq` 进 `samples/` → `tools/seq_dump.py` → `tools/gen_tests.py` 草稿 → 人工复核迁入

## 结构(随接入逐步成形)

| 位置 | 作用 |
|---|---|
| `project.yaml` | 项目级配置:显示名、veristand 覆盖段(sdf 路径待回填)、模块清单 |
| `samples/` | sdf 与 `.seq` 落地区 |
| `common/` | 待建:通道常量/工况基类/断言(按新 sdf 重建,勿照抄 TongYu_IO) |
| `<模块>/` | 待建:一个 `.seq` 一个模块(module.yaml + stimulus.py + tests/) |

## 与 p2546 的差异注意

- 模型名/模型前缀未知 → 一切全路径以新 sdf 提取为准,`tools/analyze_sdf.py` 参数化可直接跑
- `BenchStimulus` 前提(Setup/Cleanup 同构)**未证实** → 拿到 .seq 先 dump 核对,再决定是否继承
- 判定语义(EQ 等值)、请求编码(0≠OFF)、库序列 2s 时基是 p2546 实证结论,**不自动沿用**,以新 dump 为准
