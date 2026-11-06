# -*- coding: utf-8 -*-
"""全局 fixture 分层（P1 骨架核心）：

  session 级：bench_config → bench_lock（台架互斥）→ veristand（连接/部署，整个会话一次）
  function 级：vs / channel（每个用例前后把关键通道压回安全状态，防状态泄漏）
"""
import os
import sys

import pytest
import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from helpers.bench_lock import BenchLock, LockBusy          # noqa: E402
from helpers.channel import ChannelHelper                    # noqa: E402

BENCH_CONFIG_PATH = os.environ.get("HIL_BENCH_CONFIG", "config/bench.yaml")

# junitxml 输出目录预创建（旧版 pytest 不会自动建目录；且不依赖运行时 cwd）
os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports"), exist_ok=True)


@pytest.fixture(scope="session")
def bench_config():
    with open(BENCH_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="session")
def bench_lock(bench_config):
    """台架互斥：整个 pytest 会话持有；被占用时按 lock.on_busy 决定 fail 或 skip。"""
    cfg = bench_config.get("lock", {})
    lock = BenchLock(
        cfg.get("path", "C:/HIL/bench.lock"),
        cfg.get("stale_after_s", 43200),
    )
    try:
        lock.acquire()
    except LockBusy as busy:
        if cfg.get("on_busy", "fail") == "skip":
            pytest.skip(f"[锁] {busy}")
        raise
    yield lock
    lock.release()


@pytest.fixture(scope="session")
def veristand(bench_config, bench_lock):
    """连接 Gateway 并按配置部署/附加；整个会话只做一次，结束断开。

    mode=attach  附加到已部署系统（白天人工调试的安全默认，不会踢掉别人的会话）
    mode=deploy  完整部署系统定义（CI 夜间回归用；会独占台架——但我们持有锁）

    实证（P2546 台架，niveristand 4.0.0 + VS2020）：前台 VeriStand 已部署时
    connect_to_system 反而失败（ERunConfiguration 3090002）。attach 的正确姿势是
    先 get_system_state 探测：已有活动系统且路径匹配 → 直接复用，不 connect；
    否则才 connect_to_system（deploy=False 附加 / deploy=True 部署）。
    """
    cfg = bench_config["veristand"]
    from niveristand.clientapi import Factory, SystemState   # 延迟导入：纯单元测试不需要装 VeriStand
    ws = Factory().get_iworkspace2()
    deploy = str(cfg.get("mode", "attach")).lower() == "deploy"
    connected = False
    if not deploy:
        try:
            state, active_sdf, _targets = ws.get_system_state()
            want = os.path.normcase(os.path.normpath(cfg["system_definition"]))
            have = os.path.normcase(os.path.normpath(active_sdf)) if active_sdf else ""
            if state == SystemState.ACTIVE and want == have:
                print(f"[veristand] 附加到已运行系统: {active_sdf}")
                yield ws
                return                     # 复用会话，不做 disconnect（不是我们连接的）
        except Exception as e:
            print(f"[veristand] 探测活动系统失败，回退 connect_to_system: {e}")
    ws.connect_to_system(
        cfg["system_definition"], deploy, int(cfg.get("deploy_timeout_ms", 120000)))
    connected = True
    yield ws
    if connected:
        try:
            ws.disconnect_from_system("", False)   # 不 undeploy，系统留给台架
        except Exception as e:
            print(f"[veristand] 断开时出现异常（不掩盖测试结果）: {e}")


@pytest.fixture(scope="session")
def model_manager(bench_config):
    """模型参数读写接口 —— 激励写入的唯一正确通道（实证：Parameters 通道层只读，
    TestStand 存量等价机制即 ModelManager 参数 API；见 helpers/channel.py 头注）。"""
    from niveristand.clientapi import Factory
    return Factory().get_imodel_manager2(
        bench_config["veristand"].get("gateway", "localhost"))


@pytest.fixture
def vs(veristand, bench_config, model_manager):
    """function 级：用例前 + 用例后都把 reset_channels 压回安全状态。

    两侧都执行是刻意的：setup 侧保证上一条用例（或手工操作）的残留被清掉，
    teardown 侧保证本条用例的注入不泄漏给下一条。故障注入通道加进 reset_channels 即可。
    """
    vc = bench_config["veristand"]
    helper = ChannelHelper(veristand, vc.get("channel_prefix", "Aliases/"),
                           model_manager=model_manager,
                           target=vc.get("model_target", "Controller"))

    def apply_resets():
        # 走 ChannelHelper：反斜杠全路径自动转正斜杠 + 前缀规则单一来源
        for name, value in vc.get("reset_channels", {}).items():
            try:
                helper.set(name, value)
            except Exception as e:
                print(f"[vs] 复位 {name} 失败: {e}")

    apply_resets()
    yield veristand
    apply_resets()


@pytest.fixture
def channel(vs, bench_config, model_manager):
    """便捷读写通道；稳态等待用 channel.wait_near(...)。
    模型参数路径的 set 自动走 ModelManager 参数 API（见 ChannelHelper）。"""
    vc = bench_config["veristand"]
    return ChannelHelper(vs, vc.get("channel_prefix", "Aliases/"),
                         model_manager=model_manager,
                         target=vc.get("model_target", "Controller"))
