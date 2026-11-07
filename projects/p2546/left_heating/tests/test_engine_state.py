# -*- coding: utf-8 -*-
r"""P2546 左后大屏加热 —— 发动机状态批次（前提 3 + 退出 2 + 暂停 1）

依据：reports/P2546_左后大屏加热_dump.json + 历史报告
（projects/p2546/left_heating/samples/...Report[10 59 21][2026 11 3].html，实测值与期望值已核对）。

发动机状态编码（照抄存量写入值）：0=NotRunning / 1=Running / 2=Crank / 3=Fault

判定语义同全项目：EQ（实测 == Limits.Low）。
- 前提类（NoRunning/Crank/Fault）：抑制加热 → hard==0, CAN==1
- 退出类（NoRunning/Fault）：加热中置该状态 → 输出停止 → hard==0, CAN==1
- 暂停类（Crank）：加热中置 Crank → 硬线断开但 CAN 仍保持档位 → hard==0, CAN==4

存量缺陷记录：原文这些步骤名统一叫"设置发动机状态Running"，但写入值分别为 0/2/3（改名遗漏），
本翻译按写入值建参数化，不按名字。
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
PAUSED = (0.0, 4.0)          # 暂停：硬线断开，CAN 仍报三档


@allure.epic(EPIC)
@allure.feature(FEATURE)
@allure.story("发动机状态-前提条件")
@allure.title("前提条件测试_发动机状态{state}：抑制加热")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.parametrize("state", ["not_running", "crank", "fault"])
def test_engine_state_blocks_heating(bench, state):
    """前提条件测试_发动机状态X：初始化→置状态→1s→请求三档→3s→采集→判定被抑制"""
    with allure.step(f"置发动机状态 {state} 并等待 1s"):
        bench.set_engine_state(state)
        time.sleep(1)
    with allure.step("请求三档加热（库序列含 2s）"):
        bench.request_heat("level3")
    with allure.step("等待 3s 后采集输出"):
        time.sleep(3)
        out = bench.read_heat_outputs()
        time.sleep(1)
    with allure.step("判定输出被抑制（hard==0, CAN==1）"):
        assert_outputs(out, *SUPPRESSED)


@allure.epic(EPIC)
@allure.feature(FEATURE)
@allure.story("发动机状态-退出条件")
@allure.title("退出条件测试_发动机状态{state}：加热中置{state}输出停止")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.parametrize("state", ["not_running", "fault"])
def test_engine_state_exit(bench, state):
    """退出条件测试_发动机状态X：请求三档→1s→采集(加热中)→置状态→3s→采集→判定停止"""
    with allure.step("请求三档并确认加热中"):
        bench.request_heat("level3")                      # 库序列内部 2s
        time.sleep(1)
        out1 = bench.read_heat_outputs()
        time.sleep(1)
        assert_outputs(out1, *HEATING_ON)

    with allure.step(f"置发动机状态 {state} 并等待 3s"):
        time.sleep(3)
        bench.set_engine_state(state)
        time.sleep(3)
        out2 = bench.read_heat_outputs()
        time.sleep(1)
    with allure.step("判定输出停止（hard==0, CAN==1）"):
        assert_outputs(out2, *SUPPRESSED)


@allure.epic(EPIC)
@allure.feature(FEATURE)
@allure.story("发动机状态-暂停条件")
@allure.title("暂停条件测试_发动机状态Crank：硬线断开但CAN保持档位")
@allure.severity(allure.severity_level.NORMAL)
def test_engine_state_crank_pauses(bench):
    """暂停条件测试_发动机状态Crank：请求三档→1s→采集(加热中)→置Crank→3s→采集→判定暂停"""
    with allure.step("请求三档并确认加热中"):
        bench.request_heat("level3")                      # 库序列内部 2s
        time.sleep(1)
        out1 = bench.read_heat_outputs()
        time.sleep(1)
        assert_outputs(out1, *HEATING_ON)

    with allure.step("置发动机状态 Crank 并等待 3s"):
        time.sleep(3)
        bench.set_engine_state("crank")
        time.sleep(3)
        out2 = bench.read_heat_outputs()
        time.sleep(1)
    with allure.step("判定暂停（hard==0, CAN==4 保持档位）"):
        assert_outputs(out2, *PAUSED)
