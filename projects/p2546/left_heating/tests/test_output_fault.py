# -*- coding: utf-8 -*-
r"""P2546 左后大屏加热 —— 加热输出故障批次（前提 1 + 退出 1 + 恢复 2）

依据：reports/P2546_左后大屏加热_dump.json + 历史报告实测值。

FIU 通道：加热输出故障用 FIU1OUT_Channel1（开路=2 / 短地=1），短地时另写 Channel10=2。
判定语义同全项目：EQ（实测 == Limits.Low）。

已知与存量的差异（重要）：
- 历史报告（2026-11-03）中"前提/退出条件测试-加热输出短地"实测 Failed
  （hard=1/CAN=4 而期望 0/1），说明存量本身就未通过；本翻译照抄判定，
  结果与存量一致才算"复现"，不应为了让套件变绿而放宽。
- 原文 Skip（从未执行）：前提/退出条件测试-加热输出开路、故障恢复-输出短地/开路、
  40min 稳定性 —— 本批未翻译，待用户决定是否启用。
- 口径提醒：故障恢复-过压序列里步骤名与写入值错位（名为"设置程控电源8V"写 17V，
  名为"设置程控电源17V"写 13.5V），本翻译按写入值实现。
- 状态泄漏（已修）：原文"取消加热输出短地"只清 CH1，FIU1OUT_Channel10 一直留在 2，
  会污染后续用例；bench.yaml 的 reset_channels 已补 CH10，Stimulus 复位时一并清除。
- 观测记录：故障恢复-过压曾在 FIU1OUT_Channel10 残留=2 时通过，清干净后稳定失败（hard=0）；
  探针实测 17V→13.5V 后 20s 内不自恢复，按压加热开关即恢复三档。故本用例挂 xfail(strict)。
"""
import time

import allure
import pytest

from projects.p2546.common.checks import assert_outputs

pytestmark = pytest.mark.hil

EPIC = "P2546 HIL 测试"
FEATURE = "左后大屏加热"

HEATING_ON = (1.0, 4.0)      # 三档正常加热：hard=1, CAN=4
SUPPRESSED = (0.0, 1.0)      # 被抑制/停止：hard=0, CAN=1（OFF 编码）


@pytest.mark.xfail(strict=True,
                   reason="复现存量缺陷：2026-11-03 历史实测 hard=1/CAN=4，期望 0/1（判定与原文一致，不放宽）")
@allure.epic(EPIC)
@allure.feature(FEATURE)
@allure.story("输出故障-前提条件")
@allure.title("前提条件测试-加热输出短地：抑制加热")
@allure.severity(allure.severity_level.CRITICAL)
def test_out_short_blocks_heating(bench):
    """前提条件测试-加热输出短地：初始化→注入短地→1s→请求三档→3s→采集→判定
    注：存量历史实测为 Failed（hard=1/CAN=4），本用例用于复现该缺陷。"""
    with allure.step("注入加热输出短地（FIU1_CH10=2, CH1=1）并等待 1s"):
        bench.inject_out_fault("short_gnd")
        time.sleep(1)
    with allure.step("请求三档加热（库序列含 2s）"):
        bench.request_heat("level3")
    with allure.step("等待 3s 后采集输出"):
        time.sleep(3)
        out = bench.read_heat_outputs()
        time.sleep(1)
    with allure.step("判定输出被抑制（hard==0, CAN==1）"):
        assert_outputs(out, *SUPPRESSED)


@pytest.mark.xfail(strict=True,
                   reason="复现存量缺陷：2026-11-03 历史实测 hard=1/CAN=4，期望 0/1（判定与原文一致，不放宽）")
@allure.epic(EPIC)
@allure.feature(FEATURE)
@allure.story("输出故障-退出条件")
@allure.title("退出条件测试-加热输出短地：加热中注入输出停止")
@allure.severity(allure.severity_level.CRITICAL)
def test_out_short_exit(bench):
    """退出条件测试-加热输出短地：请求三档→1s→采集(加热中)→注入短地→5s→采集→判定
    注：存量历史第二组实测为 Failed（hard=1/CAN=4），本用例用于复现该缺陷。"""
    with allure.step("请求三档并确认加热中"):
        bench.request_heat("level3")                      # 库序列内部 2s
        time.sleep(1)
        out1 = bench.read_heat_outputs()
        time.sleep(1)
        assert_outputs(out1, *HEATING_ON)

    with allure.step("注入加热输出短地并等待 5s（原文 Wait5s）"):
        time.sleep(3)
        bench.inject_out_fault("short_gnd")
        time.sleep(5)
        out2 = bench.read_heat_outputs()
        time.sleep(1)
    with allure.step("判定输出停止（hard==0, CAN==1）"):
        assert_outputs(out2, *SUPPRESSED)


@allure.epic(EPIC)
@allure.feature(FEATURE)
@allure.story("故障恢复")
@allure.title("故障恢复测试-欠压故障")
@allure.severity(allure.severity_level.NORMAL)
def test_fault_recovery_undervoltage(bench):
    """故障恢复测试-欠压：三档→降到8V→6s→回13.5V→1s→重请求→判定恢复三档"""
    with allure.step("请求三档加热"):
        bench.request_heat("level3")                      # 库序列内部 2s
        time.sleep(1)
    with allure.step("降电源至 8V 并保持 6s（欠压故障）"):
        bench.set_supply_voltage(8.0)
        time.sleep(6)
    with allure.step("恢复 13.5V 并重新请求三档"):
        bench.set_supply_voltage(13.5)
        time.sleep(1)
        bench.request_heat("level3")                      # 库序列内部 2s
        time.sleep(1)
    with allure.step("采集并判定恢复后三档正常（hard==1, CAN==4）"):
        out = bench.read_heat_outputs()
        time.sleep(1)
        assert_outputs(out, *HEATING_ON)


@pytest.mark.xfail(strict=True,
                   reason="实测过压后不自动恢复：17V→13.5V 后 20s 仍 hard=0/CAN=1，按压加热开关才恢复；"
                          "原文该序列不按开关（历史 Passed 疑为 FIU 通道残留造成的假阳性）。"
                          "XPASS 说明恢复行为变了，需重新评审")
@allure.epic(EPIC)
@allure.feature(FEATURE)
@allure.story("故障恢复")
@allure.title("故障恢复测试-过压故障")
@allure.severity(allure.severity_level.NORMAL)
def test_fault_recovery_overvoltage(bench):
    """故障恢复测试-过压：三档→升到17V→6s→回13.5V→1s→重请求→判定恢复三档"""
    with allure.step("请求三档加热"):
        bench.request_heat("level3")                      # 库序列内部 2s
        time.sleep(1)
    with allure.step("升电源至 17V 并保持 6s（过压故障）"):
        bench.set_supply_voltage(17.0)
        time.sleep(6)
    with allure.step("恢复 13.5V 并重新请求三档"):
        bench.set_supply_voltage(13.5)
        time.sleep(1)
        bench.request_heat("level3")                      # 库序列内部 2s
        time.sleep(1)
    with allure.step("采集并判定恢复后三档正常（hard==1, CAN==4）"):
        out = bench.read_heat_outputs()
        time.sleep(1)
        assert_outputs(out, *HEATING_ON)
