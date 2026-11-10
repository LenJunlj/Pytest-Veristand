# -*- coding: utf-8 -*-
"""C206-10 左后三排加热 —— 模块层通道与值域

通道本体来自台架层 bench_io，全路径由项目层 channels.bench()/can()/dut() 拼装。
本文件只装"左后三排加热"的功能语义（换模块整套替换）：

- 请求：BCM_TLseatHeatLevelSet（TL = 左）
- DUT 状态：CAN2 SCCU_1 (582) SeatheatInd_TL
- 硬线输出：DAQ DI0（右后模块用 DI1）
- 档位灯：左1/2/3 = DI2/DI3/DI4，右1/2/3 = DI5/DI6/DI7（两模块都全量采集 6 路）
- NTC 故障注入：FIU3_OUT_Channel7（右后用 CH8）
- 加热输出故障：FIU1OUT_Channel1；短地配合 CH10（DTC 系列用，CH10=2 + CH1=8）
- 后三排开关（卡滞类）：MDLSignalRouting DO0（右后用 DO1）；NTC 阻值模拟 RES1

判定期望值（EQ 语义）全部随用例内联，本文件只放编码/通道，不藏用例参数。
"""
from bench_io.channels import DAQ, FIU, FIU1_CH1, FIU1_CH10, RT_DO0, SIGNAL_ROUTING
from projects.c206_10.common.channels import (  # noqa: F401  (HEAT_REQ 由 stimulus 转出)
    CH_HEAT_LVL_TL, HEAT_REQ, HEAT_REQ_NONE, bench, can, dut,
)

# ---- 功能 → 通道绑定 ----
CH_HEAT_LVL = CH_HEAT_LVL_TL                      # 左后：TL
CH_CAN_IND = dut("SCCU_1 (582)", "SeatheatInd_TL")  # DUT 档位状态（CAN2）
CH_HARD_OUT = DAQ["DI0"]                          # 加热硬线输出
# 档位灯实测映射（2026-11-09 台架扫描）：左1/2/3 = DI8/DI9/DI10，右1/2/3 = DI5/DI6/DI7。
# 存量 .seq"报文硬线采集"写的是左 DI2/DI3/DI4 —— 2026-11-07 重建 sdf 后左灯路由已变，
# DI2~DI4 现恒 0（照抄原文会让左灯判定永远失败，此处按台架实测修正）。
CH_LIGHTS = [DAQ["DI8"], DAQ["DI9"], DAQ["DI10"],  # 左1/2/3 档灯
             DAQ["DI5"], DAQ["DI6"], DAQ["DI7"]]   # 右1/2/3 档灯
# NTC 故障注入（主驾）。原文 = CH7。2026-11-09 全通道扫描曾判"CH7 无反应、CH9→90E211/90E215"
# 而改 CH9；2026-11-10 台架实跑反转：第 2 轮（CH9）本模块 22/23 失败"仍加热"，第 3 轮（CH7）通过。
# 用户按现场接线决定回 CH7。⚠ 两通道在不同轮次都有成功/失败记录，疑接触不稳：
# 本模块 22/23 再失败时，先确认故障是否真的注入（读回 CH7 值），再判断 DUT 响应时延。
CH_FIU3_NTC = bench(FIU["3_CH7"])                 # NTC 故障注入（主驾，原文 CH7）
CH_FIU3_NTC_LEGACY = bench(FIU["3_CH7"])          # 与上同一通道：保留名字只为复位兼容
CH_FIU1_CH1 = bench(FIU1_CH1)                     # 加热输出故障注入
CH_FIU1_CH10 = bench(FIU1_CH10)                   # 输出短地配合通道
CH_SWITCH = bench(RT_DO0)                         # 后三排开关（硬线）
CH_RES1 = bench(SIGNAL_ROUTING["RES1"])           # NTC 阻值模拟（耐久用例用）

# ---- 值域（照抄存量 .seq 写入值） ----
# NTC 故障：短路到地=14 / 开路=8（FIU3_OUT_Channel7/8）
NTC_FAULT = {"short_gnd": 6.0, "open": 8.0}
# 加热输出故障：左后原文"加热输出开路"写 CH1=8；短地=DTC 系列 CH10=2 + CH1=8（标签与值存疑，见 tests 头注）
OUT_FAULT = {"open": 8.0}
OUT_SHORT_GND = {"ch10": 2.0, "ch1": 8.0}
