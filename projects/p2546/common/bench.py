# -*- coding: utf-8 -*-
"""P2546 项目级台架工况基类（跨模块共用：电源/点火/电源模式/发动机/碰撞/FIU 复位）

翻译自存量各 .seq 的"测试用例初始化 / 测试用例结束"（两份 .seq 里完全一致）。
模块特有的激励（如加热档位、NTC 注入）在各自模块的 stimulus.py 里继承本类扩展。
"""
from projects.p2546.common.channels import (
    CH_CRASH, CH_ENG_STATE, CH_FIU1_CH10, CH_FIU1_CH1, CH_FIU3_CH7, CH_FIU3_CH9,
    CH_IGN, CH_KEY_STATE, CH_PWR_CURR, CH_PWR_ON, CH_PWR_RELAY, CH_PWR_VOLT, ENG_STATE,
)


class BenchStimulus:
    """台架工况：电源/点火/电源模式/发动机/碰撞，以及进入/退出复位。"""

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
        c.set(CH_FIU1_CH10, 0.0)     # 原文初始化也不清，但短地时会写 2，不清会泄漏给后续用例

    # 翻译自"测试用例结束"（Cleanup 8 步）。模块如需先撤自己的激励（如加热请求），重写本方法
    def bench_shutdown(self):
        c = self.ch
        c.set(CH_FIU3_CH9, 0.0)
        c.set(CH_FIU3_CH7, 0.0)
        c.set(CH_FIU1_CH1, 0.0)
        c.set(CH_FIU1_CH10, 0.0)
        c.set(CH_PWR_VOLT, 13.5)
        c.set(CH_PWR_CURR, 20.0)
        c.set(CH_PWR_ON, 1.0)
        c.set(CH_PWR_RELAY, 0.0)
        c.set(CH_IGN, 0.0)
        c.set(CH_KEY_STATE, 2.0)
        c.set(CH_ENG_STATE, 0.0)
        c.set(CH_CRASH, 0.0)

    def set_supply_voltage(self, volts: float):
        self.ch.set(CH_PWR_VOLT, float(volts))

    def set_crash(self, crashed: bool):
        """整车碰撞状态（原文"设置整车碰撞"/"设置整车无碰撞"）：1=碰撞，0=无碰撞"""
        self.ch.set(CH_CRASH, 1.0 if crashed else 0.0)

    def set_engine_state(self, state: str):
        """发动机状态（原文"设置发动机状态X"）：running=1 / not_running=0 / crank=2 / fault=3"""
        self.ch.set(CH_ENG_STATE, ENG_STATE[state])

    def set_power_mode(self, key_state: float, ign_valid: bool):
        """电源模式 + 硬线 IGN（原文"设置电源模式X&硬线IGN无效/有效"）。

        KeyState 编码照抄存量：OFF=0 / ACC=1 / ON(RUN)=2 / CRANK+IG=3 / Error=7
        """
        self.ch.set(CH_KEY_STATE, float(key_state))
        self.ch.set(CH_IGN, 1.0 if ign_valid else 0.0)
