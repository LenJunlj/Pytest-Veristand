# -*- coding: utf-8 -*-
"""C206-10 功能 DTC 模块激励：座椅加热动作（左/右绑定）+ 诊断 + 报文使能。

座椅加热动作复用 common/seat_heating.py；本模块额外提供 UDS 诊断与双侧通道绑定。
注意：诊断走 PCAN-USB（PCAN_USBBUS1），不是 VeriStand 的 CAN2；与台架通道并存。
"""
import allure

from projects.c206_10.common import diag
from projects.c206_10.common.seat_heating import SeatHeatingStimulus
from projects.c206_10.dtc.channels import (
    CH_CAN_IND_TL, CH_CAN_IND_TR, CH_FIU1_CH1, CH_FIU1_CH10, CH_FIU3_NTC_TL, CH_FIU3_NTC_TR,
    CH_HARD_TL, CH_HARD_TR, CH_HEAT_LVL, CH_SWITCH_TL, CH_SWITCH_TR, NTC_FAULT, OUT_FAULT_TL,
    OUT_FAULT_TR,
)


class Stimulus(SeatHeatingStimulus):
    # 座椅加热基类默认绑左后（输出开路用例判 TL）；TR 用下面的专有方法
    CH_HEAT_LVL = CH_HEAT_LVL
    CH_CAN_IND = CH_CAN_IND_TL
    CH_HARD_OUT = CH_HARD_TL
    CH_LIGHTS = ()                    # DTC 不需要档位灯
    CH_FIU3_NTC = CH_FIU3_NTC_TL
    CH_FIU1_CH1 = CH_FIU1_CH1
    CH_FIU1_CH10 = CH_FIU1_CH10
    CH_SWITCH = CH_SWITCH_TL
    CH_RES1 = None
    NTC_FAULT = NTC_FAULT
    OUT_FAULT = OUT_FAULT_TL

    def request_heat_side(self, level: str, side: str = "tl", hold: float = 0.4):
        """按侧写档位请求（0.4s 后写 0），用于输出开路用例判 TR。"""
        from projects.c206_10.common.channels import CH_HEAT_LVL_TR, HEAT_REQ, HEAT_REQ_NONE
        import time
        ch = self.CH_HEAT_LVL if side == "tl" else CH_HEAT_LVL_TR
        self.ch.set(ch, HEAT_REQ[level])
        time.sleep(hold)
        self.ch.set(ch, HEAT_REQ_NONE)

    # ---- 双侧故障注入 / 采集 ----
    def inject_ntc_fault(self, kind: str, side: str = "tl"):
        self.ch.set(CH_FIU3_NTC_TL if side == "tl" else CH_FIU3_NTC_TR, NTC_FAULT[kind])

    def clear_ntc_fault(self, side: str = "tl"):
        self.ch.set(CH_FIU3_NTC_TL if side == "tl" else CH_FIU3_NTC_TR, 0.0)

    def inject_out_fault(self, kind: str, side: str = "tl"):
        """侧向输出故障：tl=CH1=8 + CH10=2（原文"短地"）；tr=CH1=2（原文"开路"）"""
        if side == "tl":
            self.ch.set(CH_FIU1_CH10, 2.0)
            self.ch.set(CH_FIU1_CH1, OUT_FAULT_TL[kind])
        else:
            self.ch.set(CH_FIU1_CH1, OUT_FAULT_TR[kind])

    def clear_out_fault(self):
        self.ch.set(CH_FIU1_CH1, 0.0)
        self.ch.set(CH_FIU1_CH10, 0.0)

    def press_back_switch(self, pressed: bool = True, side: str = "tl"):
        self.ch.set(CH_SWITCH_TL if side == "tl" else CH_SWITCH_TR, 1.0 if pressed else 0.0)

    def capture_side(self, side: str = "tl") -> dict:
        """输出开路用例只判硬线 + CAN 两项（原文只有这两步判定）。"""
        return {"hard": self.ch.get(CH_HARD_TL if side == "tl" else CH_HARD_TR),
                "can": self.ch.get(CH_CAN_IND_TL if side == "tl" else CH_CAN_IND_TR),
                "lights": []}

    # ---- 诊断（UDS over PCAN） ----
    def clear_dtc(self, req_id: str = "762"):
        with allure.step("DTC 清除（ClearDiagnosticInformation, 请求 ID %s）" % req_id):
            return diag.clear_dtc(req_id)

    def read_dtc(self, code: str, req_id: str = "762", resp_id: str = "76A") -> str:
        """读 DTC 列表并判断指定码是否处于"本次操作循环故障"状态；返回 'True'/'False'。"""
        return diag.check_dtc(req_id, resp_id, code)
