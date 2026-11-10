# -*- coding: utf-8 -*-
r"""C206-10 功能 DTC —— 全部用例（来源 projects/c206_10/samples/功能DTC测试.seq）

顺序规则：函数按 dump 序号升序，执行顺序 = 存量 .seq 序列顺序；覆盖 dump 1~12。

判定语义：String Limit —— Limits.String = "True"/"False"，Comp = IgnoreCase。
checkdtc 返回 'True' 表示该 DTC 存在且状态字节 = 0x09（本次操作循环故障）。

诊断链路：PCAN-USB（PCAN_USBBUS1, 500k），请求 762 / 响应 76A；PDC 用例清码用 765。
这是 TestStand 时代的同一套硬件与报文时序（见 common/diag.py 头注）。

★ 原文缺陷（照抄并标注，不擅自修正）：
  - 03 PDC从节点丢失：两次检测期望都是 False（原文从未在故障生效后验证 True），
    等于只验证了"恢复后无 DTC"；如需补 True 检查请人工确认后加。
  - 04 车身控制单元1报文丢失：故障后只等 1s 就期望 True（其他用例都是数秒），
    若台架实测不稳定，应先核对原文时序而非改期望值。
  - 09 原文标签"主驾加热输出短地"实际写 CH1=8 + CH10=2；左后模块"加热输出开路"也写 CH1=8
    （同一值两个语义标签，值以写入为准，标签存疑）。
  - 11/12 开关卡滞按住 55s 后才可能出码，属长时用例（已标 slow）。
"""
import time

import allure
import pytest

from projects.c206_10.common.checks import assert_dtc, assert_seat

pytestmark = pytest.mark.hil


@allure.title("01·过压DTC")
def test_01_overvoltage_dtc(bench):
    """过压 DTC（90E017）：16.8V 保持 6s 尚未出码，再 5s 出码；回 12V 后恢复。"""
    time.sleep(1)                      # 原文：前提条件后 Wait 1
    bench.clear_dtc()
    time.sleep(1)
    bench.set_supply_voltage(16.8)     # 原文步骤名"设置程控电源16.6V"（名/值不符，以写入为准）
    time.sleep(6)
    assert_dtc(bench.read_dtc("90E017"), "False", "过压 6s")
    time.sleep(5)
    assert_dtc(bench.read_dtc("90E017"), "True", "过压 11s")
    time.sleep(2)
    bench.set_supply_voltage(12)
    time.sleep(3)
    assert_dtc(bench.read_dtc("90E017"), "False", "回压恢复")


@allure.title("02·欠压DTC")
def test_02_undervoltage_dtc(bench):
    """欠压 DTC（90E016）：8.3V 保持 6s 尚未出码，再 5s 出码；回 12V 后恢复。"""
    time.sleep(1)
    bench.clear_dtc()
    time.sleep(1)
    bench.set_supply_voltage(8.3)      # 原文步骤名"设置程控电源8.5V"（名/值不符，以写入为准）
    time.sleep(6)
    assert_dtc(bench.read_dtc("90E016"), "False", "欠压 6s")
    time.sleep(5)
    assert_dtc(bench.read_dtc("90E016"), "True", "欠压 11s")
    time.sleep(2)
    bench.set_supply_voltage(12)
    time.sleep(3.5)
    assert_dtc(bench.read_dtc("90E016"), "False", "回压恢复")


@allure.title("03·PDC从节点丢失")
def test_03_pdc_node_lost(bench):
    """PDC 从节点丢失（C14987）：停发 BCM1_11/BCM1_2/EEM 三报文 → 恢复。"""
    time.sleep(1)
    bench.clear_dtc("765")             # 原文此用例清码请求 ID 是 765（其余 762）
    bench.set_msg_enable(bcm1_11=False, bcm1_2=False, eem=False)
    time.sleep(1)
    assert_dtc(bench.read_dtc("C14987"), "False", "报文停发 1s")
    time.sleep(1)
    bench.set_msg_enable(True, True, True)
    time.sleep(2)
    assert_dtc(bench.read_dtc("C14987"), "False", "恢复后")
    time.sleep(1)


@allure.title("04·车身控制单元1报文丢失")
def test_04_bcm1_msg_lost(bench):
    """BCM1 报文丢失（D14087）：停发 BCM1_11 → 1s 即期望出码 → 恢复后清除。"""
    time.sleep(1)
    bench.clear_dtc()
    bench.set_msg_enable(bcm1_11=False)
    time.sleep(1)
    assert_dtc(bench.read_dtc("D14087"), "True", "报文停发 1s")
    time.sleep(1)
    bench.set_msg_enable(True, True, True)
    time.sleep(1)
    assert_dtc(bench.read_dtc("D14087"), "False", "恢复后")
    time.sleep(1)


@allure.title("05·主驾温度传感器短路到地")
def test_05_driver_temp_short_gnd(bench):
    """主驾温度传感器短路到地（90E211）：FIU3_CH7=14，1.5s 未出码、再 0.5s 出码，恢复后清除。"""
    time.sleep(1)
    bench.clear_dtc()
    bench.inject_ntc_fault("short_gnd", side="tl")
    time.sleep(1.5)
    assert_dtc(bench.read_dtc("90E211"), "False", "短地 1.5s")
    time.sleep(0.5)
    assert_dtc(bench.read_dtc("90E211"), "True", "短地 2s")
    bench.clear_ntc_fault("tl")
    time.sleep(1)
    assert_dtc(bench.read_dtc("90E211"), "False", "恢复后")


@allure.title("06·主驾温度传感器开路")
def test_06_driver_temp_open(bench):
    """主驾温度传感器开路（90E215）：FIU3_CH7=8。"""
    time.sleep(1)
    bench.clear_dtc()
    bench.inject_ntc_fault("open", side="tl")
    time.sleep(1.5)
    assert_dtc(bench.read_dtc("90E215"), "False", "开路 1.5s")
    time.sleep(0.5)
    assert_dtc(bench.read_dtc("90E215"), "True", "开路 2s")
    bench.clear_ntc_fault("tl")
    time.sleep(1)
    assert_dtc(bench.read_dtc("90E215"), "False", "恢复后")


@allure.title("07·副驾温度传感器短路到地")
def test_07_passenger_temp_short_gnd(bench):
    """副驾温度传感器短路到地（90E811）：FIU3_CH8=14。"""
    time.sleep(1)
    bench.clear_dtc()
    bench.inject_ntc_fault("short_gnd", side="tr")
    time.sleep(1.5)
    assert_dtc(bench.read_dtc("90E811"), "False", "短地 1.5s")
    time.sleep(0.5)
    assert_dtc(bench.read_dtc("90E811"), "True", "短地 2s")
    bench.clear_ntc_fault("tr")
    time.sleep(1)
    assert_dtc(bench.read_dtc("90E811"), "False", "恢复后")


@allure.title("08·副驾温度传感器开路")
def test_08_passenger_temp_open(bench):
    """副驾温度传感器开路（90E815）：FIU3_CH8=8。"""
    time.sleep(1)
    bench.clear_dtc()
    bench.inject_ntc_fault("open", side="tr")
    time.sleep(1.5)
    assert_dtc(bench.read_dtc("90E815"), "False", "开路 1.5s")
    time.sleep(0.5)
    assert_dtc(bench.read_dtc("90E815"), "True", "开路 2s")
    bench.clear_ntc_fault("tr")
    time.sleep(1)
    assert_dtc(bench.read_dtc("90E815"), "False", "恢复后")


@allure.title("09·司机座椅加热高端输出开路故障")
def test_09_driver_heat_output_open(bench):
    """司机侧加热输出故障（90E413）：注入期间加热仍工作，恢复后 DTC 清除。

    原文先请求三档并确认真实加热（硬线=1 / CAN=3），再注入输出故障；标签"短地"但写入值
    是 CH1=8 + CH10=2，与左后模块"开路"同值（标签存疑，按写入值翻译）。
    """
    time.sleep(1)
    bench.clear_dtc()
    bench.request_heat("level3")
    time.sleep(0.4)
    out = bench.capture_side("tl")
    time.sleep(1)
    assert_seat(out, hard=1, can=3)
    bench.inject_out_fault("open", side="tl")
    time.sleep(2)
    assert_dtc(bench.read_dtc("90E413"), "True", "故障注入 2s")
    time.sleep(0.5)
    bench.clear_out_fault()
    time.sleep(1)
    bench.request_heat("level3")
    time.sleep(0.4)
    out = bench.capture_side("tl")
    time.sleep(1)
    assert_seat(out, hard=1, can=3)
    assert_dtc(bench.read_dtc("90E413"), "False", "恢复后")


@allure.title("10·副驾座椅加热高端输出开路故障")
def test_10_passenger_heat_output_open(bench):
    """副驾侧加热输出故障（90E513）：CH1=2（原文标签"开路"），判 TR 状态与 DI1。"""
    time.sleep(1)
    bench.clear_dtc()
    bench.request_heat_side("level3", side="tr")
    time.sleep(0.4)
    out = bench.capture_side("tr")
    time.sleep(1)
    assert_seat(out, hard=1, can=3)
    bench.inject_out_fault("open", side="tr")
    time.sleep(2)
    assert_dtc(bench.read_dtc("90E513"), "True", "故障注入 2s")
    time.sleep(0.5)
    bench.clear_out_fault()
    time.sleep(1)
    bench.request_heat_side("level3", side="tr")
    time.sleep(0.4)
    out = bench.capture_side("tr")
    time.sleep(1)
    assert_seat(out, hard=1, can=3)
    assert_dtc(bench.read_dtc("90E513"), "False", "恢复后")


@pytest.mark.slow
@allure.title("11·左后三排开关卡滞")
def test_11_left_rear_switch_stuck(bench):
    """左后三排开关卡滞（91E007）：DO0 按住 55s 未出码、再 7s 出码，松开后清除。"""
    time.sleep(1)
    bench.clear_dtc()
    bench.press_back_switch(True, side="tl")
    time.sleep(55)
    assert_dtc(bench.read_dtc("91E007"), "False", "按住 55s")
    time.sleep(7)
    assert_dtc(bench.read_dtc("91E007"), "True", "按住 62s")
    time.sleep(1)
    bench.press_back_switch(False, side="tl")
    time.sleep(1)
    assert_dtc(bench.read_dtc("91E007"), "False", "松开后")
    time.sleep(1)


@pytest.mark.slow
@allure.title("12·右后三排开关卡滞")
def test_12_right_rear_switch_stuck(bench):
    """右后三排开关卡滞（91E107）：DO1 按住 55s 未出码、再 7s 出码。"""
    time.sleep(1)
    bench.clear_dtc()
    bench.press_back_switch(True, side="tr")
    time.sleep(55)
    assert_dtc(bench.read_dtc("91E107"), "False", "按住 55s")
    time.sleep(7)
    assert_dtc(bench.read_dtc("91E107"), "True", "按住 62s")
    time.sleep(1)
    bench.press_back_switch(False, side="tr")
    time.sleep(1)
    assert_dtc(bench.read_dtc("91E107"), "False", "松开后")
    time.sleep(1)
