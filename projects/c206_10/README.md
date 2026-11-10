# c206_10 —— C206-10 环境控制器(HIL 测试迁移)

一个项目 = 一套 VeriStand 工程,下含多个 `.seq` 模块。目录名规范成合法 Python 包名
(`C206-10环境控制器 → c206_10`,正式名见 `project.yaml` 的 `name`),与 p2546 同构。

**状态(2026-11-09)**:建项 + sdf 首提取 + **三个 .seq 模块全部翻译完成并上台架实跑**:
左后三排加热 29 条、右后三排加热 27 条、功能 DTC 12 条 = **68 条 hil 用例**
（右后 09「加热上下电不记忆挡位」按用户拍板 2026-11-09 删除：DUT 实测上电后恢复加热，与原文期望冲突）。
首轮全量(排除 slow,69 条时):**57 passed / 8 failed / 20 分 40 秒**;失败均为原文期望或时序缺陷,
详见 [docs/C206-10执行报告_20261109.md](../../docs/C206-10执行报告_20261109.md)。
sdf 本体在 `E:/C206-10项目/Veristand项目/C026-10.nivssdf`(2026-11-07 15:40 版);
命名说明:sdf 文件名/内部 Root 名 `C026-10` 是当年建工程笔误,**正式名 C206-10**
(不影响调用:通道路径不含 Root 名、attach 按文件路径匹配)。

## 结构

| 位置 | 作用 |
|---|---|
| `project.yaml` | 项目级配置:显示名、veristand 段(sdf 路径)、模块清单 |
| `common/channels.py` | 项目层通道:模型前缀 + C206-10 CAN 矩阵(与 p2546 零交集) |
| `common/bench.py` | 台架工况基类(电源/电源模式/整车电源模式/OTA/能量限制/报文使能) |
| `common/seat_heating.py` | 座椅加热通用激励(左右模块共用,差异在子类绑定) |
| `common/checks.py` | EQ 断言(`assert_seat`)与 DTC 字符串判定(`assert_dtc`) |
| `common/diag.py` | UDS 诊断(PCAN-USB;清码/读 DTC,复刻存量 Check_DTC1.py 时序) |
| `left_rear_heating/` | 模块:channels + stimulus + conftest + module.yaml + tests/test_all.py(29 条) |
| `right_rear_heating/` | 同上(27 条,缺号 09 已删),差异:TR/DI1/CH8/DO1/开路值 2 |
| `dtc/` | 功能 DTC(12 条):故障注入 + 诊断 + 报文丢失 |
| `samples/` | 三个存量 `.seq` |

## 运行

```bat
:: 只能按项目跑(框架限制:一次 pytest 会话只允许一个项目)
F:\TongYuTestScript\python.exe -m pytest projects\c206_10\left_rear_heating
F:\TongYuTestScript\python.exe -m pytest projects\c206_10\right_rear_heating
F:\TongYuTestScript\python.exe -m pytest projects\c206_10\dtc

:: 排除耐久/长时(07/08 耐久 1800s、2696s+600s;DTC 11/12 各约 70s 以上)
... -m "not slow"
```

前置:前台 VeriStand 部署并运行 `C026-10.nivssdf`(attach 模式按路径匹配);
DTC 模块另需 PCAN-USB(PCAN_USBBUS1, 500k)与 DUT 诊断可达。

## 翻译要点(改代码必读)

- **判定语义 EQ**:`实测 == Limits.Low`,`High` 是模板残值(0/11/`FileGlobals.VOLT/2+1`)。
  DTC 是 String Limit:`Limits.String = "True"/"False"`,`Comp=IgnoreCase`。
- **加热请求编码**:1=OFF / 2/3/4=一/二/三档 / **0=无请求(DUT 保持当前档位)**。
  本地序列"本地打开加热X档"= 写档位 → 0.4s → 写 0(见 `common/seat_heating.py`)。
- **状态值**:CAN `SeatheatInd_TL/TR` 1/2/3 = 一/二/三档;硬线 DI0(TL)/DI1(TR) = 1 表示加热中。
- **档位灯(台架实测 2026-11-09)**:左1/2/3 = **DI8/DI9/DI10**,右1/2/3 = **DI5/DI6/DI7**。
  存量 .seq 写的左 DI2/DI3/DI4 在 2026-11-07 重建 sdf 后已失效(恒 0)——按台架修正,原文映射记在 channels.py 注释。
- **"Wait" 步骤**:dump 里的 `SeqCallName` 是残留字段,**步骤名 Wait 即真实等待**,时长取 `TimeExpr`。
- **NTC 通道(台架实测)**:主驾/左后 = **FIU3_OUT_Channel9**,副驾/右后 = **FIU3_OUT_Channel8**;
  原文主驾写 CH7,全通道扫描证实 CH7 无任何效果(CH9→90E211/90E215,CH8→90E811/90E815)。
- **采集时点**:原文"报文硬线采集"在 Wait 之前 → `capture()` 后 sleep 再断言,保持原采样时刻。
- **名/值不符(存量缺陷,已自动标注)**:设置电源步骤名里的电压常与写入值不符(如名 16.5V 写 16.7V、
  名 8.5V 写 8.4V、名 13.5V 写 9.5V);以写入值为准,`⚠` 注释逐条标出。
- **耐久_2 的快照缺陷**:原文先采集、再等 600s、再断言 → 断言读的是等待前快照;已照抄并标注。

## 首提取 diff 结论(与 p2546,2026-11-07)

- **台架层 100% 复用**:模型同为 TongYu_IO;PowerControl、MDLSignalRouting 56 条、FIU 30 路、
  CAN1 内部总线 41 报文 166 信号、DAQ Dev1 84 通道、Dev2 计数器 —— 逐项一致
- **项目层零交集**:CAN 矩阵(BCM1_2/BCM1_11/EEM/GW_Config/ABM/EMS/VCU/IHU/TBOX 等)与 p2546 无重叠
- **DUT = SCCU**,走 **CAN2 口**:读 `SCCU_1 (582)` `SeatheatInd_TL/TR`;写 `BCM1_11_233_Msg`
  `BCM_TL/TRseatHeatLevelSet`

## 待确认

- 台架实跑尚未进行(需部署 C026-10 并接 DUT);首次运行建议先单条:使能 16.5V / 一档命令 / 一条温度 DTC。
- DTC 原文缺陷见 `dtc/tests/test_all.py` 头注(03 两次期望 False、04 只等 1s、09 标签"短地"写 CH1=8)。
