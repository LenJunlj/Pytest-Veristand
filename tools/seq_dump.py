# -*- coding: utf-8 -*-
"""TestStand .seq 结构化 dump（需本机装 TestStand 2020，interop 从 GAC 按路径加载）。

产出：序列(53+) → Setup/Main/Cleanup → 步骤（顺序、名称、属性树限深遍历）→ JSON。
字符串挖掘拿不到的部分全在这里：步骤执行顺序、每步参数值、表达式、FIU↔故障映射。

实证确认的 API（interop 20.0.0.49158）：
    sf.NumSequences / sf.GetSequence(i) / sf.GetSequenceByName(name)
    seq.Name / seq.GetNumSteps(StepGroups.X) / seq.GetStep(index, StepGroups.X)
    obj.AsPropertyObject() → GetNumSubproperties/GetNthSubpropertyName/GetVal*
    枚举 StepGroups: StepGroup_Setup=0, StepGroup_Main=1, StepGroup_Cleanup=2

用法：
    python tools/seq_dump.py "projects/p2546/left_heating/samples/P2546_左后大屏加热.seq" [-o reports/xxx_dump.json]

注意：TestStand Engine 在解释器退出时析构会挂死 —— 全程 try/finally + os._exit 硬退出。
"""
import argparse
import json
import os
import sys

MAX_DEPTH = 4
MAX_SUBPROPS = 60
TRUNC = 300
SKIP_BRANCHES = {"AdditionalResults", "Runtime", "Icon", "IconSmall", "ModulePrototype"}


def P(*a):
    print(*a, flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("seq")
    ap.add_argument("-o", "--out")
    args = ap.parse_args()
    seq_path = os.path.abspath(args.seq)
    out_path = args.out or os.path.join(
        "reports", os.path.splitext(os.path.basename(args.seq))[0] + "_dump.json")
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

    exit_code = 1
    try:
        import glob
        import pythonnet
        pythonnet.load("netfx")
        import clr
        ASSEMBLY = "NationalInstruments.TestStand.Interop.API"
        cands = sorted(glob.glob(
            r"C:\Windows\Microsoft.NET\assembly\GAC_MSIL"
            rf"\{ASSEMBLY}\*\{ASSEMBLY}.dll"))
        if not cands:
            raise RuntimeError("GAC 中找不到 TestStand interop（本机装 TestStand 了吗？）")
        P(f"[stage] interop: {cands[-1].rsplit(chr(92), 2)[-2]}")
        clr.AddReference(cands[-1])
        import NationalInstruments.TestStand.Interop.API as TSApi
        from NationalInstruments.TestStand.Interop.API import StepGroups

        eng = TSApi.Engine()
        eng.SuppressDialogs = True
        P("[stage] Engine 已创建（SuppressDialogs=True）")

        sf = eng.GetSequenceFileEx(seq_path)
        P(f"[stage] 文件已加载，序列数: {sf.NumSequences}")

        def val(po, path):
            for fn in ("GetValString", "GetValNumber", "GetValBoolean"):
                try:
                    v = getattr(po, fn)(path, 0)
                    s = str(v)
                    return s[:TRUNC] + ("…" if len(s) > TRUNC else "")
                except Exception:
                    continue
            return None

        def array_len(po, path):
            # 实证：GetNumElements() 无参、作用于对象自身 → 先取子对象再数
            try:
                obj = po.GetPropertyObject(path, 0)
                return int(obj.GetNumElements())
            except Exception:
                return 0

        def walk(po, path, depth):
            out = {}
            try:
                # 实证：interop 大小写为 GetNumSubProperties / GetNthSubPropertyName（大写 P）
                n = po.GetNumSubProperties(path)
            except Exception:
                return out
            for i in range(min(n, MAX_SUBPROPS)):
                try:
                    name = po.GetNthSubPropertyName(path, i, 0)   # 实证：3 参数签名
                except Exception:
                    continue
                if name in SKIP_BRANCHES:
                    continue
                full = f"{path}.{name}" if path else name
                # 数组型属性：枚举元素（变量映射表存在这里）
                nel = array_len(po, full) if depth < MAX_DEPTH else 0
                if nel > 0:
                    elems = []
                    for e in range(min(nel, 40)):
                        ep = f"{full}[{e}]"
                        sub = walk(po, ep, depth + 1)
                        v = val(po, ep)
                        elems.append(sub if sub else v)
                    out[name] = elems
                    continue
                sub = walk(po, full, depth + 1) if depth < MAX_DEPTH else {}
                v = val(po, full)
                if sub:
                    out[name] = sub
                    if v is not None and len(sub) < 4:
                        out[name]["__value__"] = v
                elif v is not None:
                    out[name] = v
            if n > MAX_SUBPROPS:
                out["__more_subprops__"] = n - MAX_SUBPROPS
            return out

        groups = [("Setup", StepGroups.StepGroup_Setup),
                  ("Main", StepGroups.StepGroup_Main),
                  ("Cleanup", StepGroups.StepGroup_Cleanup)]

        dump = {"file": os.path.basename(args.seq), "sequences": [], "file_globals": None}
        for si in range(sf.NumSequences):
            seq = sf.GetSequence(si)
            try:
                name = str(seq.Name)
            except Exception:
                name = f"Sequence#{si}"
            entry = {"name": name, "groups": {}}
            for gname, g in groups:
                steps = []
                try:
                    cnt = seq.GetNumSteps(g)
                except Exception as e:
                    P(f"[warn] GetNumSteps({gname})@{name}: {e}")
                    cnt = 0
                for i in range(cnt):
                    try:
                        st = seq.GetStep(i, g)   # 实证签名：GetStep(index, group)
                    except Exception as e:
                        P(f"[warn] GetStep({i},{gname})@{name}: {e}")
                        continue
                    rec = {"idx": i}
                    try:
                        rec["name"] = str(st.Name)
                    except Exception:
                        rec["name"] = f"step#{i}"
                    try:
                        rec["props"] = walk(st.AsPropertyObject(), "", 0)
                    except Exception:
                        rec["props"] = {}
                    steps.append(rec)
                if steps:
                    entry["groups"][gname] = steps
            dump["sequences"].append(entry)
            P(f"  [{si + 1}/{sf.NumSequences}] {name} "
              + " ".join(f"{k}:{len(v)}" for k, v in entry["groups"].items()))

        try:
            fg = sf.FileGlobalsDefaultValues
            dump["file_globals"] = walk(fg, "", 0)
        except Exception as e:
            P(f"[warn] FileGlobals 读取失败: {e}")

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(dump, f, ensure_ascii=False, indent=1)
        P(f"[done] {out_path}")
        exit_code = 0
    except Exception:
        import traceback
        traceback.print_exc()
    finally:
        # TestStand Engine 析构挂死：纯读取操作，硬退出
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(exit_code)


if __name__ == "__main__":
    main()
