# -*- coding: utf-8 -*-
"""通道读写 helper：统一别名前缀 + 写入自动分流（通道 API / 模型参数 API）+ 带超时的稳态等待

P2546 台架实证（niveristand 4.0.0 + VS2020 Gateway，2026-11-06）：
- 读：workspace 通道 API，全路径、只认正斜杠（反斜杠自动转换，存量 .seq 路径原样可用）；
- 写模型参数：通道层 Parameters/... 全部 is_writable=False（set_single_channel_value 拒绝），
  必须走 Factory().get_imodel_manager2(gateway).set_single_parameter_value()——
  TestStand 存量序列等价机制。参数表达式 = 通道全路径去掉
  "Targets/<target>/Simulation Models/Models/" 前缀和 "Parameters/" 层。
- 写非模型通道（Custom Devices 程控电源 / CAN Event-Triggered 电阻板帧 / Inports）仍走通道 API。
"""
import time

_PARAM_MARK = "/Simulation Models/Models/"


def _to_param_expression(name: str):
    """Targets/<target>/Simulation Models/Models/<model>/Parameters/<rest>
       → 参数表达式 "<model>/<rest>"（正斜杠）。非该形式返回 None。"""
    p = name.replace("\\", "/")
    i = p.find(_PARAM_MARK)
    if i < 0:
        return None
    tail = p[i + len(_PARAM_MARK):]           # "<model>/Parameters/<rest>"
    model, sep, rest = tail.partition("/")
    if sep and rest.startswith("Parameters/"):
        return model + "/" + rest[len("Parameters/"):]
    return None


class ChannelHelper:
    def __init__(self, workspace, prefix, model_manager=None, target="Controller"):
        self._ws = workspace
        self._prefix = prefix
        self._mm = model_manager                # IModelManager2；None 时模型参数写入不可用
        self._target = target

    def _full(self, name):
        name = name.replace("\\", "/")
        if "/" in name or not self._prefix:
            return name
        return name if name.startswith(self._prefix) else self._prefix + name

    def set(self, name, value):
        """模型参数路径自动转参数表达式走 ModelManager；其余走通道 API。"""
        expr = _to_param_expression(name)
        if expr is not None:
            if self._mm is None:
                raise RuntimeError("模型参数写入需要 ModelManager（conftest 的 model_manager fixture）")
            self._mm.set_single_parameter_value(self._target, expr, float(value))
        else:
            self._ws.set_single_channel_value(self._full(name), float(value))

    def get(self, name):
        # Parameters 层通道读正常（实测），统一走通道 API
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
