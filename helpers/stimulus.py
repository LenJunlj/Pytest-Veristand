# -*- coding: utf-8 -*-
"""P2546 左后大屏加热 —— 台架激励封装

全部通道路径与数值照抄自 TestStand 存量序列的结构化 dump
（reports/P2546_左后大屏加热_dump.json，tools/seq_dump.py 产出），
VeriStand 工程：E:\\P2546\\Veristand项目\\p2546.nivsproj（模型 TongYu_IO）。

注意：
- 通道用模型全路径寻址（含 \\），ChannelHelper 对含斜杠的名字直接透传；
- "VlotageControl" 是原模型里的拼写（少了 e），照抄以匹配真实通道名；
- 值域（档位编码、FIU 注入值、NTC 阻值）均照抄存量序列实测值。
"""

_IO = r"Targets\Controller\Simulation Models\Models\TongYu_IO\Parameters\IO"
_CAN_BUS = _IO + r"\CAN IO Model\CAN BUS\MDLSoftECUDataToBus"

# ---- 写通道 ----
CH_HU_HEAT_REQ = _CAN_BUS + r"\HU_SEATSET_3F4_Msg\HU_DrvSeatHeat\Value"    # 加热请求（HU 下发）
CH_KEY_STATE = _CAN_BUS + r"\BCM_VehSt1_2AB_Msg\KeyState\Value"             # 电源模式
CH_ENG_STATE = _CAN_BUS + r"\mrEMS_EngSt1_117_Msg\EngState\Value"           # 发动机状态
CH_CRASH = _CAN_BUS + r"\srP_Msg1_20E_Msg\CrashInfo\Value"                  # 碰撞信息
CH_RES2 = _IO + r"\HardLine IO Model\MDLDataToController\MDLSignalRouting\RES2\Value"  # NTC 阻值模拟
CH_DO0 = _IO + r"\HardLine IO Model\MDLDataToController\MDLSignalRouting\DO0\Value"   # 加热开关（硬线）
CH_PWR_VOLT = _IO + r"\PowerControl\VlotageControl\Value"                   # 程控电源电压（原文拼写）
CH_PWR_CURR = _IO + r"\PowerControl\CurrentControl\Value"                   # 程控电源电流
CH_PWR_ON = _IO + r"\PowerControl\ON//OFF\Value"                            # 程控电源开关（参数名含斜杠，VeriStand 用 // 转义）
CH_PWR_RELAY = _IO + r"\PowerControl\Power_Relay\Value"                     # 电源继电器
CH_IGN = _IO + r"\PowerControl\IGN\Value"                                   # 点火
CH_FIU3_CH9 = _IO + r"\FIU\FIU3_OUT_Channel9\Value"      # NTC 故障注入（本测试"左后"实际用 CH9）
CH_FIU3_CH7 = _IO + r"\FIU\FIU3_OUT_Channel7\Value"      # NTC 故障注入（存量另一处用 CH7，含义待确认）
CH_FIU1_CH1 = _IO + r"\FIU\FIU1OUT_Channel1\Value"       # 加热输出故障注入

# ---- 读通道 ----
# 存量 .seq 误写为 DI1（恒 0）；实测 DI0 随加热请求 0→1 响应，2026-11-06 用户确认
CH_HEAT_OUT_HARD = r"Targets\Controller\Hardware\Chassis\DAQ\Dev1\Digital Input\port0\DI0"
CH_HEAT_OUT_CAN = (r"Targets\Controller\Hardware\Chassis\NI-XNET\CAN\ECU\Incoming"
                   r"\Single-Point\SEAT_DrvStd (993)\IndicatorDrvSeatHeat")

# ---- 值域（照抄存量） ----
HEAT_REQ = {"off": 0.0, "level1": 2.0, "level2": 3.0, "level3": 4.0}
NTC_FAULT = {"short_gnd": 14.0, "short_vcc": 12.0, "open": 8.0}   # FIU3_CH9/CH7 值
OUT_FAULT = {"short_gnd": 1.0, "open": 2.0}                        # FIU1_CH1 值


class Stimulus:
    """台架激励：每个方法对应存量序列里的一组动作步骤。"""

    def __init__(self, channel):
        self.ch = channel

    # 翻译自"测试用例初始化"（Setup 8 步）
    def bench_ready(self):
        c = self.ch
        c.set(CH_PWR_VOLT, 13.5)
        c.set(CH_PWR_CURR, 20.0)
        c.set(CH_PWR_ON, 1.0)
        c.set(CH_PWR_RELAY, 1.0)
        c.set(CH_IGN, 1.0)
        c.set(CH_KEY_STATE, 2.0)
        c.set(CH_ENG_STATE, 1.0)
        c.set(CH_CRASH, 0.0)
        # 原文初始化只清 CH7、结束只清 CH9 —— 统一两个都清，更安全
        c.set(CH_FIU3_CH7, 0.0)
        c.set(CH_FIU3_CH9, 0.0)
        c.set(CH_FIU1_CH1, 0.0)

    # 翻译自"测试用例结束"（Cleanup 8 步）
    def bench_shutdown(self):
        c = self.ch
        c.set(CH_HU_HEAT_REQ, HEAT_REQ["off"])      # 加热请求先撤（增量安全项，原文无此步）
        c.set(CH_FIU3_CH9, 0.0)
        c.set(CH_FIU3_CH7, 0.0)
        c.set(CH_FIU1_CH1, 0.0)
        c.set(CH_PWR_VOLT, 13.5)
        c.set(CH_PWR_CURR, 20.0)
        c.set(CH_PWR_ON, 1.0)
        c.set(CH_PWR_RELAY, 0.0)
        c.set(CH_IGN, 0.0)
        c.set(CH_KEY_STATE, 2.0)
        c.set(CH_ENG_STATE, 0.0)
        c.set(CH_CRASH, 0.0)

    def set_heat_request(self, level: str):
        """level ∈ {'off','level1','level2','level3'} → HU_DrvSeatHeat 0/2/3/4"""
        self.ch.set(CH_HU_HEAT_REQ, HEAT_REQ[level])

    def set_ntc_resistance(self, ohms: float):
        """NTC 阻值模拟（存量用 5500/6500/7500 Ω）"""
        self.ch.set(CH_RES2, float(ohms))

    def heat_switch(self, pressed: bool):
        self.ch.set(CH_DO0, 1.0 if pressed else 0.0)

    def set_supply_voltage(self, volts: float):
        self.ch.set(CH_PWR_VOLT, float(volts))

    def inject_ntc_fault(self, kind: str):
        self.ch.set(CH_FIU3_CH9, NTC_FAULT[kind])

    def clear_ntc_fault(self):
        self.ch.set(CH_FIU3_CH9, 0.0)

    def inject_out_fault(self, kind: str):
        self.ch.set(CH_FIU1_CH1, OUT_FAULT[kind])

    def clear_out_fault(self):
        self.ch.set(CH_FIU1_CH1, 0.0)

    def read_heat_outputs(self) -> dict:
        """翻译自"加热输出状态和LED灯信号采集"（NI_GetVariableValues，有效读数仅 2 路）"""
        return {"hard": self.ch.get(CH_HEAT_OUT_HARD),
                "can": self.ch.get(CH_HEAT_OUT_CAN)}
