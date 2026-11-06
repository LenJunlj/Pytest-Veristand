# -*- coding: utf-8 -*-
"""临时提取脚本 3：判定限值总表 + FIU 映射 + LED 采集来源 + VOLT + 故障恢复全文"""
import json

d = json.load(open("reports/P2546_左后大屏加热_dump.json", encoding="utf-8"))
SEQ = {s["name"]: s for s in d["sequences"]}


def limit_of(p):
    """把判定步的 Limits/Comp 压成一行"""
    lim = p.get("Limits", {})
    comp = p.get("Comp", "")
    if not isinstance(lim, dict):
        return f"comp={comp} {lim}"
    hi = lim.get("HighExpr") if lim.get("UseHighExpr") == "True" and lim.get("HighExpr") else lim.get("High")
    lo = lim.get("LowExpr") if lim.get("UseLowExpr") == "True" and lim.get("LowExpr") else lim.get("Low")
    return f"[{lo}, {hi}] comp={comp}"


print("========== ① 各测试序列的判定限值总表 ==========")
for seqname in ["触发条件测试-加热三档", "触发条件测试-加热二档", "触发条件测试-加热一档", "触发条件测试-加热OFF",
                "加热控温逻辑测试-加热三档", "加热控温逻辑测试-加热二档", "加热控温逻辑测试-加热一档",
                "前提条件测试_欠压", "退出条件测试_欠压",
                "故障恢复测试-NTC短地故障", "故障恢复测试-NTC开路故障", "故障恢复测试-输出短地故障",
                "故障恢复测试-欠压故障", "故障恢复测试-过压故障"]:
    if seqname not in SEQ:
        continue
    print(f"-- {seqname}")
    for st in SEQ[seqname]["groups"].get("Main", []):
        p = st.get("props", {})
        if "反馈" in st["name"]:
            print(f"   {st['name']}: 源={p.get('DataSource')} {limit_of(p)}")

print()
print("========== ② 全文件 FIU 通道写值对（注入/取消映射） ==========")
fiu = {}
for s in d["sequences"]:
    for g, steps in s["groups"].items():
        for st in steps:
            for v in (st.get("props", {}).get("Variables") or []):
                if isinstance(v, dict) and "FIU" in str(v.get("VariableName", "")):
                    key = v["VariableName"].split("\\")[-2] + "\\" + v["VariableName"].split("\\")[-1]
                    fiu.setdefault(key, set()).add(str(v.get("VariableValue")))
                    # 记录步骤名
for k in sorted(fiu):
    print(f"   {k}: 值 {sorted(fiu[k])}")

print()
print("========== ③ LED / VOLT 信号：谁在写/读 ==========")
for s in d["sequences"]:
    for g, steps in s["groups"].items():
        for st in steps:
            p = st.get("props", {})
            for v in (p.get("Variables") or []):
                if isinstance(v, dict):
                    tgt = str(v.get("VariableValue", ""))
                    if "LEDHeat" in tgt or tgt.endswith(".VOLT") or "VOLT" == tgt.split(".")[-1]:
                        print(f"   [{s['name']}/{st['name']}] 读通道 {v.get('VariableName','')[-60:]} -> {tgt}")

print()
print("========== ④ 故障恢复测试-NTC短地故障 全文 ==========")
for g, steps in SEQ["故障恢复测试-NTC短地故障"]["groups"].items():
    for st in steps:
        p = st.get("props", {})
        vars_ = p.get("Variables") or []
        w = "; ".join(f"{(x.get('VariableName','') or '').split(chr(92))[-2]}={x.get('VariableValue')}"
                      for x in vars_ if isinstance(x, dict))
        te = p.get("TimeExpr", "")
        lim = limit_of(p) if "反馈" in st["name"] else ""
        line = f"[{g}] {st['name']}"
        if w: line += f" | 写:{w}"
        if st["name"] == "Wait" and te: line += f" | 等{te}s"
        if lim: line += f" | 判定源={p.get('DataSource')} {lim}"
        print("  " + line)
