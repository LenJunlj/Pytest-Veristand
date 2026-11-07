# -*- coding: utf-8 -*-
r"""P2546 左后大屏加热 —— NTC 故障批次（前提 2 + 退出 2 + 故障恢复 1）

依据：reports/P2546_左后大屏加热_dump.json + 历史报告实测值。

通道分工（照抄存量，勿统一）：
- 前提/退出条件-NTC短电源、NTC开路 → **CH7**
- 故障恢复测试-NTC短地、NTC开路 → **CH9**

注入值：短地=14 / 短电源=12 / 开路=8；取消=0。
判定语义同全项目：EQ（实测 == Limits.Low）。
- 前提：注入后请求三档 → 被抑制（hard==0, CAN==1）
- 退出：加热中注入 → 输出停止（hard==0, CAN==1）
- 故障恢复：注入→3s→取消→按压加热开关→输出恢复三档（hard==1, CAN==4）

原文前提类在 Main 末步还会清一次 CH7；翻译在断言后同样清除，避免状态泄漏。
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

FAULTS = [("short_vcc", "短电源"), ("open", "开路")]


@allure.epic(EPIC)
@allure.feature(FEATURE)
@allure.story("NTC故障-前提条件")
@allure.title("前提条件测试-NTC{fault}：抑制加热（CH7）")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.parametrize("kind,fault", FAULTS, ids=[f[0] for f in FAULTS])
def test_ntc_fault_blocks_heating(bench, kind, fault):
    """前提条件测试-NTCX：初始化→注入(CH7)→1s→请求三档→3s→采集→判定被抑制→清除"""
    with allure.step(f"注入 NTC {fault}（FIU3_CH7）并等待 1s"):
        bench.inject_ntc_fault(kind, ch="ch7")
        time.sleep(1)
    with allure.step("请求三档加热（库序列含 2s）"):
        bench.request_heat("level3")
    with allure.step("等待 3s 后采集输出"):
        time.sleep(3)
        out = bench.read_heat_outputs()
        time.sleep(1)
    with allure.step("判定输出被抑制（hard==0, CAN==1）"):
        assert_outputs(out, *SUPPRESSED)
    with allure.step("清除 NTC 故障（原文 Main 末步）"):
        bench.clear_ntc_fault(ch="ch7")


@allure.epic(EPIC)
@allure.feature(FEATURE)
@allure.story("NTC故障-退出条件")
@allure.title("退出条件测试-NTC{fault}：加热中注入输出停止（CH7）")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.parametrize("kind,fault", FAULTS, ids=[f[0] for f in FAULTS])
def test_ntc_fault_exit(bench, kind, fault):
    """退出条件测试-NTCX：请求三档→1s→采集(加热中)→注入(CH7)→3s→采集→判定停止→清除"""
    with allure.step("请求三档并确认加热中"):
        bench.request_heat("level3")                      # 库序列内部 2s
        time.sleep(1)
        out1 = bench.read_heat_outputs()
        time.sleep(1)
        assert_outputs(out1, *HEATING_ON)

    with allure.step(f"注入 NTC {fault}（FIU3_CH7）并等待 3s"):
        time.sleep(1)
        bench.inject_ntc_fault(kind, ch="ch7")
        time.sleep(3)
        out2 = bench.read_heat_outputs()
        time.sleep(1)
    with allure.step("判定输出停止（hard==0, CAN==1）"):
        assert_outputs(out2, *SUPPRESSED)
    with allure.step("清除 NTC 故障（原文 Main 末步）"):
        bench.clear_ntc_fault(ch="ch7")


@allure.epic(EPIC)
@allure.feature(FEATURE)
@allure.story("故障恢复")
@allure.title("故障恢复测试-NTC开路")
@allure.severity(allure.severity_level.NORMAL)
def test_fault_recovery_ntc_open(bench):
    """故障恢复测试-NTC开路故障：三档→注入(CH9,8)→3s→取消→1s→开关重触发→判定恢复"""
    with allure.step("请求三档加热"):
        bench.request_heat("level3")                      # 库序列内部 2s
        time.sleep(1)
    with allure.step("注入 NTC 开路故障（FIU3_CH9=8）"):
        bench.inject_ntc_fault("open", ch="ch9")
        time.sleep(3)
    with allure.step("取消故障注入并按压加热开关"):
        bench.clear_ntc_fault(ch="ch9")
        time.sleep(1)                                     # 原文"取消NTC开路"后 Wait1s
        bench.heat_switch(pressed=True)
        time.sleep(1)
    with allure.step("采集并判定恢复后三档正常（hard==1, CAN==4）"):
        out = bench.read_heat_outputs()
        time.sleep(1)
        assert_outputs(out, *HEATING_ON)
