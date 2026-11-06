# -*- coding: utf-8 -*-
"""P1 验收用例：连接、读写、function 级状态隔离。仅台架机上跑（pytest -m hil）。

只读首枪（2026-11-06）：
- 读探针 = DI1（硬件数字量输入，存量序列同款全路径；硬件输入只读，天然安全）；
- 写入/复位验收（test_state_isolated_*）需要 reset_channels 配置真实可写激励通道
  （RES2 / HU_DrvSeatHeat / FIU 等），bench.yaml 当前刻意清空 —— 未配置时自动 skip，
  等 hil 安全确认后再启用，无需改本文件。
"""
import time

import pytest

pytestmark = pytest.mark.hil

# 读探针：台架真实通道（照抄存量序列；含 \ 的名字 ChannelHelper 直接透传，不加前缀）
READ_PROBE = r"Targets\Controller\Hardware\Chassis\DAQ\Dev1\Digital Input\port0\DI1"


def _reset_probe(bench_config):
    """取 reset_channels 第一个 (通道, 安全值) 作为隔离验证探针；未配置返回 None。"""
    resets = bench_config["veristand"].get("reset_channels") or {}
    if not resets:
        return None
    name = next(iter(resets))
    return name, float(resets[name])


def test_gateway_alive_and_channel_readable(channel):
    """验收①：会话级连接成立，能读到一个真实通道。"""
    val = channel.get(READ_PROBE)
    assert isinstance(val, float)
    assert val == val        # 非 NaN


def test_state_isolated_a(channel, bench_config):
    """验收②（上半）：写入偏离安全值的值；本条结束后应被 function 级 fixture 复位。"""
    probe = _reset_probe(bench_config)
    if probe is None:
        pytest.skip("reset_channels 为空（只读阶段）——配好真实激励通道后再验证写入")
    name, safe = probe
    channel.set(name, safe + 1.0)          # 偏离量按通道值域自行调整
    time.sleep(0.5)                        # 模型参数经模型周期异步生效（实测 <0.3s）
    assert abs(channel.get(name) - (safe + 1.0)) < 1e-6


def test_state_isolated_b(channel, bench_config):
    """验收②（下半）：a 写入的偏离值已被复位，起始值必须等于安全值。

    必须与 _a 一起跑（同文件顺序执行）才能验证隔离——不要用 -k 单独选这条。
    """
    probe = _reset_probe(bench_config)
    if probe is None:
        pytest.skip("reset_channels 为空（只读阶段）——配好真实激励通道后再验证复位")
    name, safe = probe
    assert channel.get(name) == pytest.approx(safe, abs=1e-6)
