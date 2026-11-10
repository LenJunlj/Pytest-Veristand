# -*- coding: utf-8 -*-
"""C206-10 项目层通道 —— 模型前缀 + 本项目 CAN 矩阵 + 整车值域（跨模块共用）

三层分工（docs/通道分层方案.md）：
- 台架层  bench_io/channels.py   通道本体（电源/FIU/DAQ/信号路由），跨项目不动
- 项目层  本文件                 模型前缀 + C206-10 的 CAN 矩阵（与 p2546 零交集）
- 模块层  <模块>/channels.py     功能绑定（TL/TR、DI 分工）+ 模块值域

来源：projects/c206_10/samples/*.seq → reports/c206_*_deep.json（tools/seq_dump.py 产出）。
DUT = SCCU（环境控制器），走 CAN2 口（p2546 是 CAN/ECU 口），故 DUT 状态信号在
Hardware/.../CAN/CAN2/Incoming 下；激励侧仍是模型软 ECU（MDLSoftECUDataToBus）。

拼接约定：台架层存相对标识（前斜杠、无前缀），本文件 bench() 拼全路径；
全路径经 ChannelHelper 自动转正斜杠并分流参数 API（见 helpers/channel.py 头注）。
"""
_MODEL = "TongYu_IO"     # 与 projects/c206_10/project.yaml 的 model_name 同源
_PREFIX = "Targets/Controller/Simulation Models/Models/%s/Parameters" % _MODEL
_CAN_BUS = _PREFIX + "/IO/CAN IO Model/CAN BUS/MDLSoftECUDataToBus"
_DUT_CAN = "Targets/Controller/Hardware/Chassis/NI-XNET/CAN/CAN2/Incoming/Single-Point"


def bench(rel: str) -> str:
    """台架层相对标识 → 模型参数全路径（前斜杠）。rel 形如 "IO/FIU/FIU3_OUT_Channel7/Value"。"""
    return _PREFIX + "/" + rel


def can(msg: str, sig: str) -> str:
    """车型 CAN 矩阵信号（软 ECU 下发）→ 全路径。sig 可含子路径（如 SwitchX/Manu_Value）。"""
    return _CAN_BUS + "/" + msg + "/" + sig + "/Value"


def dut(msg: str, sig: str) -> str:
    """DUT 发出的 CAN 状态信号（CAN2 Incoming）→ 全路径。"""
    return _DUT_CAN + "/" + msg + "/" + sig


# ---- 座椅加热请求（BCM 下发，模块层区分 TL/TR） ----
CH_HEAT_LVL_TL = can("BCM1_11_233_Msg", "BCM_TLseatHeatLevelSet")
CH_HEAT_LVL_TR = can("BCM1_11_233_Msg", "BCM_TRseatHeatLevelSet")

# ---- 整车状态（本地 .seq 前提/退出/触发条件系列写这些） ----
CH_POWER_MODE = can("BCM1_2_232_Msg", "PowerMode")                    # 电源模式
CH_VDC_POWER_MODE = can("GW_Config_2B0_Msg", "VDC_PowerMode")         # 整车电源模式（4=Standby/3=Pre_Off/5=Pre_On/6=Driving）
CH_OTA_MODE = can("GW_Config_2B0_Msg", "GW_OTAMode")                  # OTA 模式（1=OTA 中）
CH_ENERGY_LIMIT = can("EEM_1_2B2_Msg", "EEM_PowerLimitSignal")        # 电能限制等级（1=无限制，2~5 逐级限制）
CH_ENERGY_LIMIT_MANU = can("EEM_1_2B2_Msg", "SwitchEEM_PowerLimitSignal/Manu_Value")  # 手动电能限制开关

# ---- 报文使能（DTC 系列模拟报文/节点丢失） ----
CH_EN_BCM1_11 = can("BCM1_11_233_Msg_Enable", "Switch")
CH_EN_BCM1_2 = can("BCM1_2_232_Msg_Enable", "Switch")
CH_EN_EEM = can("EEM_1_2B2_Msg_Enable", "Switch")

# ---- 值域（照抄存量 .seq 写入值） ----
# 加热请求编码（实证：本地打开加热X档 = 写档位→0.4s→写0）：
#   0=无请求（DUT 保持）/ 1=OFF / 2=一档 / 3=二档 / 4=三档
HEAT_REQ = {"off": 1.0, "level1": 2.0, "level2": 3.0, "level3": 4.0}
HEAT_REQ_NONE = 0.0
# FileGlobals 档位常量（原文 座椅加热一档=1 / 二档=2 / 三档=3，作为库序列入参）
HEAT_LEVEL_ARG = {"level1": 1.0, "level2": 2.0, "level3": 3.0}
