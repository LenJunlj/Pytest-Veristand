# -*- coding: utf-8 -*-
r"""C206-10 右后三排加热 —— 全部用例（来源 projects/c206_10/samples/右后三排加热测试用例.seq）

顺序规则：函数按 dump 序号升序，执行顺序 = 存量 .seq 序列顺序；本文件覆盖 dump 1~28，
**缺号 = 已删除/未翻译**（09「加热上下电不记忆挡位」按用户拍板 2026-11-09 删除：
台架实测 DUT 上电后自动恢复加热（记忆挡位），与原文"不记忆"期望冲突）。

与左后模块的差异（照抄原文，勿统一）：请求信号 BCM_TRseatHeatLevelSet、DUT 状态
SeatheatInd_TR、硬线输出 DI1、NTC 注入 CH8、后三排开关 DO1、加热输出开路值 CH1=2。

判定语义：Numeric Limit 一律 EQ（实测 == Limits.Low，High 为模板残值不参与）。
档位灯（台架实测）：右1/2/3 = DI5/DI6/DI7，左1/2/3 = DI8/DI9/DI10；
本模块判右灯亮、左灯灭（左灯 0 也一并判）。
"""
import time

import allure
import pytest

from projects.c206_10.common.checks import assert_seat
from projects.c206_10.right_rear_heating.channels import CH_FIU1_CH1, CH_FIU3_NTC, CH_RES1

pytestmark = pytest.mark.hil


@allure.title("01·本地使能条件测试_16.5V")
def test_01_enable_16v5(bench):
    """本地使能条件测试_16.5V（dump 序号 1）：原文 Setup/Main/Cleanup 逐步翻译。"""
    # 原文 Setup/Cleanup：本地加热前提条件（fixture 已覆盖）
    bench.set_supply_voltage(16.7)   # 原文：设置程控电源16.5V   # ⚠ 步骤名与写入值不符（名 16.5V / 写 16.7V，以写入为准）
    time.sleep(10)
    bench.request_heat('level3')   # 原文：本地打开加热三档（写档位→0.4s→写0）
    time.sleep(2)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=0, can=0, lights=(0, 0, 0, 0, 0, 0))
    time.sleep(1)
    bench.set_supply_voltage(15.5)   # 原文：设置程控电源15.5V
    time.sleep(2)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=0, can=0, lights=(0, 0, 0, 0, 0, 0))
    # 原文 Setup/Cleanup：测试用例结束（fixture 已覆盖）


@allure.title("02·本地使能条件测试_8.5V")
def test_02_enable_8v5(bench):
    """本地使能条件测试_8.5V（dump 序号 2）：原文 Setup/Main/Cleanup 逐步翻译。"""
    # 原文 Setup/Cleanup：本地加热前提条件（fixture 已覆盖）
    bench.set_supply_voltage(8.3)   # 原文：设置程控电源8.5V   # ⚠ 步骤名与写入值不符（名 8.5V / 写 8.3V，以写入为准）
    time.sleep(11)
    bench.request_heat('level3')   # 原文：本地打开加热三档（写档位→0.4s→写0）
    time.sleep(2)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=0, can=0, lights=(0, 0, 0, 0, 0, 0))
    time.sleep(2)
    bench.set_supply_voltage(10)   # 原文：设置程控电源9.5V   # ⚠ 步骤名与写入值不符（名 9.5V / 写 9.6V，以写入为准）
    time.sleep(2)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(2)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=0, can=0, lights=(0, 0, 0, 0, 0, 0))
    bench.request_heat('level3')   # 原文：本地打开加热三档（写档位→0.4s→写0）
    time.sleep(2)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=1, can=3, lights=(0, 0, 0, 1, 1, 1))
    # 原文 Setup/Cleanup：测试用例结束（fixture 已覆盖）


@allure.title("03·本地使能条件测试_电压9.5V")
def test_03_enable_9v5(bench):
    """本地使能条件测试_电压9.5V（dump 序号 3）：原文 Setup/Main/Cleanup 逐步翻译。"""
    # 原文 Setup/Cleanup：本地加热前提条件（fixture 已覆盖）
    bench.set_supply_voltage(9.5)   # 原文：设置程控电源9.5V
    time.sleep(2)
    bench.request_heat('level3')   # 原文：本地打开加热三档（写档位→0.4s→写0）
    time.sleep(2)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=1, can=3, lights=(0, 0, 0, 1, 1, 1))
    time.sleep(10)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=1, can=3, lights=(0, 0, 0, 1, 1, 1))
    # 原文 Setup/Cleanup：测试用例结束（fixture 已覆盖）


@allure.title("04·本地使能条件测试_电压14V")
def test_04_enable_14v(bench):
    """本地使能条件测试_电压14V（dump 序号 4）：原文 Setup/Main/Cleanup 逐步翻译。"""
    # 原文 Setup/Cleanup：本地加热前提条件（fixture 已覆盖）
    bench.set_supply_voltage(14)   # 原文：设置程控电源14V
    time.sleep(2)
    bench.request_heat('level3')   # 原文：本地打开加热三档（写档位→0.4s→写0）
    time.sleep(2)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=1, can=3, lights=(0, 0, 0, 1, 1, 1))
    time.sleep(10)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=1, can=3, lights=(0, 0, 0, 1, 1, 1))
    # 原文 Setup/Cleanup：测试用例结束（fixture 已覆盖）


@allure.title("05·本地使能条件测试_电压15.5V")
def test_05_enable_15v5(bench):
    """本地使能条件测试_电压15.5V（dump 序号 5）：原文 Setup/Main/Cleanup 逐步翻译。"""
    # 原文 Setup/Cleanup：本地加热前提条件（fixture 已覆盖）
    bench.set_supply_voltage(15.5)   # 原文：设置程控电源15.5V
    time.sleep(2)
    bench.request_heat('level3')   # 原文：本地打开加热三档（写档位→0.4s→写0）
    time.sleep(2)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=1, can=3, lights=(0, 0, 0, 1, 1, 1))
    time.sleep(10)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=1, can=3, lights=(0, 0, 0, 1, 1, 1))
    # 原文 Setup/Cleanup：测试用例结束（fixture 已覆盖）


@allure.title("06·本地触发条件测试_加热三档命令")
def test_06_trigger_level3(bench):
    """本地触发条件测试_加热三档命令（dump 序号 6）：原文 Setup/Main/Cleanup 逐步翻译。"""
    # 原文 Setup/Cleanup：本地加热前提条件（fixture 已覆盖）
    bench.set_supply_voltage(14)   # 原文：设置程控电源14V
    time.sleep(2)
    bench.request_heat('level3')   # 原文：本地打开加热三档（写档位→0.4s→写0）
    time.sleep(2)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=1, can=3, lights=(0, 0, 0, 1, 1, 1))
    time.sleep(10)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=1, can=3, lights=(0, 0, 0, 1, 1, 1))
    # 原文 Setup/Cleanup：测试用例结束（fixture 已覆盖）


@allure.title("07·本地触发条件测试_加热二档命令")
def test_07_trigger_level2(bench):
    """本地触发条件测试_加热二档命令（dump 序号 7）：原文 Setup/Main/Cleanup 逐步翻译。"""
    # 原文 Setup/Cleanup：本地加热前提条件（fixture 已覆盖）
    bench.set_supply_voltage(14)   # 原文：设置程控电源14V
    time.sleep(2)
    bench.request_heat('level2')   # 原文：本地打开加热二档（写档位→0.4s→写0）
    time.sleep(2)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=1, can=2, lights=(0, 0, 0, 1, 1, 0))
    time.sleep(10)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=1, can=2, lights=(0, 0, 0, 1, 1, 0))
    # 原文 Setup/Cleanup：测试用例结束（fixture 已覆盖）


@allure.title("08·本地触发条件测试_加热一档命令")
def test_08_trigger_level1(bench):
    """本地触发条件测试_加热一档命令（dump 序号 8）：原文 Setup/Main/Cleanup 逐步翻译。"""
    # 原文 Setup/Cleanup：本地加热前提条件（fixture 已覆盖）
    bench.set_supply_voltage(14)   # 原文：设置程控电源14V
    time.sleep(2)
    bench.request_heat('level1')   # 原文：本地打开加热一档（写档位→0.4s→写0）
    time.sleep(2)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=1, can=1, lights=(0, 0, 0, 1, 0, 0))
    time.sleep(10)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=1, can=1, lights=(0, 0, 0, 1, 0, 0))
    # 原文 Setup/Cleanup：测试用例结束（fixture 已覆盖）


@allure.title("10·本地前提条件测试_Standby")
def test_10_precond_standby(bench):
    """本地前提条件测试_Standby（dump 序号 10）：原文 Setup/Main/Cleanup 逐步翻译。"""
    # 原文 Setup/Cleanup：本地加热前提条件（fixture 已覆盖）
    bench.set_supply_voltage(14)   # 原文：设置程控电源14V
    time.sleep(2)
    bench.request_heat('level1')   # 原文：本地打开加热一档（写档位→0.4s→写0）
    time.sleep(2)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=1, can=1, lights=(0, 0, 0, 1, 0, 0))
    time.sleep(10)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=1, can=1, lights=(0, 0, 0, 1, 0, 0))
    # 原文 Setup/Cleanup：测试用例结束（fixture 已覆盖）


@allure.title("11·本地前提条件测试_Pre_Off")
def test_11_precond_pre_off(bench):
    """本地前提条件测试_Pre_Off（dump 序号 11）：原文 Setup/Main/Cleanup 逐步翻译。"""
    # 原文 Setup/Cleanup：本地加热前提条件（fixture 已覆盖）
    bench.set_vdc_power_mode(3)   # 原文：Pre_Off
    bench.set_supply_voltage(14)   # 原文：设置程控电源14V
    time.sleep(2)
    bench.request_heat('level1')   # 原文：本地打开加热一档（写档位→0.4s→写0）
    time.sleep(2)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=0, can=0, lights=(0, 0, 0, 0, 0, 0))
    time.sleep(10)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=0, can=0, lights=(0, 0, 0, 0, 0, 0))
    # 原文 Setup/Cleanup：测试用例结束（fixture 已覆盖）


@allure.title("12·本地前提条件测试_Pre_On")
def test_12_precond_pre_on(bench):
    """本地前提条件测试_Pre_On（dump 序号 12）：原文 Setup/Main/Cleanup 逐步翻译。"""
    # 原文 Setup/Cleanup：本地加热前提条件（fixture 已覆盖）
    bench.set_vdc_power_mode(5)   # 原文：Pre_On
    bench.set_supply_voltage(14)   # 原文：设置程控电源14V
    time.sleep(2)
    bench.request_heat('level1')   # 原文：本地打开加热一档（写档位→0.4s→写0）
    time.sleep(2)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=1, can=1, lights=(0, 0, 0, 1, 0, 0))
    time.sleep(10)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=1, can=1, lights=(0, 0, 0, 1, 0, 0))
    # 原文 Setup/Cleanup：测试用例结束（fixture 已覆盖）


@allure.title("13·本地前提条件测试_Driving")
def test_13_precond_driving(bench):
    """本地前提条件测试_Driving（dump 序号 13）：原文 Setup/Main/Cleanup 逐步翻译。"""
    # 原文 Setup/Cleanup：本地加热前提条件（fixture 已覆盖）
    bench.set_vdc_power_mode(6)   # 原文：Driving
    bench.set_supply_voltage(14)   # 原文：设置程控电源14V
    time.sleep(2)
    bench.request_heat('level1')   # 原文：本地打开加热一档（写档位→0.4s→写0）
    time.sleep(2)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=1, can=1, lights=(0, 0, 0, 1, 0, 0))
    time.sleep(10)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=1, can=1, lights=(0, 0, 0, 1, 0, 0))
    # 原文 Setup/Cleanup：测试用例结束（fixture 已覆盖）


@allure.title("14·本地退出条件测试_Standby-Pre_Off")
def test_14_exit_standby_to_pre_off(bench):
    """本地退出条件测试_Standby-Pre_Off（dump 序号 14）：原文 Setup/Main/Cleanup 逐步翻译。"""
    # 原文 Setup/Cleanup：本地加热前提条件（fixture 已覆盖）
    bench.set_supply_voltage(14)   # 原文：设置程控电源14V
    time.sleep(2)
    bench.request_heat('level1')   # 原文：本地打开加热一档（写档位→0.4s→写0）
    time.sleep(2)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=1, can=1, lights=(0, 0, 0, 1, 0, 0))
    time.sleep(2)
    bench.set_vdc_power_mode(3)   # 原文：Pre_Off
    time.sleep(2)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=0, can=0, lights=(0, 0, 0, 0, 0, 0))
    # 原文 Setup/Cleanup：测试用例结束（fixture 已覆盖）


@allure.title("15·本地退出条件测试_Pre_On-Pre_Off")
def test_15_exit_pre_on_to_pre_off(bench):
    """本地退出条件测试_Pre_On-Pre_Off（dump 序号 15）：原文 Setup/Main/Cleanup 逐步翻译。"""
    # 原文 Setup/Cleanup：本地加热前提条件（fixture 已覆盖）
    bench.set_vdc_power_mode(5)   # 原文：Pre_On
    bench.set_supply_voltage(14)   # 原文：设置程控电源14V
    time.sleep(2)
    bench.request_heat('level1')   # 原文：本地打开加热一档（写档位→0.4s→写0）
    time.sleep(2)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=1, can=1, lights=(0, 0, 0, 1, 0, 0))
    time.sleep(2)
    bench.set_vdc_power_mode(3)   # 原文：Pre_Off
    time.sleep(2)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=0, can=0, lights=(0, 0, 0, 0, 0, 0))
    # 原文 Setup/Cleanup：测试用例结束（fixture 已覆盖）


@allure.title("16·本地退出条件测试_Driving-Pre_Off")
def test_16_exit_driving_to_pre_off(bench):
    """本地退出条件测试_Driving-Pre_Off（dump 序号 16）：原文 Setup/Main/Cleanup 逐步翻译。"""
    # 原文 Setup/Cleanup：本地加热前提条件（fixture 已覆盖）
    bench.set_vdc_power_mode(6)   # 原文：Driving
    bench.set_supply_voltage(14)   # 原文：设置程控电源14V
    time.sleep(2)
    bench.request_heat('level1')   # 原文：本地打开加热一档（写档位→0.4s→写0）
    time.sleep(2)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=1, can=1, lights=(0, 0, 0, 1, 0, 0))
    time.sleep(2)
    bench.set_vdc_power_mode(3)   # 原文：Pre_Off
    time.sleep(2)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=0, can=0, lights=(0, 0, 0, 0, 0, 0))
    # 原文 Setup/Cleanup：测试用例结束（fixture 已覆盖）


@allure.title("17·本地退出条件测试_电压16.5V")
def test_17_exit_16v5(bench):
    """本地退出条件测试_电压16.5V（dump 序号 17）：原文 Setup/Main/Cleanup 逐步翻译。"""
    # 原文 Setup/Cleanup：本地加热前提条件（fixture 已覆盖）
    bench.set_supply_voltage(14)   # 原文：设置程控电源14V
    time.sleep(2)
    bench.request_heat('level3')   # 原文：本地打开加热三档（写档位→0.4s→写0）
    time.sleep(2)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=1, can=3, lights=(0, 0, 0, 1, 1, 1))
    time.sleep(1)
    bench.set_supply_voltage(16.9)   # 原文：设置程控电源16.5V   # ⚠ 步骤名与写入值不符（名 16.5V / 写 16.9V，以写入为准）
    time.sleep(5)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=1, can=3, lights=(0, 0, 0, 1, 1, 1))
    time.sleep(6)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=0, can=0, lights=(0, 0, 0, 0, 0, 0))
    time.sleep(1)
    bench.set_supply_voltage(15.5)   # 原文：设置程控电源15.5V
    time.sleep(5)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=0, can=0, lights=(0, 0, 0, 0, 0, 0))
    # 原文 Setup/Cleanup：测试用例结束（fixture 已覆盖）


@allure.title("18·本地退出条件测试_电压8.5V")
def test_18_exit_8v5(bench):
    """本地退出条件测试_电压8.5V（dump 序号 18）：原文 Setup/Main/Cleanup 逐步翻译。"""
    # 原文 Setup/Cleanup：本地加热前提条件（fixture 已覆盖）
    bench.request_heat('level3')   # 原文：本地打开加热三档（写档位→0.4s→写0）
    time.sleep(2)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=1, can=3, lights=(0, 0, 0, 1, 1, 1))
    time.sleep(2)
    bench.set_supply_voltage(8.4)   # 原文：设置程控电源8.5V
    time.sleep(5)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=1, can=3, lights=(0, 0, 0, 1, 1, 1))
    time.sleep(7)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=0, can=0, lights=(0, 0, 0, 0, 0, 0))
    time.sleep(2)
    bench.set_supply_voltage(8.5)   # 原文：设置程控电源8.5V
    time.sleep(2)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=0, can=0, lights=(0, 0, 0, 0, 0, 0))
    # 原文 Setup/Cleanup：测试用例结束（fixture 已覆盖）


@allure.title("19·本地退出条件测试_OTA限制")
def test_19_exit_ota(bench):
    """本地退出条件测试_OTA限制（dump 序号 19）：原文 Setup/Main/Cleanup 逐步翻译。"""
    # 原文 Setup/Cleanup：本地加热前提条件（fixture 已覆盖）
    bench.request_heat('level3')   # 原文：本地打开加热三档（写档位→0.4s→写0）
    time.sleep(2)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=1, can=3, lights=(0, 0, 0, 1, 1, 1))
    time.sleep(2)
    bench.set_ota_mode(1)   # 原文：OTA
    time.sleep(1)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=0, can=0, lights=(0, 0, 0, 0, 0, 0))
    time.sleep(2)
    bench.set_ota_mode(0)   # 原文：非OTA
    time.sleep(2)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=0, can=0, lights=(0, 0, 0, 0, 0, 0))
    # 原文 Setup/Cleanup：测试用例结束（fixture 已覆盖）


@allure.title("20·本地退出条件测试_加热输出开路")
def test_20_exit_out_open(bench):
    """本地退出条件测试_加热输出开路（dump 序号 20）：原文 Setup/Main/Cleanup 逐步翻译。"""
    # 原文 Setup/Cleanup：本地加热前提条件（fixture 已覆盖）
    bench.request_heat('level3')   # 原文：本地打开加热三档（写档位→0.4s→写0）
    time.sleep(2)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=1, can=3, lights=(0, 0, 0, 1, 1, 1))
    time.sleep(2)
    bench.ch.set(CH_FIU1_CH1, 2)   # 原文：加热输出开路
    time.sleep(3)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=0, can=0, lights=(0, 0, 0, 0, 0, 0))
    bench.ch.set(CH_FIU1_CH1, 0)   # 原文：加热输出恢复故障
    time.sleep(1)
    bench.request_heat('level3')   # 原文：本地打开加热三档（写档位→0.4s→写0）
    time.sleep(2)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=1, can=3, lights=(0, 0, 0, 1, 1, 1))
    time.sleep(2)
    # 原文 Setup/Cleanup：测试用例结束（fixture 已覆盖）


@allure.title("21·本地退出条件测试_NTC开路")
def test_21_exit_ntc_open(bench):
    """本地退出条件测试_NTC开路（dump 序号 21）：原文 Setup/Main/Cleanup 逐步翻译。"""
    # 原文 Setup/Cleanup：本地加热前提条件（fixture 已覆盖）
    bench.request_heat('level3')   # 原文：本地打开加热三档（写档位→0.4s→写0）
    time.sleep(2)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=1, can=3, lights=(0, 0, 0, 1, 1, 1))
    time.sleep(2)
    bench.ch.set(CH_FIU3_NTC, 8)   # 原文：NTC开路
    time.sleep(3)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=0, can=0, lights=(0, 0, 0, 0, 0, 0))
    time.sleep(2)
    bench.request_heat('level3')   # 原文：本地打开加热三档（写档位→0.4s→写0）
    time.sleep(2)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=0, can=0, lights=(0, 0, 0, 0, 0, 0))
    bench.ch.set(CH_FIU3_NTC, 0)   # 原文：NTC恢复故障
    time.sleep(2)
    bench.request_heat('level3')   # 原文：本地打开加热三档（写档位→0.4s→写0）
    time.sleep(2)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=1, can=3, lights=(0, 0, 0, 1, 1, 1))
    # 原文 Setup/Cleanup：测试用例结束（fixture 已覆盖）


@allure.title("22·本地退出条件测试_NTC短路到地")
def test_22_exit_ntc_short_gnd(bench):
    """本地退出条件测试_NTC短路到地（dump 序号 22）：原文 Setup/Main/Cleanup 逐步翻译。"""
    # 原文 Setup/Cleanup：本地加热前提条件（fixture 已覆盖）
    bench.request_heat('level3')   # 原文：本地打开加热三档（写档位→0.4s→写0）
    time.sleep(2)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=1, can=3, lights=(0, 0, 0, 1, 1, 1))
    time.sleep(2)
    bench.ch.set(CH_FIU3_NTC, 14)   # 原文：NTC短路到地
    time.sleep(3)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=0, can=0, lights=(0, 0, 0, 0, 0, 0))
    bench.request_heat('level3')   # 原文：本地打开加热三档（写档位→0.4s→写0）
    time.sleep(2)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=0, can=0, lights=(0, 0, 0, 0, 0, 0))
    time.sleep(2)
    bench.ch.set(CH_FIU3_NTC, 0)   # 原文：NTC短路到地
    time.sleep(3)
    bench.request_heat('level3')   # 原文：本地打开加热三档（写档位→0.4s→写0）
    time.sleep(2)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=1, can=3, lights=(0, 0, 0, 1, 1, 1))
    time.sleep(2)
    # 原文 Setup/Cleanup：测试用例结束（fixture 已覆盖）


@allure.title("23·本地触发条件测试_能源限制")
def test_23_trigger_energy_limit(bench):
    """本地触发条件测试_能源限制（dump 序号 23）：原文 Setup/Main/Cleanup 逐步翻译。"""
    # 原文 Setup/Cleanup：本地加热前提条件（fixture 已覆盖）
    bench.set_supply_voltage(14)   # 原文：设置程控电源14V
    time.sleep(2)
    bench.request_heat('level3')   # 原文：本地打开加热三档（写档位→0.4s→写0）
    time.sleep(2)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=1, can=3, lights=(0, 0, 0, 1, 1, 1))
    time.sleep(1)
    bench.set_energy_limit(1)   # 原文：非电能限制
    time.sleep(1)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=1, can=3, lights=(0, 0, 0, 1, 1, 1))
    time.sleep(1)
    bench.set_energy_limit(2)   # 原文：非电能限制
    time.sleep(1)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=0, can=0, lights=(0, 0, 0, 0, 0, 0))
    time.sleep(1)
    bench.set_energy_limit(3)   # 原文：非电能限制
    time.sleep(1)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=0, can=0, lights=(0, 0, 0, 0, 0, 0))
    time.sleep(1)
    bench.set_energy_limit(4)   # 原文：非电能限制
    time.sleep(1)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=0, can=0, lights=(0, 0, 0, 0, 0, 0))
    time.sleep(1)
    bench.set_energy_limit(5)   # 原文：非电能限制
    time.sleep(1)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=0, can=0, lights=(0, 0, 0, 0, 0, 0))
    # 原文 Setup/Cleanup：测试用例结束（fixture 已覆盖）


@allure.title("24·本地触发条件测试_能源限制_1")
def test_24_trigger_energy_limit_1(bench):
    """本地触发条件测试_能源限制_1（dump 序号 24）：原文 Setup/Main/Cleanup 逐步翻译。"""
    # 原文 Setup/Cleanup：本地加热前提条件（fixture 已覆盖）
    bench.set_supply_voltage(14)   # 原文：设置程控电源14V
    time.sleep(2)
    bench.request_heat('level3')   # 原文：本地打开加热三档（写档位→0.4s→写0）
    time.sleep(2)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=1, can=3, lights=(0, 0, 0, 1, 1, 1))
    time.sleep(1)
    bench.set_energy_limit(1)   # 原文：电能限制
    time.sleep(1)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=1, can=3, lights=(0, 0, 0, 1, 1, 1))
    # 原文 Setup/Cleanup：测试用例结束（fixture 已覆盖）


@allure.title("25·本地触发条件测试_能源限制_2")
def test_25_trigger_energy_limit_2(bench):
    """本地触发条件测试_能源限制_2（dump 序号 25）：原文 Setup/Main/Cleanup 逐步翻译。"""
    # 原文 Setup/Cleanup：本地加热前提条件（fixture 已覆盖）
    bench.set_supply_voltage(14)   # 原文：设置程控电源14V
    time.sleep(2)
    bench.request_heat('level3')   # 原文：本地打开加热三档（写档位→0.4s→写0）
    time.sleep(2)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=1, can=3, lights=(0, 0, 0, 1, 1, 1))
    time.sleep(1)
    bench.set_energy_limit(2)   # 原文：电能限制
    time.sleep(1)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=0, can=0, lights=(0, 0, 0, 0, 0, 0))
    # 原文 Setup/Cleanup：测试用例结束（fixture 已覆盖）


@allure.title("26·本地触发条件测试_能源限制_3")
def test_26_trigger_energy_limit_3(bench):
    """本地触发条件测试_能源限制_3（dump 序号 26）：原文 Setup/Main/Cleanup 逐步翻译。"""
    # 原文 Setup/Cleanup：本地加热前提条件（fixture 已覆盖）
    bench.set_supply_voltage(14)   # 原文：设置程控电源14V
    time.sleep(2)
    bench.request_heat('level3')   # 原文：本地打开加热三档（写档位→0.4s→写0）
    time.sleep(2)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=1, can=3, lights=(0, 0, 0, 1, 1, 1))
    time.sleep(1)
    bench.set_energy_limit(3)   # 原文：电能限制
    time.sleep(1)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=0, can=0, lights=(0, 0, 0, 0, 0, 0))
    # 原文 Setup/Cleanup：测试用例结束（fixture 已覆盖）


@allure.title("27·本地触发条件测试_能源限制_4")
def test_27_trigger_energy_limit_4(bench):
    """本地触发条件测试_能源限制_4（dump 序号 27）：原文 Setup/Main/Cleanup 逐步翻译。"""
    # 原文 Setup/Cleanup：本地加热前提条件（fixture 已覆盖）
    bench.set_supply_voltage(14)   # 原文：设置程控电源14V
    time.sleep(2)
    bench.request_heat('level3')   # 原文：本地打开加热三档（写档位→0.4s→写0）
    time.sleep(2)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=1, can=3, lights=(0, 0, 0, 1, 1, 1))
    time.sleep(1)
    bench.set_energy_limit(4)   # 原文：电能限制
    time.sleep(1)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=0, can=0, lights=(0, 0, 0, 0, 0, 0))
    # 原文 Setup/Cleanup：测试用例结束（fixture 已覆盖）


@allure.title("28·本地触发条件测试_能源限制_5")
def test_28_trigger_energy_limit_5(bench):
    """本地触发条件测试_能源限制_5（dump 序号 28）：原文 Setup/Main/Cleanup 逐步翻译。"""
    # 原文 Setup/Cleanup：本地加热前提条件（fixture 已覆盖）
    bench.set_supply_voltage(14)   # 原文：设置程控电源14V
    time.sleep(2)
    bench.request_heat('level3')   # 原文：本地打开加热三档（写档位→0.4s→写0）
    time.sleep(2)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=1, can=3, lights=(0, 0, 0, 1, 1, 1))
    time.sleep(1)
    bench.set_energy_limit(5)   # 原文：电能限制
    time.sleep(1)
    out = bench.capture()   # 原文：报文硬线采集（读 1 CAN + 7 硬线）
    time.sleep(1)
    # 原文 8 项判定（EQ：实测 == Limits.Low）
    assert_seat(out, hard=0, can=0, lights=(0, 0, 0, 0, 0, 0))
    # 原文 Setup/Cleanup：测试用例结束（fixture 已覆盖）
