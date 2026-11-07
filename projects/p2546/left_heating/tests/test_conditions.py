# -*- coding: utf-8 -*-
r"""P2546 左后大屏加热 —— 前提/退出条件批次（过压、整车碰撞）

生成依据：reports/P2546_左后大屏加热_dump.json（结构化 dump）
          + projects/p2546/left_heating/samples/...Report[10 59 21][2026 11 3].html（历史实测值）
通道/数值/时序/限值 100% 照抄存量，判定语义同 test_heating.py：EQ（实测 == Limits.Low）。

本批 4 条：
- 前提条件测试_过压：17V 下请求三档 → 输出应被抑制（hard==0, CAN==1）
- 退出条件测试_过压：正常加热中 → 升 17V → 5s → 输出停止
- 前提条件测试_整车碰撞：碰撞置位下请求三档 → 输出应被抑制
- 退出条件测试_整车碰撞：正常加热中 → 置碰撞 → 3s → 输出停止

时序要点（与原文逐条对齐）：
- 前提类：Setup 里先施加故障/工况（17V 或碰撞）→ Wait 1s → Main 请求档位 → Wait 3s → 采集
- 退出类：请求档位（库序列含 2s）→ Wait 1s → 采集判定"加热中" → Wait 1s → 施加工况
          → 过压 Wait 5s / 碰撞 Wait 3s → 采集 → 判定"已停止"
"""
import time

import allure
import pytest

from projects.p2546.common.checks import assert_outputs

pytestmark = pytest.mark.hil

EPIC = "P2546 HIL 测试"
FEATURE = "左后大屏加热"

# 期望值（原文 Limits.Low，EQ 语义）
HEATING_ON = (1.0, 4.0)      # 三档正常加热：hard=1, CAN=4
SUPPRESSED = (0.0, 1.0)      # 被抑制/停止：hard=0, CAN=1（OFF 编码）


@allure.epic(EPIC)
@allure.feature(FEATURE)
@allure.story("过压保护")
@allure.title("前提条件测试_过压：17V 抑制加热")
@allure.severity(allure.severity_level.CRITICAL)
def test_condition_overvoltage_blocks_heating(bench):
    """前提条件测试_过压：初始化→17V→1s→请求三档→3s→采集→判定输出被抑制"""
    with allure.step("升电源电压至 17V（过压工况）并等待 1s"):
        bench.set_supply_voltage(17.0)
        time.sleep(1)
    with allure.step("在过压下请求三档加热（库序列含 2s）"):
        bench.request_heat("level3")
    with allure.step("等待 3s 后采集输出"):
        time.sleep(3)
        out = bench.read_heat_outputs()
        time.sleep(1)
    with allure.step("判定输出被抑制（hard==0, CAN==1）"):
        assert_outputs(out, *SUPPRESSED)


@allure.epic(EPIC)
@allure.feature(FEATURE)
@allure.story("过压保护")
@allure.title("退出条件测试_过压：加热中升 17V 输出停止")
@allure.severity(allure.severity_level.CRITICAL)
def test_condition_overvoltage_exit(bench):
    """退出条件测试_过压：请求三档→1s→采集(加热中)→16V 升压→5s→采集→判定停止"""
    with allure.step("请求三档并确认加热中"):
        bench.request_heat("level3")                      # 库序列内部 2s
        time.sleep(1)
        out1 = bench.read_heat_outputs()
        time.sleep(1)
        assert_outputs(out1, *HEATING_ON)

    with allure.step("升电压至 17V 并等待 5s"):
        time.sleep(1)
        bench.set_supply_voltage(17.0)
        time.sleep(5)
        out2 = bench.read_heat_outputs()
        time.sleep(1)
    with allure.step("判定过压后输出停止（hard==0, CAN==1）"):
        assert_outputs(out2, *SUPPRESSED)


@allure.epic(EPIC)
@allure.feature(FEATURE)
@allure.story("碰撞保护")
@allure.title("前提条件测试_整车碰撞：碰撞置位抑制加热")
@allure.severity(allure.severity_level.CRITICAL)
def test_condition_crash_blocks_heating(bench):
    """前提条件测试_整车碰撞：初始化→碰撞=1→1s→请求三档→3s→采集→判定输出被抑制"""
    with allure.step("置整车碰撞信号 = 1 并等待 1s"):
        bench.set_crash(True)
        time.sleep(1)
    with allure.step("在碰撞工况下请求三档加热（库序列含 2s）"):
        bench.request_heat("level3")
    with allure.step("等待 3s 后采集输出"):
        time.sleep(3)
        out = bench.read_heat_outputs()
        time.sleep(1)
    with allure.step("判定输出被抑制（hard==0, CAN==1）"):
        assert_outputs(out, *SUPPRESSED)


@allure.epic(EPIC)
@allure.feature(FEATURE)
@allure.story("碰撞保护")
@allure.title("退出条件测试_整车碰撞：加热中置碰撞输出停止")
@allure.severity(allure.severity_level.CRITICAL)
def test_condition_crash_exit(bench):
    """退出条件测试_整车碰撞：请求三档→1s→采集(加热中)→碰撞=1→3s→采集→判定停止"""
    with allure.step("请求三档并确认加热中"):
        bench.request_heat("level3")                      # 库序列内部 2s
        time.sleep(1)
        out1 = bench.read_heat_outputs()
        time.sleep(1)
        assert_outputs(out1, *HEATING_ON)

    with allure.step("置整车碰撞信号并等待 3s"):
        time.sleep(1)
        bench.set_crash(True)
        time.sleep(3)
        out2 = bench.read_heat_outputs()
        time.sleep(1)
    with allure.step("判定碰撞后输出停止（hard==0, CAN==1）"):
        assert_outputs(out2, *SUPPRESSED)
