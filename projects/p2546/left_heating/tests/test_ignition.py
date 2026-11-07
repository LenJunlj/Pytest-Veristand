# -*- coding: utf-8 -*-
r"""P2546 左后大屏加热 —— 点火开关挡位批次（前提 4 + 退出 3）

依据：reports/P2546_左后大屏加热_dump.json + 历史报告
（projects/p2546/left_heating/samples/...Report[10 59 21][2026 11 3].html，实测值已核对）。

电源模式编码（照抄存量写入值）：OFF=0 / ACC=1 / ON(RUN)=2 / CRANK+IG=3 / Error=7；
每条同时写硬线 IGN（仅 CRANK+IG 挡为有效=1，其余无效=0）。

判定语义同全项目：EQ（实测 == Limits.Low）。
- 前提：仅 CRANK+IG 挡允许加热（hard==1, CAN==4）；OFF/ACC/Error 均抑制（hard==0, CAN==1）
- 退出：加热中切到 OFF/ACC/Error → 输出停止（hard==0, CAN==1）

时序差异（照抄原文，勿"统一"）：
- 退出-OFF 在置挡前等待 3s，退出-ACC/Error 只等 1s
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

# (id, KeyState, IGN 有效, 期望输出)
PRECONDITIONS = [
    ("off", 0.0, False, SUPPRESSED),
    ("acc", 1.0, False, SUPPRESSED),
    ("crank_ig", 3.0, True, HEATING_ON),
    ("error", 7.0, False, SUPPRESSED),
]
# (id, KeyState, IGN 有效, 置挡前等待秒数) —— 原文 OFF 挡等 3s，ACC/Error 等 1s
EXITS = [
    ("off", 0.0, False, 3),
    ("acc", 1.0, False, 1),
    ("error", 7.0, False, 1),
]


@allure.epic(EPIC)
@allure.feature(FEATURE)
@allure.story("点火开关-前提条件")
@allure.title("前提条件测试-点火开关{case}挡")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.parametrize("case,key_state,ign_valid,expect", PRECONDITIONS,
                         ids=[p[0] for p in PRECONDITIONS])
def test_ignition_blocks_heating(bench, case, key_state, ign_valid, expect):
    """前提条件测试-点火开关X挡：初始化→置电源模式→1s→请求三档→3s→采集→判定"""
    with allure.step(f"置电源模式 {case}（KeyState={key_state:g}, IGN={'有效' if ign_valid else '无效'}）"):
        bench.set_power_mode(key_state, ign_valid)
        time.sleep(1)
    with allure.step("请求三档加热（库序列含 2s）"):
        bench.request_heat("level3")
    with allure.step("等待 3s 后采集输出"):
        time.sleep(3)
        out = bench.read_heat_outputs()
        time.sleep(1)
    with allure.step(f"判定输出（hard=={expect[0]:g}, CAN=={expect[1]:g}）"):
        assert_outputs(out, *expect)


@allure.epic(EPIC)
@allure.feature(FEATURE)
@allure.story("点火开关-退出条件")
@allure.title("退出条件测试-点火开关{case}挡")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.parametrize("case,key_state,ign_valid,pre_wait", EXITS,
                         ids=[p[0] for p in EXITS])
def test_ignition_exit(bench, case, key_state, ign_valid, pre_wait):
    """退出条件测试-点火开关X挡：请求三档→1s→采集(加热中)→置挡→3s→采集→判定停止"""
    with allure.step("请求三档并确认加热中"):
        bench.request_heat("level3")                      # 库序列内部 2s
        time.sleep(1)
        out1 = bench.read_heat_outputs()
        time.sleep(1)
        assert_outputs(out1, *HEATING_ON)

    with allure.step(f"置电源模式 {case}（置挡前等待 {pre_wait}s，照抄原文）并等待 3s"):
        time.sleep(pre_wait)
        bench.set_power_mode(key_state, ign_valid)
        time.sleep(3)
        out2 = bench.read_heat_outputs()
        time.sleep(1)
    with allure.step("判定输出停止（hard==0, CAN==1）"):
        assert_outputs(out2, *SUPPRESSED)
