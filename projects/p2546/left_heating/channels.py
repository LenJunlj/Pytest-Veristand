# -*- coding: utf-8 -*-
"""P2546 左后大屏加热 —— 模块层通道与值域

通道本体来自台架层 bench_io（相对标识），全路径由项目层 channels.bench() 拼装。
本文件只装"左后大屏加热"的功能语义（存量 .seq 事实，换模块整套替换）：

- FIU3 CH7/CH9 分工：ch7=前提/退出条件系列、ch9=故障恢复系列
- FIU1 CH1/CH10：CH1 开路/短地，CH10 短地配合（=2，原文不复位会泄漏 — 已修）
- RES2=NTC 阻值模拟、DO0=加热开关硬线、DI0=加热输出采集
- 值域 HEAT_REQ/NTC_FAULT/OUT_FAULT：模块层（分层方案 D3：
  sdf 无故障值语义、跨项目同值无证据，故不升台架层）

生成依据：reports/P2546_左后大屏加热_dump.json（tools/seq_dump.py 产出）。
"""
from bench_io.channels import (
    FIU1_CH1, FIU1_CH10, FIU3_CH7, FIU3_CH9, HW_DI0, RT_DO0, RT_RES2,
)
from projects.p2546.common.channels import bench, can

# ---- 功能 → 台架通道绑定 ----
CH_RES2 = bench(RT_RES2)                 # NTC 阻值模拟
CH_DO0 = bench(RT_DO0)                   # 加热开关（硬线）
CH_FIU3_CH7 = bench(FIU3_CH7)            # NTC 故障注入：前提/退出条件系列
CH_FIU3_CH9 = bench(FIU3_CH9)            # NTC 故障注入：故障恢复系列
NTC_CHANNELS = {"ch7": CH_FIU3_CH7, "ch9": CH_FIU3_CH9}
CH_FIU1_CH1 = bench(FIU1_CH1)            # 加热输出故障注入（开路=2 / 短地=1）
CH_FIU1_CH10 = bench(FIU1_CH10)          # 加热输出短地配合通道（短地时=2，照抄存量）

# 加热请求（HU 下发，项目 CAN 接口段拼接；功能信号属模块层）
CH_HU_HEAT_REQ = can("HU_SEATSET_3F4_Msg", "HU_DrvSeatHeat")     # Drv=主驾/左侧

# ---- 采集（读） ----
# 存量 .seq 误写为 DI1（恒 0）；实测 DI0 随加热请求 0→1 响应，2026-11-06 用户确认
CH_HEAT_OUT_HARD = HW_DI0
# DUT 功能报文（XNET 端口 ECU 口 = p2546 的 DUT 总线，接线事实见 bench_io/registry.csv）
CH_HEAT_OUT_CAN = ("Targets/Controller/Hardware/Chassis/NI-XNET/CAN/ECU/Incoming"
                   "/Single-Point/SEAT_DrvStd (993)/IndicatorDrvSeatHeat")

# ---- 值域（照抄存量） ----
# 加热请求编码（实证，2026-11-06 评审）：0=无请求（DUT 保持原状态）/ 1=OFF / 2=一档 / 3=二档 / 4=三档
# 依据：库序列"加热三档请求"= 写4→等1s→写0→等1s，而历史报告随后采到 CAN 仍为 4（说明 0 不是 OFF）；
#       序列"加热OFF"= 写1→等1s→写0，报告实测 CAN=1。
HEAT_REQ = {"off": 1.0, "level1": 2.0, "level2": 3.0, "level3": 4.0}
HEAT_REQ_NONE = 0.0     # "加热NO Request"：不改变当前档位
NTC_FAULT = {"short_gnd": 14.0, "short_vcc": 12.0, "open": 8.0}   # FIU3_CH9/CH7 值
OUT_FAULT = {"short_gnd": 1.0, "open": 2.0}                        # FIU1_CH1 值
