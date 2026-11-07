# -*- coding: utf-8 -*-
r"""P2546 左后大屏加热 —— TestStand 存量序列的 pytest 翻译（首版草稿）

生成依据：reports/P2546_左后大屏加热_dump.json（53 序列结构化 dump），
通道/数值/时序/限值 100% 照抄存量，非人肉对照编辑器翻译。
首版覆盖 10 条存量序列：触发条件(4) + 控温逻辑(3) + 欠压前提/退出(2) + NTC短地故障恢复(1)。

与原序列的已知差异 / 待确认清单（2026-11-06 评审已逐条闭环）
依据三源交叉验证：重建的结构化 dump（tools/seq_dump.py）+ TestStand 历史报告实测值
（本目录 samples/...Report[10 59 21][2026 11 3].html）+ interop 全文件 RunMode 统计。

1. LED 三项判定：原文 174/174（58 序列 × 3）全为 Skip，且采集序列只写 HeatOutHard/HeatOutCAN，
   FileGlobals.LEDHeat* 声明后从未被写 → 不翻译，维持。
2. 限值表达式引用 FileGlobals.VOLT：file_globals 仅 5 个变量，无 VOLT（未定义，存量缺陷）→ 不翻译。
3. 控温逻辑三档 CAN 下限均 4（复制自三档未改，存量缺陷）；且该三条序列在原文 MainSequence 中整条 Skip
   → 用户拍板：删除本翻译中的控温逻辑用例（缺陷证据保留于本注释与 git 历史）。
4. 触发-OFF 第二组"CAN∈[1,11]"实为"CAN == 1"：原文判定语义是 EQ（等于 Low），并非区间；
   OFF 时 CAN 编码 = 1（0=无请求 / 1=OFF / 2~4=一~三档）。
5. 触发-OFF 的等待：原文"加热OFF"序列 = 写 OFF=1(等1s) → 写无请求(等1s)，再 + 外层 1s，
   即撤请求后到采集共 2s → 已按原文补齐（此前误用 3s）。
   另注：该序列首步名为"加热一档请求"但实际写 1（OFF），是复制库序列改了值忘改名。
6. NTC 故障通道：CH7 用于"前提/退出条件-NTC短地/短电源/开路"，CH9 用于"故障恢复-NTC短地/开路"。
   本翻译只覆盖故障恢复 → CH9 正确，与 CH7 无冲突。
7. bench_shutdown 比原文多"撤加热请求"（安全增量）；原文结束只清 CH9/CH1、初始化只清 CH7/CH1
   （清理不对称，本翻译统一全清）。
8. 【已确认存量缺陷 2026-11-06】硬线输出采集通道存量误写 port0\DI1（恒 0），
   实测真实通道为 port0\DI0（随加热请求 0→1 响应），stimulus.CH_HEAT_OUT_HARD 已修正。
9. 【本轮新发现 2026-11-06】判定语义为 EQ（实测 == Low，High=11 是模板残留、不参与判定）。
   此前按区间 [Low, High] 翻译会掩盖档位错误（如 level1 时回 4 也能过）→ 已改为精确等值。
10.【本轮新发现】加热请求编码 0 = 无请求（DUT 保持原状态），不是 OFF；OFF 必须写 1。
   依据：库序列"加热X档请求"写 4→0 后实测 CAN 仍为 4。stimulus.HEAT_REQ 已修正。
11.【本轮新发现】库序列"加热X档请求"自带 2s 内部等待（写档位→1s→无请求→1s），是原文时序的一部分。
   漏掉会让时序类判定提前采样：实测 8.5V 欠压下 DUT 在请求后 3~6s 之间才切断输出，原文按 6s 采样
   （1s 初始化 + 2s 库序列 + 3s 外层），此前翻译只等 4s 导致误判 P1。已封装为 Stimulus.request_heat。
"""
import time

import allure
import pytest

from projects.p2546.common.checks import assert_outputs

pytestmark = pytest.mark.hil

# Allure 报告语义（epic → feature → story 三级结构）
EPIC = "P2546 HIL 测试"
FEATURE = "左后大屏加热"

# (heat_out_hard 期望值, heat_out_can 期望值) —— 原文判定为 EQ（实测 == Limits.Low）
TRIGGER_SPECS = {
    "level3": (1.0, 4.0),
    "level2": (1.0, 3.0),
    "level1": (1.0, 2.0),
}


# bench fixture 见 projects/p2546/left_heating/conftest.py；assert_outputs 见 common/checks.py


# ================= 触发条件测试（存量 4 条 → 1 个参数化 + 1 条 OFF） =================

@allure.epic(EPIC)
@allure.feature(FEATURE)
@allure.story("触发条件")
@allure.title("触发条件测试-{level}")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.parametrize("level", ["level1", "level2", "level3"])
def test_trigger_level(bench, level):
    """触发条件测试-加热X档：初始化→档位请求→3s→采集→1s→判定"""
    with allure.step(f"设置加热请求 {level}（库序列：写档位→1s→无请求→1s）"):
        bench.request_heat(level)
    with allure.step("等待 3s 后采集硬线/CAN 输出（原文时序）"):
        time.sleep(3)
        out = bench.read_heat_outputs()
        time.sleep(1)
    with allure.step("判定输出（精确等值）"):
        assert_outputs(out, *TRIGGER_SPECS[level])


@allure.epic(EPIC)
@allure.feature(FEATURE)
@allure.story("触发条件")
@allure.title("触发条件测试-加热OFF")
@allure.severity(allure.severity_level.NORMAL)
def test_trigger_off(bench):
    """触发条件测试-加热OFF：先验证三档加热中，再按原文 OFF 链（写 OFF=1 → 无请求）
    验证输出停止。判定语义 EQ：停止后 hard==0、CAN==1（OFF 编码）。"""
    with allure.step("设置三档请求并确认加热中"):
        bench.request_heat("level3")
        time.sleep(3)
        out1 = bench.read_heat_outputs()
        time.sleep(1)
        assert_outputs(out1, *TRIGGER_SPECS["level3"])   # 原文第一组：三档状态

    with allure.step("按原文执行 OFF 链：写 OFF=1 → 1s → 无请求 → 1s"):
        time.sleep(1)                                     # 原文判定后 Wait 1s
        # 原文"加热OFF"序列首步名为"加热一档请求"，实际写的是 1（OFF）——复制库序列改了值忘改名
        bench.set_heat_request("off")
        time.sleep(1)                                     # 库序列"加热OFF"内部 Wait
        bench.no_heat_request()
        time.sleep(1)                                     # 库序列"加热OFF"内部 Wait
        time.sleep(1)                                     # 外层 Wait1s（原文）→ 撤请求后共 2s
        out2 = bench.read_heat_outputs()
        time.sleep(1)
    with allure.step("判定 OFF 后输出停止（hard==0, CAN==1）"):
        assert_outputs(out2, 0.0, 1.0)                    # 原文第二组：OFF 后


# ================= 加热控温逻辑测试（存量 3 条）—— 本轮按用户拍板删除 =================
# 删除理由（2026-11-06 评审）：该 3 条序列在原文 MainSequence 中整条 Skip（从未执行），
# 且其 CAN 下限三档均为 4（照抄三档未改，存量缺陷）。保留证据：上一版翻译在此跑出
# 2 failed（DUT 一/二档回报 2/3，期望 4），属新发现而非回归；如日后恢复，需先由用户澄清限值语义。


# ================= 前提/退出条件：欠压（存量 2 条） =================

@allure.epic(EPIC)
@allure.feature(FEATURE)
@allure.story("欠压保护")
@allure.title("前提条件测试_欠压：8.5V 抑制加热")
@allure.severity(allure.severity_level.CRITICAL)
def test_undervoltage_inhibits_heating(bench):
    """前提条件测试_欠压：8.5V 下请求三档 → 输出应被抑制（原文 EQ：hard==0, CAN==1）"""
    with allure.step("降电源电压至 8.5V（欠压工况）"):
        bench.set_supply_voltage(8.5)
        time.sleep(1)
    with allure.step("在欠压下调三档加热请求"):
        bench.request_heat("level3")
        time.sleep(3)
        out = bench.read_heat_outputs()
        time.sleep(1)
    with allure.step("判定输出被抑制（hard==0, CAN==1）"):
        assert_outputs(out, 0.0, 1.0)


@allure.epic(EPIC)
@allure.feature(FEATURE)
@allure.story("欠压保护")
@allure.title("退出条件测试_欠压：加热中降 8.5V 输出停止")
@allure.severity(allure.severity_level.CRITICAL)
def test_undervoltage_exit(bench):
    """退出条件测试_欠压：正常电压加热中 → 降 8.5V → 5s → 输出停止"""
    with allure.step("正常电压下请求三档并确认加热中"):
        bench.request_heat("level3")                      # 库序列内部 2s
        time.sleep(1)
        out1 = bench.read_heat_outputs()
        time.sleep(1)
        assert_outputs(out1, *TRIGGER_SPECS["level3"])   # 第一组：正常加热中（hard==1, CAN==4）

    with allure.step("降电压至 8.5V 并等待 5s"):
        time.sleep(1)
        bench.set_supply_voltage(8.5)
        time.sleep(5)
        out2 = bench.read_heat_outputs()
        time.sleep(1)
    with allure.step("判定欠压后输出停止（hard==0, CAN==1）"):
        assert_outputs(out2, 0.0, 1.0)                   # 第二组：欠压后


# ================= 故障恢复：NTC 短地（存量 1 条，其余 5 条故障场景后续铺开） =================

@allure.epic(EPIC)
@allure.feature(FEATURE)
@allure.story("故障恢复")
@allure.title("故障恢复测试-NTC短地")
@allure.severity(allure.severity_level.NORMAL)
def test_fault_recovery_ntc_short_to_gnd(bench):
    """故障恢复测试-NTC短地故障：三档→注入→3s→取消→2s→开关重触发→判定恢复正常"""
    with allure.step("请求三档加热"):
        bench.request_heat("level3")                      # 库序列内部 2s
        time.sleep(1)
    with allure.step("加热开启"):
        out = bench.read_heat_outputs()
        time.sleep(1)
        assert_outputs(out, *TRIGGER_SPECS["level3"])
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
        assert_outputs(out, *TRIGGER_SPECS["level3"])    # 恢复后三档正常（hard==1, CAN==4）
