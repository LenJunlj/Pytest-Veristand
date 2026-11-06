# -*- coding: utf-8 -*-
"""P1 验收用例：连接、读写、function 级状态隔离。仅台架机上跑（pytest -m hil）。

别名统一改成你冒烟时读到的那个真实通道（bench.yaml 的 reset_channels 也要同步）。
"""
import pytest

pytestmark = pytest.mark.hil


def test_gateway_alive_and_channel_readable(channel):
    """验收①：会话级连接成立，能读到一个真实通道。"""
    val = channel.get("DesiredRPM")
    assert isinstance(val, float)
    assert val == val        # 非 NaN


def test_state_isolated_a(channel):
    """验收②（上半）：写入非安全值；本条结束后应被 function 级 fixture 复位。"""
    channel.set("DesiredRPM", 1234.0)
    assert abs(channel.get("DesiredRPM") - 1234.0) < 1e-6


def test_state_isolated_b(channel, bench_config):
    """验收②（下半）：a 写入的 1234 已被复位，起始值必须等于安全值。

    必须与 _a 一起跑（同文件顺序执行）才能验证隔离——不要用 -k 单独选这条。
    """
    safe = bench_config["veristand"]["reset_channels"]["DesiredRPM"]
    assert channel.get("DesiredRPM") == pytest.approx(safe, abs=1e-6)
