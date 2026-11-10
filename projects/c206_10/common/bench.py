# -*- coding: utf-8 -*-
"""C206-10 项目级台架工况基类（跨模块共用：电源/电源模式/能量限制/OTA/报文使能）

翻译自三个 .seq 共有的本地序列「本地加热前提条件」/「测试用例结束」：
    Main 步骤逐条对应（SET 值、WAIT 时长），Setup/Cleanup 结构一致。
模块特有激励（座椅加热请求、NTC/输出故障、开关、采集）在模块 stimulus.py 继承扩展。
"""
import time

from bench_io import channels as bio
from projects.c206_10.common.channels import (
    CH_ENERGY_LIMIT, CH_ENERGY_LIMIT_MANU, CH_EN_BCM1_11, CH_EN_BCM1_2, CH_EN_EEM,
    CH_OTA_MODE, CH_POWER_MODE, CH_VDC_POWER_MODE, bench,
)

CH_PWR_VOLT = bench(bio.PWR_VOLT)
CH_PWR_CURR = bench(bio.PWR_CURR)
CH_PWR_ON = bench(bio.PWR_ON)
CH_PWR_RELAY = bench(bio.PWR_RELAY)


class BenchStimulus:
    """台架工况：电源/电源模式/整车电源模式/OTA/能量限制/报文使能。"""

    def __init__(self, channel):
        self.ch = channel

    # 翻译自"本地加热前提条件"（Main 8 步：电源 12V/20A/ON、PowerMode=4、Standby、继电器 ON、等 2s）
    def bench_ready(self):
        c = self.ch
        c.set(CH_PWR_VOLT, 12.0)
        c.set(CH_PWR_CURR, 20.0)
        c.set(CH_PWR_ON, 1.0)
        c.set(CH_POWER_MODE, 4.0)          # PowerModle=4
        c.set(CH_ENERGY_LIMIT_MANU, 0.0)   # 非电能限制（手动限制开关关）
        c.set(CH_OTA_MODE, 0.0)            # 非 OTA
        c.set(CH_VDC_POWER_MODE, 4.0)      # Standby
        c.set(CH_PWR_RELAY, 1.0)           # 电源继电器 ON
        # 原文此处调用"设置程控电源12V/20A/ON"并等 2s（上电稳定）
        time.sleep(2)

    # 翻译自"测试用例结束"（Main 8 步）
    def bench_shutdown(self):
        c = self.ch
        c.set(CH_PWR_VOLT, 12.0)
        c.set(CH_PWR_CURR, 20.0)
        c.set(CH_PWR_ON, 0.0)
        c.set(CH_PWR_RELAY, 0.0)
        c.set(CH_POWER_MODE, 0.0)
        c.set(CH_VDC_POWER_MODE, 3.0)      # Pre_Off
        c.set(CH_ENERGY_LIMIT, 0.0)
        c.set(CH_OTA_MODE, 0.0)            # 增量：原文只清 FIU，不清 OTA（防泄漏）
        c.set(CH_EN_BCM1_11, 1.0)          # 增量：报文使能恢复（DTC 系列会关）
        c.set(CH_EN_BCM1_2, 1.0)
        c.set(CH_EN_EEM, 1.0)
        time.sleep(2)

    # ---- 工况原语（各 case 直接调用，参数内联） ----
    def set_supply_voltage(self, volts: float):
        self.ch.set(CH_PWR_VOLT, float(volts))

    def set_power_mode(self, value: float):
        """PowerModle（BCM1_2_232）：原文 4=上电 / 0=下电"""
        self.ch.set(CH_POWER_MODE, float(value))

    def set_vdc_power_mode(self, value: float):
        """整车电源模式：4=Standby / 3=Pre_Off / 5=Pre_On / 6=Driving"""
        self.ch.set(CH_VDC_POWER_MODE, float(value))

    def set_ota_mode(self, on: bool):
        self.ch.set(CH_OTA_MODE, 1.0 if on else 0.0)

    def set_energy_limit(self, level: float):
        """电能限制等级：1=无限制 / 2~5 逐级限制（原文"电能限制"/"非电能限制"）"""
        self.ch.set(CH_ENERGY_LIMIT, float(level))

    def set_msg_enable(self, bcm1_11: bool = True, bcm1_2: bool = True, eem: bool = True):
        """报文使能开关：False = 停发该报文（模拟节点/报文丢失）"""
        self.ch.set(CH_EN_BCM1_11, 1.0 if bcm1_11 else 0.0)
        self.ch.set(CH_EN_BCM1_2, 1.0 if bcm1_2 else 0.0)
        self.ch.set(CH_EN_EEM, 1.0 if eem else 0.0)
