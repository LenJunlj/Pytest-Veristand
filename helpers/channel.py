# -*- coding: utf-8 -*-
"""通道读写 helper：统一别名前缀 + 带超时的稳态等待（稳态校验/故障注入两种形态都够用）"""
import time


class ChannelHelper:
    def __init__(self, workspace, prefix):
        self._ws = workspace
        self._prefix = prefix

    def _full(self, name):
        # 实证（P2546 样本）：台架通道用模型全路径寻址（Targets\...\Value，含 \ 或 /），
        # 只有短名（别名）才需要加前缀。全路径直接透传。
        if "/" in name or "\\" in name or not self._prefix:
            return name
        return name if name.startswith(self._prefix) else self._prefix + name

    def set(self, name, value):
        self._ws.set_single_channel_value(self._full(name), float(value))

    def get(self, name):
        return self._ws.get_single_channel_value(self._full(name))

    def wait_near(self, name, target, tol, timeout_s=10.0, poll_s=0.25, stable_n=2):
        """等待通道进入并保持 [target±tol]（连续 stable_n 次），用于稳态校验。

        超时抛 AssertionError 并带最后读数，方便定位是没到稳态还是别名写错。
        """
        deadline = time.monotonic() + timeout_s
        hits = 0
        last = None
        while time.monotonic() < deadline:
            last = self.get(name)
            if abs(last - target) <= tol:
                hits += 1
                if hits >= stable_n:
                    return last
            else:
                hits = 0
            time.sleep(poll_s)
        raise AssertionError(
            f"等待 {self._full(name)} 到达 {target}±{tol} 超时（{timeout_s}s），最后读数 {last}")
