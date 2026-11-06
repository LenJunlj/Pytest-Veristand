# -*- coding: utf-8 -*-
"""VeriStand ↔ Python 连通性冒烟测试（4 步）

在哪跑：装有 VeriStand 客户端/Gateway 的机器（先在台架机上跑）
怎么跑：python smoke_vs.py
然后：  无论成败，把完整输出（含报错栈）贴回对话。
        第 4 步的别名请改成你系统定义里真实存在的通道别名；
        连前 3 步都失败也没关系——失败信息本身就是诊断数据。
"""
import sys
import traceback

print("=" * 60)
print("Python :", sys.version.replace("\n", " "))
print("解释器 :", sys.executable)
print("=" * 60)


def run_step(n, desc, fn):
    try:
        ret = fn()
        suffix = "" if ret is None else f"  ->  {ret}"
        print(f"[{n}/4] OK    {desc}{suffix}")
        return True
    except Exception:
        print(f"[{n}/4] FAIL  {desc}")
        traceback.print_exc()
        return False


# 1/4 底层依赖 pythonnet（对 Python 版本敏感）
ok = run_step(1, "导入 pythonnet (clr)", lambda: (__import__("clr"), None)[1])

# 2/4 niveristand 包本体（顺带打印已装版本）
if ok:
    def _import_ns():
        import niveristand  # noqa: F401
        from importlib.metadata import version
        return f"已装版本 {version('niveristand')}"
    ok = run_step(2, "导入 niveristand", _import_ns)

# 3/4 连接本机 Gateway（此机没装 VeriStand 客户端则在此步失败，属预期）
if ok:
    def _get_ws():
        from niveristand.clientapi import Factory
        ws = Factory().get_iworkspace2()
        return f"工作区对象 {type(ws).__name__}"
    ok = run_step(3, "连接本机 Gateway", _get_ws)

# 4/4 通道读探针（把别名换成真实的；方法名以实际安装版本为准，报错也贴回来）
if ok:
    def _read_probe():
        from niveristand.clientapi import Factory
        ws = Factory().get_iworkspace2()
        return ws.get_single_channel_value("Aliases/DesiredRPM")
    run_step(4, "读通道探针（记得改别名）", _read_probe)

print("=" * 60)
print("结束：请把以上完整输出（含报错栈）贴回对话。")
