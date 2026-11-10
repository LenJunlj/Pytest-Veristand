# -*- coding: utf-8 -*-
"""C206-10 右后三排加热 —— 模块层通道与值域

与左后模块（left_rear_heating/channels.py）逐项对应，差异照抄存量 .seq：
- 请求 BCM_TRseatHeatLevelSet、DUT 状态 SeatheatInd_TR
- 硬线输出 DI1（左后用 DI0）
- NTC 故障注入 FIU3_OUT_Channel8（左后用 CH7）
- 后三排开关 MDLSignalRouting DO1（左后用 DO0）
- 加热输出"开路"值 CH1=2（左后同标签写 8 —— 两侧不同，勿统一）
"""
from bench_io.channels import DAQ, FIU, FIU1_CH1, FIU1_CH10, SIGNAL_ROUTING
from projects.c206_10.common.channels import (  # noqa: F401
    CH_HEAT_LVL_TR, HEAT_REQ, HEAT_REQ_NONE, bench, can, dut,
)

# ---- 功能 → 通道绑定 ----
CH_HEAT_LVL = CH_HEAT_LVL_TR                        # 右后：TR
CH_CAN_IND = dut("SCCU_1 (582)", "SeatheatInd_TR")  # DUT 档位状态（CAN2）
CH_HARD_OUT = DAQ["DI1"]                            # 加热硬线输出
# 档位灯实测映射（2026-11-09 台架扫描）：左1/2/3 = DI8/DI9/DI10，右1/2/3 = DI5/DI6/DI7。
# 存量 .seq"报文硬线采集"写的是左 DI2/DI3/DI4 —— 2026-11-07 重建 sdf 后左灯路由已变，
# DI2~DI4 现恒 0（照抄原文会让左灯判定永远失败，此处按台架实测修正）。
CH_LIGHTS = [DAQ["DI8"], DAQ["DI9"], DAQ["DI10"],  # 左1/2/3 档灯
             DAQ["DI5"], DAQ["DI6"], DAQ["DI7"]]   # 右1/2/3 档灯
CH_FIU3_NTC = bench(FIU["3_CH8"])                       # NTC 故障注入
CH_FIU1_CH1 = bench(FIU1_CH1)                       # 加热输出故障注入
CH_FIU1_CH10 = bench(FIU1_CH10)                     # 输出短地配合通道
CH_SWITCH = bench(SIGNAL_ROUTING["DO1"])            # 后三排开关（硬线）
CH_RES1 = bench(SIGNAL_ROUTING["RES1"])             # NTC 阻值模拟

NTC_FAULT = {"short_gnd": 6.0, "open": 8.0}
OUT_FAULT = {"open": 2.0}                           # 右后原文"加热输出开路"= CH1=2
