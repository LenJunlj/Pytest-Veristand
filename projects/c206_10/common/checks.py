# -*- coding: utf-8 -*-
"""C206-10 断言工具：把存量 TestStand Numeric Limit / String Limit 判定翻成 pytest 断言。

判定语义（实证，与 p2546 同族）：Comparison Type = EQ，实测 == Limits.Low，High 不参与
（High 里常见 0/11 模板残值甚至 `FileGlobals.VOLT/2 +1` 这类未定义表达式）。
DTC 的 String Limit：Limits.String = "True"/"False"，Comp=IgnoreCase。
"""
import allure


def _fmt(lights):
    return "L1=%s L2=%s L3=%s R1=%s R2=%s R3=%s" % tuple(lights)


def assert_seat(out: dict, hard, can, lights=None):
    """座椅加热 8 项判定：硬线输出 / CAN 状态 / 左右 1~3 档灯。

    out = 原文"报文硬线采集"的采集结果；lights 为 6 元组（左1~3、右1~3），
    省略时只判硬线与 CAN（存量 DTC 输出开路用例只判这两项）。
    实测值挂到 Allure 报告当前步骤下，失败可直接看到现场数据。
    """
    lines = ["硬线输出(hard) = %s 期望 %s" % (out["hard"], hard),
             "CAN 输出(can)   = %s 期望 %s" % (out["can"], can)]
    if lights is not None:
        lines.append("档位灯          = %s 期望 %s" % (_fmt(out["lights"]), _fmt(lights)))
    lines.append("判定语义: 精确等值 (EQ, 期望=Limits.Low)")
    allure.attach("\n".join(lines), name="实测输出与期望值",
                  attachment_type=allure.attachment_type.TEXT)

    assert out["hard"] == hard, "硬线输出 %s != 期望 %s" % (out["hard"], hard)
    assert out["can"] == can, "CAN 输出 %s != 期望 %s" % (out["can"], can)
    if lights is not None:
        assert tuple(out["lights"]) == tuple(lights), \
            "档位灯 %s != 期望 %s" % (_fmt(out["lights"]), _fmt(lights))


def assert_dtc(actual: str, expected: str, name: str = ""):
    """DTC 判定（String Limit, IgnoreCase）：checkdtc 返回 'True'/'False'。"""
    allure.attach("DTC检测 %s：实测 %r 期望 %r（IgnoreCase）" % (name or "结果", actual, expected),
                  name="DTC 判定",
                  attachment_type=allure.attachment_type.TEXT)
    assert actual is not None and str(actual).lower() == str(expected).lower(), \
        "DTC 检测 %s 实测 %r != 期望 %r" % (name, actual, expected)
