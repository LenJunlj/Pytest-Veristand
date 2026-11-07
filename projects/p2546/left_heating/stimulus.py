# -*- coding: utf-8 -*-
"""P2546 左后大屏加热 —— 模块激励（加热档位 / NTC / 输出故障 / 加热开关 / 输出采集）

台架工况（电源/点火/电源模式/发动机/碰撞）继承自项目级 BenchStimulus（common/bench.py）；
本模块通道与值域在 left_heating/channels.py（模块层）。生成依据：
reports/P2546_左后大屏加热_dump.json（tools/seq_dump.py 产出）。
"""
import time

from projects.p2546.common.bench import BenchStimulus
from projects.p2546.left_heating.channels import (
    CH_DO0, CH_FIU1_CH10, CH_FIU1_CH1, CH_HEAT_OUT_CAN, CH_HEAT_OUT_HARD, CH_HU_HEAT_REQ,
    CH_RES2, HEAT_REQ, HEAT_REQ_NONE, NTC_CHANNELS, NTC_FAULT, OUT_FAULT,
)


class Stimulus(BenchStimulus):
    """左后大屏加热激励：每个方法对应存量序列里的一组动作步骤。"""

    def bench_shutdown(self):
        """结束工况前先撤加热请求（增量安全项，原文无此步）：
        先显式 OFF（写 1），再置"无请求"；写 0 本身不等于关加热。"""
        self.ch.set(CH_HU_HEAT_REQ, HEAT_REQ["off"])
        self.ch.set(CH_HU_HEAT_REQ, HEAT_REQ_NONE)
        super().bench_shutdown()

    def set_heat_request(self, level: str):
        """level ∈ {'off','level1','level2','level3'} → HU_DrvSeatHeat 1/2/3/4（0 表示无请求）"""
        self.ch.set(CH_HU_HEAT_REQ, HEAT_REQ[level])

    def request_heat(self, level: str):
        """等价于原文库序列"加热X档请求"：写档位 → 等 1s → 写无请求 → 等 1s。

        该 2s 内部等待是原文时序的一部分（漏掉会让欠压保护等时序判定提前采样）。
        实证 2026-11-06：8.5V 下 DUT 在请求后 3~6s 之间切断输出，原文按 6s 采样。
        """
        self.set_heat_request(level)
        time.sleep(1)
        self.no_heat_request()
        time.sleep(1)

    def no_heat_request(self):
        """翻译自"加热NO Request"：写 0（停发请求，DUT 保持当前状态）"""
        self.ch.set(CH_HU_HEAT_REQ, HEAT_REQ_NONE)

    def set_ntc_resistance(self, ohms: float):
        """NTC 阻值模拟（存量用 5500/6500/7500 Ω）"""
        self.ch.set(CH_RES2, float(ohms))

    def heat_switch(self, pressed: bool):
        self.ch.set(CH_DO0, 1.0 if pressed else 0.0)

    def inject_ntc_fault(self, kind: str, ch: str = "ch9"):
        """NTC 故障注入：ch9=故障恢复系列，ch7=前提/退出条件系列（照抄存量分工）"""
        self.ch.set(NTC_CHANNELS[ch], NTC_FAULT[kind])

    def clear_ntc_fault(self, ch: str = "ch9"):
        self.ch.set(NTC_CHANNELS[ch], 0.0)

    def inject_out_fault(self, kind: str):
        """加热输出故障注入：short_gnd=CH10(2)+CH1(1) / open=CH1(2)，值照抄存量"""
        if kind == "short_gnd":
            self.ch.set(CH_FIU1_CH10, 2.0)
        self.ch.set(CH_FIU1_CH1, OUT_FAULT[kind])

    def clear_out_fault(self):
        """取消加热输出故障：原文只清 CH1（CH10 留在 2）—— 这里同时清 CH10，
        否则短地配置会泄漏给后续用例（实测会让故障恢复-过压误判）。"""
        self.ch.set(CH_FIU1_CH1, 0.0)
        self.ch.set(CH_FIU1_CH10, 0.0)

    def read_heat_outputs(self) -> dict:
        """翻译自"加热输出状态和LED灯信号采集"（NI_GetVariableValues，有效读数仅 2 路）"""
        return {"hard": self.ch.get(CH_HEAT_OUT_HARD),
                "can": self.ch.get(CH_HEAT_OUT_CAN)}
