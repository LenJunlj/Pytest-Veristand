# -*- coding: utf-8 -*-
"""C206-10 左后三排加热 —— 模块激励（通道绑定；动作实现见 common/seat_heating.py）"""
from projects.c206_10.common.seat_heating import SeatHeatingStimulus
from projects.c206_10.left_rear_heating.channels import (
    CH_CAN_IND, CH_FIU1_CH1, CH_FIU1_CH10, CH_FIU3_NTC, CH_FIU3_NTC_LEGACY, CH_HARD_OUT,
    CH_HEAT_LVL, CH_LIGHTS, CH_RES1, CH_SWITCH, NTC_FAULT, OUT_FAULT,
)


class Stimulus(SeatHeatingStimulus):
    CH_HEAT_LVL = CH_HEAT_LVL
    CH_CAN_IND = CH_CAN_IND
    CH_HARD_OUT = CH_HARD_OUT
    CH_LIGHTS = CH_LIGHTS
    CH_FIU3_NTC = CH_FIU3_NTC
    CH_FIU3_NTC_LEGACY = CH_FIU3_NTC_LEGACY
    CH_FIU1_CH1 = CH_FIU1_CH1
    CH_FIU1_CH10 = CH_FIU1_CH10
    CH_SWITCH = CH_SWITCH
    CH_RES1 = CH_RES1
    NTC_FAULT = NTC_FAULT
    OUT_FAULT = OUT_FAULT
