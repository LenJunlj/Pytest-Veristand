# c206_10 —— C206-10 环境控制器(HIL 测试迁移)

一个项目 = 一套 VeriStand 工程,下含多个 `.seq` 模块。目录名规范成合法 Python 包名
(`C206-10环境控制器 → c206_10`,正式名见 `project.yaml` 的 `name`),与 p2546 同构。

**状态:2026-11-07 建项;同日 sdf 首提取完成**(`docs/c206_10_registry.csv` 443 行,diff 结论见下)。
sdf 本体在 `E:/C206-10项目/Veristand项目/C026-10.nivssdf`(2026-11-07 15:40 版)。
命名说明:sdf 文件名/内部 Root 名 `C026-10` 是当年 VeriStand 建工程的笔误,**正式名 C206-10**
(用户确认 2026-11-07)——不影响调用:通道路径不含 Root 名、attach 按文件路径匹配,详见 project.yaml 注释。

## 首提取 diff 结论(与 p2546,2026-11-07)

- **台架层 100% 复用**:模型同为 TongYu_IO;PowerControl(含 VlotageControl 拼写/默认值)、
  MDLSignalRouting 56 条、FIU 30 路通道本体、CAN1 内部总线 41 报文 166 信号、DAQ Dev1 84 通道
  ——与 p2546 逐项 diff 全部为空
- **项目层零交集**:CAN 矩阵 7 报文(ABS_1/BCM1_2/BCM1_11/EEM_1/GW_Config/IC_1/PDCSlave_2)全新
- **DUT = SCCU(环境控制器)**,走 **CAN2 口**(p2546 是 CAN/ECU 口):读 `SCCU_1 (582)`
  SeatheatInd_TL/TR + TL/TRSeatHeatSwitch、`OTA_VerInfo_SCCU (1130)`;写 BCM1_11 (563)
  `BCM_TL/TRseatHeatLevelSet` 等 15 信号
- **台架层增量更正(2026-11-07)**:DAQ Dev2 计数器 CO0~CO3(频率/占空比)两个项目 sdf 都有(各 8 条),
  非本项目独有(此前误判,已更正);本项目相对 p2546 的真实差异只有 DUT 口(CAN2)与 CAN 矩阵

## 接入步骤(sdf 已到位,剩 3~5)

1. ~~sdf 落位~~ ✅ 2. ~~analyze_sdf 提取~~ ✅ 3. ~~与 p2546 登记表 diff~~ ✅(结论如上)
4. 视分层方案拍板结果建 `common/`(或按 bench_io/ 新结构)
5. 存量 `.seq` 进 `samples/` → `tools/seq_dump.py` → `tools/gen_tests.py` 草稿 → 人工复核迁入

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
