# -*- coding: utf-8 -*-
"""分层等值测试(不需要台架,-m "not hil" 可跑)

作用:锁定 bench_io(台架层)与项目/模块层拼装的**行为等价**——
通道字符串与旧版字面量一致(经 ChannelHelper 归一化后逐字节相同),
保证分层重构不改测试行为。规则见 docs/通道分层方案.md §9。
"""
from bench_io import channels as bch


def test_fiu_full_set():
    assert len(bch.FIU) == 30                      # 3 板 × 10 路
    assert bch.FIU["1_CH1"] == "IO/FIU/FIU1OUT_Channel1/Value"
    assert bch.FIU["2_CH10"] == "IO/FIU/FIU2_OUT_Channel10/Value"
    assert bch.FIU["3_CH9"] == "IO/FIU/FIU3_OUT_Channel9/Value"


def test_signal_routing_full_set():
    assert len(bch.SIGNAL_ROUTING) == 56           # DO24/AO4/PO4/RES24
    assert bch.SIGNAL_ROUTING["DO0"] == \
        "IO/HardLine IO Model/MDLDataToController/MDLSignalRouting/DO0/Value"
    assert bch.SIGNAL_ROUTING["RES23"] == \
        "IO/HardLine IO Model/MDLDataToController/MDLSignalRouting/RES23/Value"


def test_power_channels_verbatim():
    # "VlotageControl" 原模型拼写、"ON//OFF" 双斜杠转义,必须原样保留
    assert bch.PWR_VOLT == "IO/PowerControl/VlotageControl/Value"
    assert bch.PWR_ON == "IO/PowerControl/ON//OFF/Value"
    assert bch.PWR_CURR == "IO/PowerControl/CurrentControl/Value"
    assert bch.PWR_RELAY == "IO/PowerControl/Power_Relay/Value"
    assert bch.IGN == "IO/PowerControl/IGN/Value"


def test_daq_full_set_and_di_ports():
    assert len(bch.DAQ) == 84                      # AI32 + AO4 + DI24 + DO24
    assert bch.DAQ["DI0"] == \
        "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Digital Input/port0/DI0"
    # 编号非连续:DI8 在 port2,DI9 在 port1(照抄 sdf,勿公式化)
    assert bch.DAQ["DI8"].endswith("port2/DI8")
    assert bch.DAQ["DI9"].endswith("port1/DI9")
    assert bch.DAQ["DO23"].endswith("port0/DO23")


# ---------------------------------------------------------------- 等价性锁定
# 分层改造前(单文件 common/channels.py)的 17 条全路径字面量快照。
# 新拼装路径经 ChannelHelper 归一化(反斜杠→正斜杠)后必须逐字节相同,
# 且参数 API 分流表达式(_to_param_expression)必须一致 —— 锁定"行为零变化"。

from helpers.channel import _to_param_expression          # noqa: E402
from projects.p2546.common import bench as bench_mod      # noqa: E402
from projects.p2546.common import channels as proj_ch     # noqa: E402
from projects.p2546.left_heating import channels as mod_ch  # noqa: E402

_IO = "Targets\\Controller\\Simulation Models\\Models\\TongYu_IO\\Parameters\\IO"
_CAN = _IO + "\\CAN IO Model\\CAN BUS\\MDLSoftECUDataToBus"

OLD_PATHS = {                                             # 改造前 channels.py 原文快照
    "CH_KEY_STATE": _CAN + "\\BCM_VehSt1_2AB_Msg\\KeyState\\Value",
    "CH_ENG_STATE": _CAN + "\\mrEMS_EngSt1_117_Msg\\EngState\\Value",
    "CH_CRASH": _CAN + "\\srP_Msg1_20E_Msg\\CrashInfo\\Value",
    "CH_PWR_VOLT": _IO + "\\PowerControl\\VlotageControl\\Value",
    "CH_PWR_CURR": _IO + "\\PowerControl\\CurrentControl\\Value",
    "CH_PWR_ON": _IO + "\\PowerControl\\ON//OFF/Value",
    "CH_PWR_RELAY": _IO + "\\PowerControl\\Power_Relay\\Value",
    "CH_IGN": _IO + "\\PowerControl\\IGN\\Value",
    "CH_HU_HEAT_REQ": _CAN + "\\HU_SEATSET_3F4_Msg\\HU_DrvSeatHeat\\Value",
    "CH_RES2": _IO + "\\HardLine IO Model\\MDLDataToController\\MDLSignalRouting\\RES2\\Value",
    "CH_DO0": _IO + "\\HardLine IO Model\\MDLDataToController\\MDLSignalRouting\\DO0\\Value",
    "CH_FIU3_CH7": _IO + "\\FIU\\FIU3_OUT_Channel7\\Value",
    "CH_FIU3_CH9": _IO + "\\FIU\\FIU3_OUT_Channel9\\Value",
    "CH_FIU1_CH1": _IO + "\\FIU\\FIU1OUT_Channel1\\Value",
    "CH_FIU1_CH10": _IO + "\\FIU\\FIU1OUT_Channel10\\Value",
    "CH_HEAT_OUT_HARD": r"Targets\Controller\Hardware\Chassis\DAQ\Dev1\Digital Input\port0\DI0",
    "CH_HEAT_OUT_CAN": (r"Targets\Controller\Hardware\Chassis\NI-XNET\CAN\ECU\Incoming"
                        r"\Single-Point\SEAT_DrvStd (993)\IndicatorDrvSeatHeat"),
}

NEW_PATHS = {
    "CH_KEY_STATE": proj_ch.CH_KEY_STATE,
    "CH_ENG_STATE": proj_ch.CH_ENG_STATE,
    "CH_CRASH": proj_ch.CH_CRASH,
    "CH_PWR_VOLT": bench_mod.CH_PWR_VOLT,
    "CH_PWR_CURR": bench_mod.CH_PWR_CURR,
    "CH_PWR_ON": bench_mod.CH_PWR_ON,
    "CH_PWR_RELAY": bench_mod.CH_PWR_RELAY,
    "CH_IGN": bench_mod.CH_IGN,
    "CH_HU_HEAT_REQ": mod_ch.CH_HU_HEAT_REQ,
    "CH_RES2": mod_ch.CH_RES2,
    "CH_DO0": mod_ch.CH_DO0,
    "CH_FIU3_CH7": mod_ch.CH_FIU3_CH7,
    "CH_FIU3_CH9": mod_ch.CH_FIU3_CH9,
    "CH_FIU1_CH1": mod_ch.CH_FIU1_CH1,
    "CH_FIU1_CH10": mod_ch.CH_FIU1_CH10,
    "CH_HEAT_OUT_HARD": mod_ch.CH_HEAT_OUT_HARD,
    "CH_HEAT_OUT_CAN": mod_ch.CH_HEAT_OUT_CAN,
}


def _norm(s):
    """ChannelHelper._full 的归一化口径:反斜杠全转正斜杠。"""
    return s.replace("\\", "/")


def test_17_channel_paths_byte_identical_after_normalize():
    assert set(OLD_PATHS) == set(NEW_PATHS)
    for name in OLD_PATHS:
        assert _norm(NEW_PATHS[name]) == _norm(OLD_PATHS[name]), name


def test_param_expression_routing_unchanged():
    """参数 API 分流必须走同一分支(模型参数→参数表达式;DAQ 硬件→None 走通道 API)。"""
    for name in OLD_PATHS:
        assert _to_param_expression(NEW_PATHS[name]) == _to_param_expression(OLD_PATHS[name]), name


# ---------------------------------------------------------------- 复位三级合并
import os                          # noqa: E402

import yaml                        # noqa: E402

from helpers.config_merge import merge_reset_channels  # noqa: E402

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_merge_reset_channels_order():
    """bench → project → module,后者覆盖同名键。"""
    assert merge_reset_channels({"a": 1, "b": 1}, {"b": 2}, [{"c": 3}, {"c": 4}]) == \
        {"a": 1, "b": 2, "c": 4}
    assert merge_reset_channels(None) == {}
    assert merge_reset_channels({"a": 1}, None, [None, {}]) == {"a": 1}


def test_reset_split_bench_vs_module():
    """bench.yaml 只留台架级安全值(5 条电源)/ 模块激励复位迁到 module.yaml(7 条)。"""
    bench = yaml.safe_load(open(os.path.join(_REPO, "config", "bench.yaml"), encoding="utf-8"))
    module = yaml.safe_load(open(os.path.join(_REPO, "projects", "p2546", "left_heating",
                                              "module.yaml"), encoding="utf-8"))
    bench_resets = bench["veristand"]["reset_channels"]
    module_resets = module["reset"]
    assert len(bench_resets) == 5 and len(module_resets) == 7
    assert all("PowerControl" in k for k in bench_resets)
    assert all("PowerControl" not in k for k in module_resets)
    # 合并结果 = 原单级 7 条模块 + 新增 5 条台架安全值 = 12 条
    assert len(merge_reset_channels(bench_resets, None, [module_resets])) == 12

