# -*- coding: utf-8 -*-
"""C206-10 座椅加热模块通用激励（左后/右后共用，差异全在子类的通道绑定）

原文三个 .seq 的座椅加热动作完全同构，只有"哪一侧"不同：
    请求 BCM_TL/TRseatHeatLevelSet、状态 SeatheatInd_TL/TR、硬线 DI0/DI1、
    NTC 注入 CH7/CH8、后三排开关 DO0/DO1、输出开路值 8/2。
子类只覆盖类属性（见 left_rear_heating/stimulus.py、right_rear_heating/stimulus.py）。

时序依据（reports/c206_*_deep.json）：
- 本地打开加热X档 = 写档位 → Wait 0.4s → 写 0（0=无请求，DUT 保持档位）
- 报文硬线采集 = 读 CAN 状态 1 路 + 硬线 1 路 + 6 路灯（无等待）；原文随后 Wait 1s 才断言
"""
import time

from projects.c206_10.common.bench import BenchStimulus
from projects.c206_10.common.channels import HEAT_REQ, HEAT_REQ_NONE

REQUEST_HOLD_S = 0.4


class SeatHeatingStimulus(BenchStimulus):
    """座椅加热激励基类；子类绑定通道常量与值域。"""

    # ---- 子类必须覆盖 ----
    CH_HEAT_LVL = None
    CH_CAN_IND = None
    CH_HARD_OUT = None
    CH_LIGHTS = ()
    CH_FIU3_NTC = None
    CH_FIU3_NTC_LEGACY = None       # 原文用过的陈旧通道（已失效），清理时一并归零
    CH_FIU1_CH1 = None
    CH_FIU1_CH10 = None
    CH_SWITCH = None
    CH_RES1 = None
    NTC_FAULT = {}
    OUT_FAULT = {}

    def set_heat_level(self, code: float):
        """直接写请求码（0=无请求 / 1=OFF / 2/3/4=一/二/三档）。"""
        self.ch.set(self.CH_HEAT_LVL, float(code))

    def request_heat(self, level: str, hold: float = REQUEST_HOLD_S):
        """翻译自本地序列"本地打开加热X档"：写档位 → 0.4s → 写无请求。"""
        self.set_heat_level(HEAT_REQ[level])
        time.sleep(hold)
        self.set_heat_level(HEAT_REQ_NONE)

    def no_heat_request(self):
        self.set_heat_level(HEAT_REQ_NONE)

    # ---- 故障注入 ----
    def inject_ntc_fault(self, kind: str):
        self.ch.set(self.CH_FIU3_NTC, self.NTC_FAULT[kind])

    def clear_ntc_fault(self):
        self.ch.set(self.CH_FIU3_NTC, 0.0)
        if self.CH_FIU3_NTC_LEGACY:
            self.ch.set(self.CH_FIU3_NTC_LEGACY, 0.0)

    def inject_out_fault(self, kind: str):
        self.ch.set(self.CH_FIU1_CH1, self.OUT_FAULT[kind])

    def clear_out_fault(self):
        """CH1 与 CH10 都清：原文只清被写的通道，CH10 会泄漏给后续用例。"""
        self.ch.set(self.CH_FIU1_CH1, 0.0)
        self.ch.set(self.CH_FIU1_CH10, 0.0)

    # ---- 开关 / NTC 阻值 ----
    def press_back_switch(self, pressed: bool = True):
        self.ch.set(self.CH_SWITCH, 1.0 if pressed else 0.0)

    def set_ntc_resistance(self, ohms: float):
        self.ch.set(self.CH_RES1, float(ohms))

    # ---- 采集（翻译自"报文硬线采集"） ----
    def capture(self) -> dict:
        return {
            "hard": self.ch.get(self.CH_HARD_OUT),
            "can": self.ch.get(self.CH_CAN_IND),
            "lights": [self.ch.get(c) for c in self.CH_LIGHTS],
        }
