# -*- coding: utf-8 -*-
"""功能 DTC —— 模块级 fixture（对应原文每个序列的 Setup/Cleanup）。"""
import allure
import pytest

from projects.c206_10.dtc.stimulus import Stimulus


@pytest.fixture
def bench(channel):
    """台架标准工况 —— 翻译自存量 Setup「本地加热前提条件」/ Cleanup「测试用例结束」。"""
    stim = Stimulus(channel)
    with allure.step("台架初始化 bench_ready（电源12V/20A/ON、PowerMode=4、Standby、继电器 ON）"):
        stim.bench_ready()
    yield stim
    with allure.step("台架清理 bench_shutdown（电源下电、继电器断、Pre_Off、恢复报文使能/OTA）"):
        stim.bench_shutdown()
