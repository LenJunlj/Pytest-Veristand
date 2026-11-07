# -*- coding: utf-8 -*-
"""VeriStand .nivssdf 通道分析器(只读)

用法:
    python analyze_sdf.py <sdf路径> [输出目录(默认 sdf同目录/sdf_analysis)]

产出:
    model_io.json    模型 Parameters/IO 全部叶子通道(路径/类型/默认值)
    hardware.json    Hardware 全部通道 + DataSourceNode 模型绑定
    registry.csv     三层归层登记表(台架层/项目层/模块层初判)

依据 docs/通道分层方案.md §2 的三段拆分;归层规则见 layer_for_* 函数。
配套: docs/bench_io_registry.csv(首跑产物,p2546.nivssdf);一次性查询脚本在 reports/sdf_analysis/(gitignored,可弃)。
此工具即交接规划的 gen_channels_draft.py 雏形(拍板 D1~D5 后升级: dump 未登记通道自动出士稿)。
"""
import sys, io, os, csv, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from xml.etree import ElementTree as ET

TYPE_TAGS = {"I32","U32","U16","U64","Double","Boolean","String"}

def children(el):
    return [c for c in el if c.tag not in ("Description","Properties","Errors")]

def get_prop(el, name):
    for p in el.findall("./Properties/Property"):
        if p.attrib.get("Name") == name:
            s = p.find("String")
            if s is not None: return s.text
    return None

def channel_value(ch):
    dv = ch.find("DefaultValue")
    if dv is None: return None, None
    for c in dv:
        if c.tag in TYPE_TAGS: return c.tag, (c.text or "").strip()
        if c.tag == "Elem": return "array", (c.text or "").strip()
    return None, None

def main(sdf, outdir):
    os.makedirs(outdir, exist_ok=True)
    tree = ET.parse(sdf); root = tree.getroot()
    targets = root.find(".//TargetSections")
    # 逐 Target 提取(通常一个 Controller)
    all_model_io, all_hw = [], []
    for target in targets.iter("Target"):
        tname = target.attrib.get("Name","?")
        secs = {c.attrib.get("Name"): c for c in target if c.tag == "Section"}
        # 模型(多个 Section: 每个 = 一个模型)
        if "Simulation Models" not in secs: continue
        models = None
        for c in secs["Simulation Models"].iter("Section"):
            if c.attrib.get("Name") == "Models": models = c; break
        if models is None: continue
        for m in children(models):
            if m.tag != "Section": continue
            mname = m.attrib.get("Name")
            params = None
            for c in m:
                if c.tag=="Section" and c.attrib.get("Name")=="Parameters": params=c; break
            if params is None: continue
            def walk(el, prefix):
                for c in children(el):
                    nm = c.attrib.get("Name","")
                    if c.tag == "Section": walk(c, prefix+nm+"/")
                    elif c.tag == "Channel":
                        typ, val = channel_value(c)
                        all_model_io.append({"model": mname, "target": tname,
                            "path": prefix+nm, "type": typ, "default": val,
                            "expr": get_prop(c, "Expression")})
            walk(params, "")
        # 硬件
        if "Hardware" in secs:
            def walk_hw(el, prefix):
                for c in children(el):
                    nm = c.attrib.get("Name","")
                    if c.tag == "Section": walk_hw(c, prefix+nm+"/")
                    elif c.tag == "Channel":
                        binds = [d.attrib.get("Channel") for d in c.iter("DataSourceNode")]
                        all_hw.append({"target": tname, "path": prefix+nm, "binds": binds})
            walk_hw(secs["Hardware"], "")
    json.dump(all_model_io, open(os.path.join(outdir,"model_io.json"),"w",encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(all_hw, open(os.path.join(outdir,"hardware.json"),"w",encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"model_io: {len(all_model_io)}  hardware: {len(all_hw)}")

    # ---- registry.csv ----
    def layer_params(p):
        if p.startswith("IO/FIU/"): return "台架层"
        if p.startswith("IO/PowerControl/"): return "台架层"
        if "MDLSignalRouting" in p: return "台架层"
        if "MDLSoftECUDataToBus" in p: return "项目层(CAN矩阵)"
        return "模型内部"
    rows = []
    for m in all_model_io:
        p = m["path"]; segs = p.split("/"); parent = segs[-2] if len(segs)>=2 else ""
        lay = layer_params(p)
        if segs[-1]!="Value": continue                       # 只收信号面
        if lay=="模型内部": continue                          # Lookup/Saturation等机制不入主表
        if parent.startswith("Switch"): continue             # Switch机制(Manu_Value等)
        typ = ("FIU注入" if p.startswith("IO/FIU/") else
               "电源控制" if p.startswith("IO/PowerControl/") else
               "硬线路由" if "MDLSignalRouting" in p else "CAN信号")
        rows.append([typ, parent, m["model"]+"/"+p, m["type"] or "", m["default"] or "",
                     "", lay, "", ""])
    def layer_hw(p):
        if "/DAQ/" in p: return "台架层(DAQ)"
        if "CAN/ECU/" in p: return "项目层(DUT CAN)"
        if "CAN1/" in p: return "台架层(CAN1内部总线)"
        return "台架层"
    for h in all_hw:
        p = h["path"]
        binds = "; ".join("/".join(b.split("/")[-4:]) for b in h["binds"])
        typ = ("DI" if "/Digital Input/" in p else "DO" if "/Digital Output/" in p else
               "AI" if "/Analog Input/" in p else "AO" if "/Analog Output/" in p else "XNET")
        rows.append([typ+"硬件", p.split("/")[-1], p, "", "", binds, layer_hw(p), "", ""])
    with open(os.path.join(outdir,"registry.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["类型","通道/信号标识","sdf路径","数据类型","默认值","模型绑定/路由","归层初判","现有代码使用","备注(人工补)"])
        w.writerows(rows)
    from collections import Counter
    c = Counter(r[6] for r in rows)
    print(f"registry: {len(rows)} 行")
    for k,v in sorted(c.items()): print(f"   {v:4d}  {k}")

if __name__ == "__main__":
    sdf = sys.argv[1]
    outdir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(os.path.abspath(sdf)), "sdf_analysis")
    main(sdf, outdir)
