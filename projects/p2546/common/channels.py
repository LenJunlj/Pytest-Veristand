# -*- coding: utf-8 -*-
"""P2546 项目级通道常量与值域（模型 TongYu_IO，跨模块共用）

全部通道路径与数值照抄自 TestStand 存量序列的结构化 dump
（tools/seq_dump.py 产出，如 reports/P2546_左后大屏加热_dump.json），
VeriStand 工程：E:\\P2546\\Veristand项目\\p2546.nivsproj。

注意：
- 通道用模型全路径寻址（含 \\），ChannelHelper 对含斜杠的名字直接透传；
- "VlotageControl" 是原模型里的拼写（少了 e），照抄以匹配真实通道名；
- 值域（档位编码、FIU 注入值、NTC 阻值）均照抄存量序列实测值；
- 模块特有语义（如加热档位）也放这里：同一模型下通道是项目级事实。
"""

_IO = r"Targets\Controller\Simulation Models\Models\TongYu_IO\Parameters\IO"
_CAN_BUS = _IO + r"\CAN IO Model\CAN BUS\MDLSoftECUDataToBus"

# ---- 台架工况（项目级：电源/点火/电源模式/发动机/碰撞） ----
CH_KEY_STATE = _CAN_BUS + r"\BCM_VehSt1_2AB_Msg\KeyState\Value"             # 电源模式
CH_ENG_STATE = _CAN_BUS + r"\mrEMS_EngSt1_117_Msg\EngState\Value"           # 发动机状态
CH_CRASH = _CAN_BUS + r"\srP_Msg1_20E_Msg\CrashInfo\Value"                  # 碰撞信息
CH_PWR_VOLT = _IO + r"\PowerControl\VlotageControl\Value"                   # 程控电源电压（原文拼写）
CH_PWR_CURR = _IO + r"\PowerControl\CurrentControl\Value"                   # 程控电源电流
CH_PWR_ON = _IO + r"\PowerControl\ON//OFF/Value"                            # 程控电源开关（参数名含斜杠，VeriStand 用 // 转义）
CH_PWR_RELAY = _IO + r"\PowerControl\Power_Relay\Value"                     # 电源继电器
CH_IGN = _IO + r"\PowerControl\IGN\Value"                                   # 点火

# ---- 加热（HU 请求 / NTC / 输出故障 / 硬线开关） ----
CH_HU_HEAT_REQ = _CAN_BUS + r"\HU_SEATSET_3F4_Msg\HU_DrvSeatHeat\Value"    # 加热请求（HU 下发）
CH_RES2 = _IO + r"\HardLine IO Model\MDLDataToController\MDLSignalRouting\RES2\Value"  # NTC 阻值模拟
CH_DO0 = _IO + r"\HardLine IO Model\MDLDataToController\MDLSignalRouting\DO0\Value"   # 加热开关（硬线）
CH_FIU3_CH9 = _IO + r"\FIU\FIU3_OUT_Channel9\Value"      # NTC 故障注入：故障恢复系列用 CH9
CH_FIU3_CH7 = _IO + r"\FIU\FIU3_OUT_Channel7\Value"      # NTC 故障注入：前提/退出条件系列用 CH7
NTC_CHANNELS = {"ch7": CH_FIU3_CH7, "ch9": CH_FIU3_CH9}
CH_FIU1_CH1 = _IO + r"\FIU\FIU1OUT_Channel1\Value"       # 加热输出故障注入（开路=2 / 短地=1）
CH_FIU1_CH10 = _IO + r"\FIU\FIU1OUT_Channel10\Value"     # 加热输出短地配合通道（短地时=2，照抄存量）

# ---- 采集（读） ----
# 存量 .seq 误写为 DI1（恒 0）；实测 DI0 随加热请求 0→1 响应，2026-11-06 用户确认
CH_HEAT_OUT_HARD = r"Targets\Controller\Hardware\Chassis\DAQ\Dev1\Digital Input\port0\DI0"
CH_HEAT_OUT_CAN = (r"Targets\Controller\Hardware\Chassis\NI-XNET\CAN\ECU\Incoming"
                   r"\Single-Point\SEAT_DrvStd (993)\IndicatorDrvSeatHeat")

# ---- 值域（照抄存量） ----
# 加热请求编码（实证，2026-11-06 评审）：0=无请求（DUT 保持原状态）/ 1=OFF / 2=一档 / 3=二档 / 4=三档
# 依据：库序列"加热三档请求"= 写4→等1s→写0→等1s，而历史报告随后采到 CAN 仍为 4（说明 0 不是 OFF）；
#       序列"加热OFF"= 写1→等1s→写0，报告实测 CAN=1。
HEAT_REQ = {"off": 1.0, "level1": 2.0, "level2": 3.0, "level3": 4.0}
HEAT_REQ_NONE = 0.0     # "加热NO Request"：不改变当前档位
# 发动机状态编码（照抄存量"设置发动机状态X"写入值）
ENG_STATE = {"not_running": 0.0, "running": 1.0, "crank": 2.0, "fault": 3.0}
NTC_FAULT = {"short_gnd": 14.0, "short_vcc": 12.0, "open": 8.0}   # FIU3_CH9/CH7 值
OUT_FAULT = {"short_gnd": 1.0, "open": 2.0}                        # FIU1_CH1 值
