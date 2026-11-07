# -*- coding: utf-8 -*-
"""草稿 ↔ 手工版 调用轨迹比对（门4，docs/通道分层方案.md §9.4）

用法:
    python tools/compare_draft.py <草稿.py> <手工版.py> [--json] [--show]

抽取每个 test 函数的两个可比视图,按 dump 序号配对(test_draft_NN ↔ test_NN_*):

1. **事件序列**(必须完全一致):bench.* 调用(参数解析模块常量/星号解包/字典下标)
   与输出判定(草稿的内联 `assert out["hard"]==X` 与手工的 `assert_outputs(out,*CONST)`
   统一为 ("assert", (hard, can)),按读取位置附着)。
2. **睡眠序列**(归一后比较):手工版把"首个动作前的 Wait"并入步骤/省略,故两侧都
   丢弃首个动作之前的睡眠;其余逐项比较(时序是判定语义的一部分,不能放宽)。

白名单(KNOWN 偏差,仅报告不判失败;理由见会话交接.md):
- 33 触发-OFF:手工内联 vs 生成器塌缩成 request_heat('off'),时序等价
- 37 故障恢复-NTC短地:手工版多一段"加热开启确认"(合理增强,原文无此段)
- 41/42 故障恢复-欠压/过压:用户实证改工况(8.4V×3.5s / 17V×3.5s + 中间自检)

退出码: 0 = 全部一致或仅白名单偏差; 1 = 存在非白名单不一致。
"""
import argparse
import ast
import json
import sys

KNOWN_DEVIATIONS = {
    "33": "手工内联 vs 生成器塌缩 request_heat('off')（时序等价）",
    "37": "手工版多一段加热开启确认（合理增强）",
    "41": "用户改工况 8.4V×3.5s + 中间自检（实证修正）",
    "42": "用户改工况 17V×3.5s + 前置自检（实证修正）",
}


# ---------------------------------------------------------------- 常量求值
# Stimulus 方法签名(绑定位置/关键字参数并填默认值:省略参数 ≡ 显式默认值)
_TARGET_SPECS = {
    "request_heat": (("level",), {}),
    "set_heat_request": (("level",), {}),
    "no_heat_request": ((), {}),
    "set_ntc_resistance": (("ohms",), {}),
    "heat_switch": (("pressed",), {}),
    "inject_ntc_fault": (("kind", "ch"), {"ch": "ch9"}),
    "clear_ntc_fault": (("ch",), {"ch": "ch9"}),
    "inject_out_fault": (("kind",), {}),
    "clear_out_fault": ((), {}),
    "read_heat_outputs": ((), {}),
    "set_supply_voltage": (("volts",), {}),
    "set_crash": (("crashed",), {}),
    "set_engine_state": (("state",), {}),
    "set_power_mode": (("key_state", "ign_valid"), {}),
    "bench_ready": ((), {}),
    "bench_shutdown": ((), {}),
}


def _bind(method, args, kwargs):
    """按签名填充默认值 → 规范化位置参数元组;未知方法保留 (args, kwargs)。"""
    spec = _TARGET_SPECS.get(method)
    if spec is None:
        return (tuple(args), tuple(sorted(kwargs.items())))
    names, defaults = spec
    bound = dict(zip(names, args))
    for k, v in kwargs.items():
        bound[k] = v
    return tuple(bound.get(n, defaults.get(n, "<missing>")) for n in names)


def _eval(node, env):
    if isinstance(node, ast.Starred):
        return _eval(node.value, env)
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        v = _eval(node.operand, env)
        return -v if isinstance(v, (int, float)) else v
    if isinstance(node, ast.Name):
        return env.get(node.id, "<%s>" % node.id)
    if isinstance(node, ast.Subscript):
        base = _eval(node.value, env)
        key = _eval(node.slice, env)
        try:
            return base[key]
        except (KeyError, TypeError):
            return "<%s[%r]>" % (getattr(node.value, "id", "?"), key)
    return "<expr>"


def _module_env(tree):
    env = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name):
            try:
                env[node.targets[0].id] = ast.literal_eval(node.value)
            except (ValueError, SyntaxError):
                pass
    return env


def _expand(args, env):
    out = []
    for a in args:
        if isinstance(a, ast.Starred):
            v = _eval(a, env)
            if isinstance(v, tuple):
                out.extend(v)
            else:
                out.append(v)
        else:
            out.append(_eval(a, env))
    return tuple(out)


# ---------------------------------------------------------------- 事件抽取
def _extract(fn, env):
    """→ (事件列表, 睡眠列表);事件 = (kind, payload) 按源码顺序。"""
    raw = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id == "bench":
                kw = {k.arg: _eval(k.value, env) for k in node.keywords if k.arg}
                raw.append((node.lineno, "call", f.attr,
                            _bind(f.attr, _expand(node.args, env), kw)))
            elif isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) \
                    and f.value.id == "time" and f.attr == "sleep":
                raw.append((node.lineno, "sleep", _expand(node.args, env)))
            elif isinstance(f, ast.Name) and f.id == "assert_outputs":
                args = _expand(node.args, env)
                raw.append((node.lineno, "assert", tuple(args[1:3])))   # 跳过 out 变量
        elif isinstance(node, ast.Assert):
            t = node.test
            if isinstance(t, ast.Compare) and isinstance(t.left, ast.Subscript) \
                    and isinstance(t.left.value, ast.Name) and t.left.value.id.startswith("out"):
                key = _eval(t.left.slice, env)
                want = _eval(t.comparators[0], env)
                raw.append((node.lineno, "assert_raw", (key, _float(want))))

    raw.sort(key=lambda x: x[0])
    events, sleeps, pending = [], [], None
    seen_action = False          # 首个动作/读取之前的 Wait 手工版惯例省略 → 两侧统一丢弃
    for item in raw:
        if item[1] == "call":
            events.append(("bench." + item[2], item[3]))
            seen_action = True
        elif item[1] == "sleep":
            if seen_action:
                sleeps.append(_float(item[2][0]) if item[2] else None)
        elif item[1] == "assert":
            events.append(("assert", item[2]))
            seen_action = True
        else:  # assert_raw:硬线→CAN 相邻两条合并成一对
            key, want = item[2]
            if pending is None:
                pending = {"hard": None, "can": None}
            if key in ("hard", "can"):
                pending[key] = want
            if pending["hard"] is not None and pending["can"] is not None:
                events.append(("assert", (pending["hard"], pending["can"])))
                pending = None
                seen_action = True
    return events, sleeps


def _float(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return float(v)
    return v


# ---------------------------------------------------------------- 主流程
def _load_functions(path):
    tree = ast.parse(open(path, encoding="utf-8").read())
    env = _module_env(tree)
    out = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            num = node.name[len("test_"):]
            if num.startswith("draft_"):
                num = num[len("draft_"):]
            num = num.split("_", 1)[0]
            if num.isdigit():
                out[num] = (node.name, _extract(node, env))
    return out


def compare(draft_path, manual_path):
    draft = _load_functions(draft_path)
    manual = _load_functions(manual_path)
    common = sorted(set(draft) & set(manual), key=int)
    results = []
    for num in common:
        d_name, (d_ev, d_sl) = draft[num]
        m_name, (m_ev, m_sl) = manual[num]
        same = d_ev == m_ev and d_sl == m_sl
        status = "MATCH" if same else ("KNOWN" if num in KNOWN_DEVIATIONS else "DIFF")
        results.append({"nn": num, "draft": d_name, "manual": m_name, "status": status,
                        "draft_events": d_ev, "manual_events": m_ev,
                        "draft_sleeps": d_sl, "manual_sleeps": m_sl,
                        "note": KNOWN_DEVIATIONS.get(num, "")})
    only_d = sorted(set(draft) - set(manual), key=int)
    only_m = sorted(set(manual) - set(draft), key=int)
    return results, only_d, only_m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("draft")
    ap.add_argument("manual")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--show", action="store_true", help="不一致时打印两侧轨迹")
    args = ap.parse_args()
    results, only_d, only_m = compare(args.draft, args.manual)
    counts = {"MATCH": 0, "KNOWN": 0, "DIFF": 0}
    for r in results:
        counts[r["status"]] += 1
    if args.json:
        print(json.dumps({"results": results, "only_draft": only_d, "only_manual": only_m},
                         ensure_ascii=False, indent=1))
    else:
        for r in results:
            mark = {"MATCH": "OK ", "KNOWN": "已知", "DIFF": "!! "}[r["status"]]
            print("[%s] %s (%s ↔ %s)%s" % (mark, r["nn"], r["draft"], r["manual"],
                                            ("  — " + r["note"]) if r["note"] else ""))
            if r["status"] == "DIFF" and args.show:
                print("      draft  ev:", r["draft_events"])
                print("      manual ev:", r["manual_events"])
                print("      draft  sl:", r["draft_sleeps"])
                print("      manual sl:", r["manual_sleeps"])
        print()
        if only_d:
            print("仅在草稿(未翻译/用户拍板 Skip):", ", ".join(only_d))
        if only_m:
            print("仅在手工版:", ", ".join(only_m))
        print("==== 配对 %d 对: MATCH %d / KNOWN %d / DIFF %d ====" %
              (len(results), counts["MATCH"], counts["KNOWN"], counts["DIFF"]))
    sys.exit(1 if counts["DIFF"] else 0)


if __name__ == "__main__":
    main()
