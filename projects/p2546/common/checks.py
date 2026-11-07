# -*- coding: utf-8 -*-
"""left_heating 断言工具：把存量 TestStand 的 Numeric Limit 判定翻成 pytest 断言。"""
import allure


def assert_outputs(out: dict, hard_expect, can_expect):
    """两项有效判定的翻译（硬线输出 + CAN 输出）。
    原文 Comparison Type = EQ（== Limits.Low），即期望精确等值，不是区间。
    实测值挂到 Allure 报告的当前步骤下，失败时可直接看到现场数据。"""
    allure.attach(
        "硬线输出(hard) = {hard} 期望 {h}\nCAN 输出(can)  = {can} 期望 {c}\n判定语义: 精确等值 (EQ)".format(
            hard=out["hard"], can=out["can"], h=hard_expect, c=can_expect),
        name="实测输出与期望值",
        attachment_type=allure.attachment_type.TEXT)
    assert out["hard"] == hard_expect, \
        f"硬线输出 {out['hard']} != 期望 {hard_expect}"
    assert out["can"] == can_expect, \
        f"CAN 输出 {out['can']} != 期望 {can_expect}"
