# -*- coding: utf-8 -*-
"""临时提取脚本：把关键序列压缩成人读摘要（用于生成 test_heating.py 的依据）"""
import json

d = json.load(open("reports/P2546_左后大屏加热_dump.json", encoding="utf-8"))

WANT = [
    "测试用例初始化", "测试用例结束",
    "加热一档请求", "加热二档请求", "加热三档请求", "加热NO Request", "加热开关按下",
    "加热输出状态和LED灯信号采集",
    "触发条件测试-加热一档", "触发条件测试-加热三档",
    "加热控温逻辑测试-加热一档", "加热控温逻辑测试-加热三档",
    "前提条件测试_欠压", "退出条件测试_欠压",
    "故障恢复测试-NTC短地故障",
    "设置程控电源13.5V/20A/ON", "取消NTC故障", "设置NTC短地", "设置NTC开路", "设置加热输出短地",
    "设置左后加热NTC阻值5.5kΩ", "设置左后加热NTC阻值7.5kΩ",
    "设置电源模式OFF&硬线IGN无效", "设置整车碰撞",
]

PREFIX = "Targets\\Controller\\Simulation Models\\Models\\TongYu_IO\\Parameters\\IO\\"


def brief_var(v):
    if isinstance(v, dict):
        name = v.get("VariableName", "?")
        if name.startswith(PREFIX):
            name = "IO/" + name[len(PREFIX):]
        return f"{name}={v.get('VariableValue')}"
    return str(v)


for s in d["sequences"]:
    if s["name"] not in WANT:
        continue
    print(f"===== {s['name']} =====")
    for g, steps in s["groups"].items():
        for st in steps:
            p = st.get("props", {})
            t = p.get("NI_StepTypeName", "")
            parts = [f"[{g}] {st['name']}"]
            if t:
                parts.append(f"类型:{t}")
            for varr in ("Variables", "VariableExpressions"):
                if p.get(varr):
                    items = [brief_var(x) for x in p[varr] if x]
                    if items:
                        parts.append(("写:" if varr == "Variables" else "写表达式:") + "; ".join(items))
            if st["name"] == "Wait":
                te = p.get("TimeExpr")
                parts.append(f"等待:{te}s" if te else "等待:?")
            ts = p.get("TS", {})
            if isinstance(ts, dict):
                for ek in ("PreExpr", "PostExpr", "StatusExpr", "PreCond"):
                    ev = ts.get(ek)
                    if ev:
                        parts.append(f"TS.{ek}:{ev}")
            print("  " + " | ".join(parts))

print()
print("===== FileGlobals =====")
fg = d.get("file_globals") or {}
for k, v in fg.items():
    print(f"  {k} = {json.dumps(v, ensure_ascii=False)[:120]}")
