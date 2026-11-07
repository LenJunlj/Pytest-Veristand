# -*- coding: utf-8 -*-
"""left_heating 项目级 fixture（多个测试模块共用）。断言工具在 checks.py。"""
import time

import allure
import pytest

from projects.p2546.left_heating.stimulus import Stimulus


@pytest.fixture
def bench(channel):
    """台架标准工况 —— 翻译自存量的 Setup(测试用例初始化) / Cleanup(测试用例结束)。"""
    stim = Stimulus(channel)
    with allure.step("台架初始化 bench_ready（电源13.5V/20A、继电器、IGN、KeyState、发动机状态、清FIU）"):
        stim.bench_ready()
    time.sleep(1)                # 原文：初始化后等待 1s
    yield stim
    with allure.step("台架清理 bench_shutdown（撤加热请求、清FIU、断继电器/IGN）"):
        stim.bench_shutdown()
