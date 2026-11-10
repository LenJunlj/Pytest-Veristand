# -*- coding: utf-8 -*-
"""C206-10 功能 DTC 模块 —— 通道与值域

DTC 系列在"本地加热前提条件"基础上做单点故障注入，用 UDS 诊断读故障码：
- 温度传感器：主驾 FIU3_OUT_Channel7、副驾 FIU3_OUT_Channel8（短地=14 / 开路=8）
- 加热输出：司机 CH1=8 + CH10=2（原文"主驾加热输出短地"）、副驾 FIU1_CH1=2（原文"开路"）
- 报文/节点丢失：BCM1_11 / BCM1_2 / EEM 报文使能开关（项目层常量）
- 开关卡滞：后三排开关 DO0（左后）/ DO1（右后），按住 55s 触发 91E007/91E107
- 输出开路用例（9/10）还要读 TL/TR 状态与 DI0/DI1 硬线，判定加热是否仍工作

DTC 编码（照抄原文 be_checked_dtc）：90E017 过压 / 90E016 欠压 / C14987 PDC 节点丢失
D14087 BCM1 报文丢失 / 90E211、90E215 主驾温度短地/开路 / 90E811、90E815 副驾
90E413、90E513 座椅加热输出 / 91E007、91E107 左右后开关卡滞
"""
from bench_io.channels import DAQ, FIU, FIU1_CH1, FIU1_CH10, SIGNAL_ROUTING
from projects.c206_10.common.channels import (  # noqa: F401
    CH_EN_BCM1_11, CH_EN_BCM1_2, CH_EN_EEM, CH_HEAT_LVL_TL, HEAT_REQ, HEAT_REQ_NONE,
    bench, dut,
)

CH_HEAT_LVL = CH_HEAT_LVL_TL
CH_CAN_IND_TL = dut("SCCU_1 (582)", "SeatheatInd_TL")
CH_CAN_IND_TR = dut("SCCU_1 (582)", "SeatheatInd_TR")
CH_HARD_TL = DAQ["DI0"]
CH_HARD_TR = DAQ["DI1"]
# 主驾温度传感器 NTC。原文 CH7；2026-11-07 全通道扫描曾判"CH7 无反应、CH9→90E211/90E215"
# 而改 CH9；2026-11-10 台架实跑证据反转（第 2 轮 CH9 下左后 22/23 失败，第 3 轮换 CH7 后通过），
# 用户按现场接线决定统一回 CH7。⚠ 两通道在不同轮次都有成功/失败记录，疑接触不稳：
# 复跑 DTC 05/06 若仍不出码，先确认 CH7 是否真的驱动了 DUT，再谈出码时延。
CH_FIU3_NTC_TL = bench(FIU["3_CH7"])      # 主驾温度传感器（原文 CH7，2026-11-10 回退）
CH_FIU3_NTC_TR = bench(FIU["3_CH8"])      # 副驾温度传感器
CH_FIU1_CH1 = bench(FIU1_CH1)
CH_FIU1_CH10 = bench(FIU1_CH10)
CH_SWITCH_TL = bench(SIGNAL_ROUTING["DO0"])
CH_SWITCH_TR = bench(SIGNAL_ROUTING["DO1"])

NTC_FAULT = {"short_gnd": 6.0, "open": 8.0}
# 加热输出故障值（两侧不同，照抄原文）
OUT_FAULT_TL = {"open": 8.0}          # 司机侧原文"主驾加热输出短地"：CH1=8 + CH10=2
OUT_FAULT_TR = {"open": 2.0}          # 副驾侧原文"副驾加热输出开路"：CH1=2
