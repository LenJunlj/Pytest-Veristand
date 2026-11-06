# -*- coding: utf-8 -*-
"""临时提取脚本 2：判定步骤限值 + 剩余动作步骤参数 + FileGlobals"""
import json

d = json.load(open("reports/P2546_左后大屏加热_dump.json", encoding="utf-8"))
SEQ = {s["name"]: s for s in d["sequences"]}
PREFIX = "Targets\\Controller\\Simulation Models\\Models\\TongYu_IO\\Parameters\\IO\\"


def brief_var(v):
    if isinstance(v, dict):
        name = v.get("VariableName", "?")
        if name.startswith(PREFIX):
            name = "IO/" + name[len(PREFIX):]
        return f"{name}={v.get('VariableValue')}"
    return str(v)


print("========== ① 判定步骤：数据源与限值（触发条件测试-加热一档） ==========")
for st in SEQ["触发条件测试-加热一档"]["groups"]["Main"]:
    nm = st["name"]
    if "反馈" not in nm:
        continue
    p = st.get("props", {})
    print(f"-- {nm}")
    for k in ("DataSource", "Comp", "Limits", "Measurement"):
        if k in p:
            print(f"   {k} = {json.dumps(p[k], ensure_ascii=False)[:300]}")

print()
print("========== ② 采集步骤全文（加热输出状态和LED灯信号采集） ==========")
st = SEQ["加热输出状态和LED灯信号采集"]["groups"]["Main"][0]
print(json.dumps({k: v for k, v in st.get("props", {}).items()
                  if k not in ("TS", "Result")}, ensure_ascii=False, indent=1)[:1200])

print()
print("========== ③ 档位请求/开关/电源/故障注入 的写值 ==========")
for nm in ("加热一档请求", "加热二档请求", "加热三档请求", "加热NO Request", "加热开关按下",
           "设置程控电源13.5V/20A/ON", "设置程控电源继电器",
           "设置NTC短地", "取消NTC故障", "设置加热输出短地", "设置整车碰撞",
           "设置电源模式OFF&硬线IGN无效", "设置发动机状态Running", "设置IGN"):
    if nm not in SEQ:
        print(f"-- {nm}: (不在序列列表)"); continue
    for g, steps in SEQ[nm]["groups"].items():
        for st in steps:
            p = st.get("props", {})
            if st["name"] == "Wait":
                continue
            vars_ = p.get("Variables") or []
            items = "; ".join(brief_var(x) for x in vars_ if x) or "(无写值)"
            print(f"-- [{g}] {st['name']}: {items}")

print()
print("========== ④ 初始化/结束步骤 ==========")
for nm in ("测试用例初始化", "测试用例结束"):
    print(f"-- {nm}:")
    for g, steps in SEQ[nm]["groups"].items():
        for st in steps:
            p = st.get("props", {})
            vars_ = p.get("Variables") or []
            items = "; ".join(brief_var(x) for x in vars_ if x)
            extra = f" 写:{items}" if items else ""
            t = p.get("NI_StepTypeName", "")
            te = p.get("TimeExpr", "")
            wait = f" 等待{te}s" if st["name"] == "Wait" and te else ""
            print(f"   [{g}] {st['name']}{' 类型:'+t if t else ''}{extra}{wait}")

print()
print("========== ⑤ FileGlobals 默认值 ==========")
for k, v in (d.get("file_globals") or {}).items():
    print(f"   {k} = {json.dumps(v, ensure_ascii=False)[:150]}")
