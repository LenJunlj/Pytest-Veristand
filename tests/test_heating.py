# -*- coding: utf-8 -*-
"""P2546 左后大屏加热 —— TestStand 存量序列的 pytest 翻译（首版草稿）

生成依据：reports/P2546_左后大屏加热_dump.json（53 序列结构化 dump），
通道/数值/时序/限值 100% 照抄存量，非人肉对照编辑器翻译。
首版覆盖 10 条存量序列：触发条件(4) + 控温逻辑(3) + 欠压前提/退出(2) + NTC短地故障恢复(1)。

与原序列的已知差异 / 待确认清单（评审时逐条过）：
1. LED 三项判定在存量中全部为 Skip 模式（174/174）且无采集来源 → 本翻译不含 LED 断言；
2. 存量限值表达式引用 FileGlobals.VOLT，但该变量未定义（疑似遗留缺陷）→ 不翻；
3. 控温逻辑三档的 CAN 下限均为 4（疑似复制自三档触发未改）→ 本版照抄，语义待确认；
4. 触发-OFF 第二组判定 CAN∈[1,11] 照抄原文（OFF 后 CAN≥1 的物理含义待确认）；
5. 触发-OFF 的"OFF 请求后等待时长"未单独提取，按触发用例的 3s 取值，评审确认；
6. NTC 故障注入存量中同时出现 CH7/CH9 两通道，本翻译统一走 CH9；
7. bench_shutdown 比原文多一步"撤加热请求"（安全增量，原文无）；
8. 【已确认存量缺陷 2026-11-06】硬线输出采集通道存量误写 port0\DI1（恒 0），
   实测真实通道为 port0\DI0（随加热请求 0→1 响应），stimulus.CH_HEAT_OUT_HARD 已修正。
"""
import time

import allure
import pytest

from helpers.stimulus import Stimulus

pytestmark = pytest.mark.hil

# Allure 报告语义（epic → feature → story 三级结构）
EPIC = "P2546 HIL 测试"
FEATURE = "左后大屏加热"

# (heat_out_hard 区间, heat_out_can 区间) —— 照抄 dump 的 CheckLimits Low/High
TRIGGER_SPECS = {
    "level3": ((1.0, 11.0), (4.0, 11.0)),
    "level2": ((1.0, 11.0), (3.0, 11.0)),
    "level1": ((1.0, 11.0), (2.0, 11.0)),
}
# 控温逻辑: (hard 区间, can 区间, NTC 阻值 Ω)
NTC_LOGIC_SPECS = {
    "level3": ((0.0, 11.0), (4.0, 11.0), 5500.0),
    "level2": ((0.0, 11.0), (4.0, 11.0), 6500.0),
    "level1": ((0.0, 11.0), (4.0, 11.0), 7500.0),
}


@pytest.fixture
def bench(channel):
    """台架标准工况 —— 翻译自存量的 Setup(测试用例初始化) / Cleanup(测试用例结束)。"""
    stim = Stimulus(channel)
    with allure.step("台架初始化 bench_ready（电源13.5V/20A、继电器、IGN、KeyState、发动机状态、清FIU）"):
        stim.bench_ready()
    time.sleep(1)                # 原文：初始化后等待 1s
    yield stim
    with allure.step("台架清理 bench_shutdown（撤加热请求、清FIU、断继电器/IGN）"):
        stim.bench_shutdown()


def assert_outputs(out: dict, hard_rng, can_rng):
    """两项有效判定的翻译（硬线输出 + CAN 输出，CheckLimits 区间语义）。
    实测值挂到 Allure 报告的当前步骤下，失败时可直接看到现场数据。"""
    allure.attach(
        "硬线输出(hard) = {hard}\nCAN 输出(can)  = {can}\n判定区间: hard∈{h}, can∈{c}".format(
            hard=out["hard"], can=out["can"], h=hard_rng, c=can_rng),
        name="实测输出与判定区间",
        attachment_type=allure.attachment_type.TEXT)
    assert hard_rng[0] <= out["hard"] <= hard_rng[1], \
        f"硬线输出 {out['hard']} 不在区间 {hard_rng}"
    assert can_rng[0] <= out["can"] <= can_rng[1], \
        f"CAN 输出 {out['can']} 不在区间 {can_rng}"


# ================= 触发条件测试（存量 4 条 → 1 个参数化 + 1 条 OFF） =================

@allure.epic(EPIC)
@allure.feature(FEATURE)
@allure.story("触发条件")
@allure.title("触发条件测试-{level}")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.parametrize("level", ["level1", "level2", "level3"])
def test_trigger_level(bench, level):
    """触发条件测试-加热X档：初始化→档位请求→3s→采集→1s→判定"""
    with allure.step(f"设置加热请求 {level}"):
        bench.set_heat_request(level)
    with allure.step("等待 3s 后采集硬线/CAN 输出（原文时序）"):
        time.sleep(3)
        out = bench.read_heat_outputs()
        time.sleep(1)
    with allure.step("判定输出区间"):
        assert_outputs(out, *TRIGGER_SPECS[level])


@allure.epic(EPIC)
@allure.feature(FEATURE)
@allure.story("触发条件")
@allure.title("触发条件测试-加热OFF")
@allure.severity(allure.severity_level.NORMAL)
def test_trigger_off(bench):
    """触发条件测试-加热OFF：先验证三档加热中，再请求 OFF 验证输出停止"""
    with allure.step("设置三档请求并确认加热中"):
        bench.set_heat_request("level3")
        time.sleep(3)
        out1 = bench.read_heat_outputs()
        time.sleep(1)
        assert_outputs(out1, (1.0, 11.0), (4.0, 11.0))   # 原文第一组：三档状态

    with allure.step("请求 OFF 并确认输出停止"):
        bench.set_heat_request("off")
        time.sleep(3)                                     # 待确认项 5
        out2 = bench.read_heat_outputs()
        time.sleep(1)
        assert_outputs(out2, (0.0, 11.0), (1.0, 11.0))   # 原文第二组：OFF 后


# ================= 加热控温逻辑测试（存量 3 条 → 1 个参数化） =================

@allure.epic(EPIC)
@allure.feature(FEATURE)
@allure.story("控温逻辑")
@allure.title("控温逻辑测试-{level}")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.parametrize("level", ["level1", "level2", "level3"])
def test_ntc_control_logic(bench, level):
    """加热控温逻辑测试-加热X档：档位→1s→NTC 阻值→3s→采集→1s→判定"""
    hard_rng, can_rng, ntc_ohms = NTC_LOGIC_SPECS[level]
    with allure.step(f"设置加热请求 {level}"):
        bench.set_heat_request(level)
        time.sleep(1)
    with allure.step(f"设置 NTC 阻值 {ntc_ohms}Ω（电阻仿真板）"):
        bench.set_ntc_resistance(ntc_ohms)
    with allure.step("等待 3s 后采集输出"):
        time.sleep(3)
        out = bench.read_heat_outputs()
        time.sleep(1)
    with allure.step("判定输出区间"):
        assert_outputs(out, hard_rng, can_rng)            # CAN 下限待确认项 3


# ================= 前提/退出条件：欠压（存量 2 条） =================

@allure.epic(EPIC)
@allure.feature(FEATURE)
@allure.story("欠压保护")
@allure.title("前提条件测试_欠压：8.5V 抑制加热")
@allure.severity(allure.severity_level.CRITICAL)
def test_undervoltage_inhibits_heating(bench):
    """前提条件测试_欠压：8.5V 下请求三档 → 输出应被抑制（下限放宽）"""
    with allure.step("降电源电压至 8.5V（欠压工况）"):
        bench.set_supply_voltage(8.5)
        time.sleep(1)
    with allure.step("在欠压下调三档加热请求"):
        bench.set_heat_request("level3")
        time.sleep(3)
        out = bench.read_heat_outputs()
        time.sleep(1)
    with allure.step("判定输出被抑制"):
        assert_outputs(out, (0.0, 11.0), (1.0, 11.0))


@allure.epic(EPIC)
@allure.feature(FEATURE)
@allure.story("欠压保护")
@allure.title("退出条件测试_欠压：加热中降 8.5V 输出停止")
@allure.severity(allure.severity_level.CRITICAL)
def test_undervoltage_exit(bench):
    """退出条件测试_欠压：正常电压加热中 → 降 8.5V → 5s → 输出停止"""
    with allure.step("正常电压下请求三档并确认加热中"):
        bench.set_heat_request("level3")
        time.sleep(1)
        out1 = bench.read_heat_outputs()
        time.sleep(1)
        assert_outputs(out1, (1.0, 11.0), (4.0, 11.0))   # 第一组：正常加热中

    with allure.step("降电压至 8.5V 并等待 5s"):
        time.sleep(1)
        bench.set_supply_voltage(8.5)
        time.sleep(5)
        out2 = bench.read_heat_outputs()
        time.sleep(1)
    with allure.step("判定欠压后输出停止"):
        assert_outputs(out2, (0.0, 11.0), (1.0, 11.0))   # 第二组：欠压后


# ================= 故障恢复：NTC 短地（存量 1 条，其余 5 条故障场景后续铺开） =================

@allure.epic(EPIC)
@allure.feature(FEATURE)
@allure.story("故障恢复")
@allure.title("故障恢复测试-NTC短地")
@allure.severity(allure.severity_level.NORMAL)
def test_fault_recovery_ntc_short_to_gnd(bench):
    """故障恢复测试-NTC短地故障：三档→注入→3s→取消→2s→开关重触发→判定恢复正常"""
    with allure.step("请求三档加热"):
        bench.set_heat_request("level3")
        time.sleep(1)
    with allure.step("注入 NTC 短地故障（FIU3_CH9=14）"):
        bench.inject_ntc_fault("short_gnd")
        time.sleep(3)
    with allure.step("取消故障注入并按压加热开关"):
        bench.clear_ntc_fault()
        time.sleep(2)
        bench.heat_switch(pressed=True)
        time.sleep(1)
    with allure.step("采集并判定恢复后三档正常"):
        out = bench.read_heat_outputs()
        time.sleep(1)
        assert_outputs(out, (1.0, 11.0), (4.0, 11.0))    # 恢复后三档正常
