# -*- coding: utf-8 -*-
"""P2546 项目层通道 —— 模型前缀 + 车型 CAN 矩阵 + 整车值域(跨模块共用)

三层分工（docs/通道分层方案.md，2026-11-07 落地）：
- 台架层  bench_io/channels.py      通道本体与相对标识（同台架跨项目不动）
- 项目层  本文件                    模型前缀 + 车型 CAN 矩阵信号 + 整车值域
- 模块层  <模块>/channels.py        功能绑定（CH7/CH9 分工等）+ 模块值域

双项目实证：C026-10 与 p2546 模型同名 TongYu_IO、台架层通道逐项一致，
CAN 矩阵零交集 —— 换项目只改本文件的 model_name 与 CAN 信号；换模块只改模块层。

拼接约定：台架层存"相对标识"（前斜杠、不含前缀），本文件 bench() 拼全路径；
全路径经 ChannelHelper 自动转正斜杠并分流参数 API（见 helpers/channel.py 头注）。
"""

_MODEL = "TongYu_IO"     # 与 projects/p2546/project.yaml 的 model_name 同源
_PREFIX = "Targets/Controller/Simulation Models/Models/%s/Parameters" % _MODEL
_CAN_BUS = _PREFIX + "/IO/CAN IO Model/CAN BUS/MDLSoftECUDataToBus"


def bench(rel: str) -> str:
    """台架层相对标识 → 模型参数全路径（前斜杠）。rel 形如 "IO/FIU/FIU3_OUT_Channel7/Value"。"""
    return _PREFIX + "/" + rel


def can(msg: str, sig: str) -> str:
    """车型 CAN 矩阵信号 → 全路径。msg 形如 "BCM_VehSt1_2AB_Msg"，sig 形如 "KeyState"。"""
    return _CAN_BUS + "/" + msg + "/" + sig + "/Value"


# ---- 车型 CAN 矩阵信号（整车事实：报文名/信号名换车型必变） ----
CH_KEY_STATE = can("BCM_VehSt1_2AB_Msg", "KeyState")          # 电源模式
CH_ENG_STATE = can("mrEMS_EngSt1_117_Msg", "EngState")        # 发动机状态
CH_CRASH = can("srP_Msg1_20E_Msg", "CrashInfo")               # 碰撞信息

# ---- 整车值域 ----
# 发动机状态（照抄存量"设置发动机状态X"写入值）
ENG_STATE = {"not_running": 0.0, "running": 1.0, "crank": 2.0, "fault": 3.0}
# 电源模式 KeyState 编码（照抄存量；2026-11-07 自 bench.py 注释迁入，复用清单疑点 5b 闭环）
KEY_STATE = {"off": 0.0, "acc": 1.0, "on": 2.0, "crank_ig": 3.0, "error": 7.0}
