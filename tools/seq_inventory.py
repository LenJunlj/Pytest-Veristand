# -*- coding: utf-8 -*-
"""从 TestStand .seq（TOF 二进制）生成迁移清单草稿 CSV。

能拿到：步骤/子序列名（中文）、动作步骤名、VeriStand 通道全路径、FileGlobals 信号名。
拿不到：步骤执行顺序、每步参数值、表达式逻辑 —— 那些要在装了 TestStand 的机器上
        跑结构化 dump 才能取出（字符串级挖掘的固有边界）。

用法：
    python tools/seq_inventory.py samples/P2546_左后大屏加热.seq -o docs/migration_inventory.csv
"""
import argparse
import csv
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from seq_strings import ascii_runs, gbk_runs, load_payload

SUGGEST = {
    "前提/退出条件": "公共前置/后置：fixture 或 helper 函数",
    "触发条件": "测试用例 test_（按档位/工况 parametrize）",
    "控温逻辑": "测试用例 test_（按档位 parametrize）",
    "故障恢复": "测试用例 test_（注入→断言→强制清除）",
    "动作步骤": "helpers/stimulus.py 封装函数",
    "通道路径": "通道词汇：channel.set/get 直接用全路径",
    "信号/全局变量": "测量通道词汇表（constants/dataclass）",
}
ORDER = list(SUGGEST.keys())

# TestStand 文件级标准属性（非测试信号），从 FileGlobals 邻近提取时排除
TS_STD_PROPS = {"BatchSync", "ModelFile", "ModelOption", "SFGlobalsScope",
                "UseStepLoadOpt", "UseStepUnloadOpt", "Version"}


def classify_cn(s: str):
    if "前提条件" in s or "退出条件" in s:
        return "前提/退出条件"
    if "触发条件" in s:
        return "触发条件"
    if "控温逻辑" in s:
        return "控温逻辑"
    if "故障恢复" in s:
        return "故障恢复"
    if s.startswith(("设置", "取消")):
        return "动作步骤"
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("seq")
    ap.add_argument("-o", "--out", default="docs/migration_inventory.csv")
    args = ap.parse_args()

    payload = load_payload(args.seq)
    base = os.path.basename(args.seq)

    rows, seen = [], set()

    def add(cat, name, off):
        key = (cat, name)
        if key not in seen:
            seen.add(key)
            rows.append({"序列文件": base, "类别": cat, "名称": name,
                         "偏移": hex(off), "迁移建议": SUGGEST[cat], "状态": "待翻译"})

    for off, s in gbk_runs(payload):
        cat = classify_cn(s.strip())
        if cat:
            add(cat, s.strip(), off)

    fgd_off = None
    for off, s in ascii_runs(payload):
        s = s.strip()
        if s.startswith("Targets\\"):
            add("通道路径", s, off)
        if s == "FileGlobalDefaults":
            fgd_off = off

    # FileGlobals 信号名：紧跟在 FileGlobalDefaults 标记之后的短标识符
    if fgd_off is not None:
        id_pat = re.compile(r"^[A-Za-z][A-Za-z0-9_]{4,29}$")
        for off, s in ascii_runs(payload, minlen=5):
            s = s.strip()
            if s in TS_STD_PROPS:
                continue
            if fgd_off < off < fgd_off + 300 and id_pat.match(s):
                add("信号/全局变量", s.strip(), off)

    rows.sort(key=lambda r: (ORDER.index(r["类别"]), r["名称"]))

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    new_file = not os.path.exists(args.out)
    with open(args.out, "a", newline="", encoding="utf-8-sig") as f:   # utf-8-sig 便于 Excel 打开
        w = csv.DictWriter(f, fieldnames=["序列文件", "类别", "名称", "偏移", "迁移建议", "状态"])
        if new_file:
            w.writeheader()
        w.writerows(rows)

    print(f"共 {len(rows)} 条写入 {args.out}")
    for cat in ORDER:
        n = sum(1 for r in rows if r["类别"] == cat)
        if n:
            print(f"  {cat}: {n}")


if __name__ == "__main__":
    sys.exit(main())
