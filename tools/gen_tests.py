# -*- coding: utf-8 -*-
"""存量 dump JSON → pytest 用例草稿 + 通道常量草稿（P0-3 报告生成器）。

输入：tools/seq_dump.py 产出的结构化 dump JSON（如 reports/P2546_左后大屏加热_dump.json）。
输出（默认 reports/gen/<模块名>/，pytest 不收集，复核后人工迁入 tests/）：
    draft_all.py             **全部用例生成在同一个文件，顺序严格 = 输入 dump 的序列顺序**
                             （用户 2026-11-07 规则，便于与后续用例 Excel/mapping 对照排查）；
                             函数名 test_draft_<NN>，NN = dump 序号，与 manifest 一一对应
    gen_channels_draft.py    dump 里出现、channels.py 尚未覆盖的通道路径（下一个项目直接用）
    gen_manifest.md          dump序号/序列/函数/TODO/期望值 清单（对照表）

翻译规则（全部来自已闭环的实证，见 会话交接.md 机制速查）：
- 判定语义 EQ：实测 == Limits.Low，High 不参与（不是区间）→ assert 精确等值；
- 加热请求编码：1=OFF / 2/3/4=一/二/三档，0=无请求（保持）；
- 档位请求时序：写档位→1s→写0→1s 是库序列语义 → 检测到该 4 步模式时塌缩为
  bench.request_heat(level)，漏掉这 2s 会提前采样（欠压保护实测 3~6s 才切断）；
- LED 三项判定（高档/中档/低档 LED 硬线反馈）原文 174/174 全 Skip → 只留注释不生成 assert；
- DI1 写入 / Cyclic ECU 通道写入：存量已知缺陷 → 生成注释性 TODO，不生成写语句。

用法：
    python tools/gen_tests.py reports/P2546_左后大屏加热_dump.json            # 全部序列
    python tools/gen_tests.py <dump.json> --only "前提条件测试_过压,前提条件测试_整车碰撞"
    python tools/gen_tests.py <dump.json> -o reports/gen/预览

注意：草稿文件名不带 test_ 前缀（防误收集）；复核后重命名并迁入 tests/。
RunMode 不在 dump 里（当时用 interop 单独统计）：Skip 序列请用 --skip 指定，只登记进
manifest 不生成草稿。
"""
import argparse
import datetime
import json
import os
import re
import sys

# ---- 已知通道映射：dump 变量路径(后缀) → channels.py 常量 + 语义动作 ----
# kind: heat_req / crash / volt / eng / ntc_res / switch / fiu_ntc / fiu_out / raw / defect
VAR_MAP = {
    r"HU_DrvSeatHeat\Value":            ("CH_HU_HEAT_REQ", "heat_req"),
    r"srP_Msg1_20E_Msg\CrashInfo\Value": ("CH_CRASH", "crash"),
    r"PowerControl\VlotageControl\Value": ("CH_PWR_VOLT", "volt"),      # 原文拼写少了 e
    r"PowerControl\CurrentControl\Value": ("CH_PWR_CURR", "raw"),
    r"PowerControl\ON/OFF\Value":         ("CH_PWR_ON", "raw"),
    r"PowerControl\Power_Relay\Value":    ("CH_PWR_RELAY", "raw"),
    r"PowerControl\IGN\Value":            ("CH_IGN", "raw"),
    r"BCM_VehSt1_2AB_Msg\KeyState\Value": ("CH_KEY_STATE", "raw"),
    r"mrEMS_EngSt1_117_Msg\EngState\Value": ("CH_ENG_STATE", "eng"),
    r"MDLSignalRouting\RES2\Value":      ("CH_RES2", "ntc_res"),
    r"MDLSignalRouting\DO0\Value":       ("CH_DO0", "switch"),
    r"FIU3_OUT_Channel7\Value":          ("CH_FIU3_CH7", "fiu_ntc"),
    r"FIU3_OUT_Channel9\Value":          ("CH_FIU3_CH9", "fiu_ntc"),
    r"FIU1OUT_Channel1\Value":           ("CH_FIU1_CH1", "fiu_out"),
    r"FIU1OUT_Channel10\Value":          ("CH_FIU1_CH10", "fiu_out"),
    # 已知存量缺陷：写 DI 通道（原文误写 DI1，应读 DI0）；写 Cyclic ECU 通道会被软 ECU 周期覆盖
    r"Digital Input\port0\DI1":          (None, "defect_di"),
    r"ECU\Incoming\Single-Point":        (None, "defect_can"),
}

HEAT_REQ_NAMES = {1.0: "off", 2.0: "level1", 3.0: "level2", 4.0: "level3"}
ENG_NAMES = {0.0: "not_running", 1.0: "running", 2.0: "crank", 3.0: "fault"}
NTC_FAULT_NAMES = {8.0: "open", 12.0: "short_vcc", 14.0: "short_gnd"}
OUT_FAULT_NAMES = {1.0: "short_gnd", 2.0: "open"}

# ---- 库序列（后排加热测试用例.seq）→ stimulus 方法 ----
LIBSEQ_MAP = {
    "测试用例初始化": "# conftest 的 bench fixture 已覆盖（连接复用/锁/工况初始化）",
    "测试用例结束":   "# teardown: bench_shutdown 已在 fixture 里（含撤加热增量）",
    "加热OFF":       "bench.request_heat('off')      # 写1→1s→写0，共 2s",
    "加热一档请求":   "bench.request_heat('level1')   # 库序列含 2s 内部等待",
    "加热二档请求":   "bench.request_heat('level2')   # 库序列含 2s 内部等待",
    "加热三档请求":   "bench.request_heat('level3')   # 库序列含 2s 内部等待",
    "加热开关按下":   "bench.heat_switch(True)",
}

# 同文件子序列（SFPath=''）特殊处理；其余视为 MainSequence 编排调用，不展开
SAMEFILE_MAP = {
    "加热输出状态和LED灯信号采集": "out = bench.read_heat_outputs()",
}

# 限值步骤名 → 输出键（EQ 语义：期望值 = Limits.Low）
LIMIT_MAP = {
    "加热状态硬线信号反馈": "hard",
    "加热状态CAN信号反馈": "can",
}
LED_STEP_RE = re.compile(r"加热(高|中|低)档LED硬线信号反馈")

HELPERS = {"MainSequence", "*Library*", "加热OFF", "加热一档请求", "加热二档请求",
           "加热三档请求", "加热开关按下", "加热输出状态和LED灯信号采集",
           "测试用例初始化", "测试用例结束"}


def to_num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def match_var(path):
    """dump 变量全路径 → (常量名, 语义 kind)；未映射返回 (None, None)"""
    for suffix, (const, kind) in VAR_MAP.items():
        if path.endswith(suffix.replace("/", "\\")) or suffix in path:
            return const, kind
    return None, None


class Draft:
    def __init__(self, seq_name, seq_idx):
        self.name = seq_name
        self.idx = seq_idx
        self.func = f"test_draft_{seq_idx:02d}"   # 序号=dump 序列号，与输入顺序一一对应
        self.body = []          # (step_label, [code lines])
        self.todos = 0
        self.expects = []       # (输出键, 期望值) 摘要用

    def add(self, label, lines):
        self.body.append((label, lines))

    def todo(self, lines):
        self.todos += 1
        self.add("TODO", lines)


def translate_setvar(step, draft):
    name = str(step["name"])
    variables = [v for v in (step["props"].get("Variables") or [])
                 if isinstance(v, dict) and v.get("VariableName")]

    def path_of(v):
        return str(v["VariableName"]).replace("/", "\\")

    def val_of(v):
        return to_num(v.get("VariableValue"))

    # ---- FIU1 加热输出故障：CH10 与 CH1 必须按"配合对"整体翻译 ----
    # 短地 = CH10=2 + CH1=1（两条写在同一步或分步）；开路 = CH1=2；取消 = 全 0
    fiu_ch10 = next((v for v in variables if "FIU1OUT_Channel10" in path_of(v)), None)
    fiu_ch1 = next((v for v in variables if "FIU1OUT_Channel1\\" in path_of(v)
                    or path_of(v).endswith("FIU1OUT_Channel1\\Value")), None)
    if fiu_ch1 is not None or fiu_ch10 is not None:
        ch1v, ch10v = (val_of(fiu_ch1) if fiu_ch1 else None), (val_of(fiu_ch10) if fiu_ch10 else None)
        if ch10v == 2.0 or ch1v == 1.0:
            src = "CH10=2 + CH1=1" if (ch10v == 2.0 and ch1v == 1.0) else f"CH1={ch1v:g}" + (f" + CH10={ch10v:g}" if ch10v is not None else "")
            draft.add(name, [f"bench.inject_out_fault('short_gnd')   # {src}（短地配合对，stimulus 一并写 CH10/CH1）"])
        elif ch1v == 2.0:
            draft.add(name, ["bench.inject_out_fault('open')   # CH1=2"])
        elif (ch1v == 0.0 and ch10v in (0.0, None)) or (ch1v is None and ch10v == 0.0):
            draft.add(name, ["bench.clear_out_fault()   # 清 CH1+CH10（原文只清 CH1，CH10 泄漏是存量缺陷）"])
        else:
            draft.todo([f"# TODO 未知 FIU1 组合: CH1={ch1v} CH10={ch10v}"])
        # 该步其余变量照常翻译，FIU1 两条已处理
        variables = [v for v in variables if v is not fiu_ch1 and v is not fiu_ch10]

    # ---- 电源模式：KeyState 与 IGN 常同步骤成对写 → set_power_mode ----
    ks = next((v for v in variables if "KeyState" in path_of(v)), None)
    ign = next((v for v in variables if path_of(v).endswith(r"IGN\Value")), None)
    if ks is not None and ign is not None:
        ksv, ignv = val_of(ks), val_of(ign)
        draft.add(name, [f"bench.set_power_mode({ksv:g}, {bool(ignv)})   # KeyState={ksv:g} + IGN={ignv:g}"
                         f"（原文一步成对写）"])
        variables = [v for v in variables if v is not ks and v is not ign]

    for v in variables:
        path = path_of(v)
        val = val_of(v)
        const, kind = match_var(path)
        if kind is None:
            draft.todo([f"# TODO 未映射通道（见 gen_channels_draft.py）: {path} = {v.get('VariableValue')}"])
            continue
        if kind == "heat_req":
            if val == 0.0:
                draft.add(name, ["bench.no_heat_request()   # 写 0：无请求，DUT 保持当前状态"])
            else:
                lvl = HEAT_REQ_NAMES.get(val)
                draft.add(name, [f"bench.set_heat_request('{lvl}')   # 写 {v.get('VariableValue')}"
                                 + ("（后续 1s→写0→1s 若出现，应塌缩为 request_heat）" if lvl else "")])
        elif kind == "crash":
            draft.add(name, [f"bench.set_crash({'True' if val else 'False'})   # 写 {v.get('VariableValue')}"])
        elif kind == "volt":
            note = ""
            # 标签残留检测：步骤名里的数字与实际写入值不符（如"设置程控电源8V"实际写 17）
            m = re.search(r"\d+(?:\.\d+)?", name)
            if m and abs(float(m.group()) - val) > 1e-9:
                note = f"   # 注意: 步骤名「{name}」与实际写入 {v.get('VariableValue')} 不符（存量标签残留，以写入值为准）"
            draft.add(name, [f"bench.set_supply_voltage({val:g})   # 程控电源电压{note}"])
        elif kind == "eng":
            st = ENG_NAMES.get(val, "?")
            draft.add(name, [f"bench.set_engine_state('{st}')   # 写 {v.get('VariableValue')}"])
        elif kind == "ntc_res":
            draft.add(name, [f"bench.set_ntc_resistance({val:g})   # NTC 阻值(Ω)"])
        elif kind == "switch":
            draft.add(name, [f"bench.heat_switch({bool(val)})   # DO0 写 {v.get('VariableValue')}"])
        elif kind == "fiu_ntc":
            ch = "ch7" if "Channel7" in path else "ch9"
            fault = NTC_FAULT_NAMES.get(val)
            if fault:
                draft.add(name, [f"bench.inject_ntc_fault('{fault}', '{ch}')   # 写 {v.get('VariableValue')}"])
            elif val == 0.0:
                draft.add(name, [f"bench.clear_ntc_fault('{ch}')   # 清零"])
            else:
                draft.todo([f"# TODO 未知 FIU3 值: {const} = {v.get('VariableValue')}（NTC_FAULT 无此档）"])
        elif kind == "fiu_out":
            # 单独出现（未成对）时兜底；正常路径已在函数开头按配合对整体处理
            draft.todo([f"# TODO FIU1 单通道写入未配对: {const} = {v.get('VariableValue')}"])
        elif kind in ("raw",):
            if const == "CH_KEY_STATE":
                draft.todo([f"# TODO 电源模式: bench.set_power_mode(key_state={v.get('VariableValue')}, ign_valid=?)"
                            f"  # 原文写 KeyState={v.get('VariableValue')}（IGN 通常同步写 1）"])
            elif const == "CH_IGN":
                draft.todo([f"# TODO 点火: 原文写 IGN={v.get('VariableValue')}（多与 KeyState 同步，见 set_power_mode）"])
            else:
                draft.todo([f"# TODO 直接写（bench 无封装方法）: ch.set({const}, {v.get('VariableValue')})"])
        elif kind == "defect_di":
            draft.todo([f"# 存量缺陷: 原文写 DI1（恒 0）；有效采集是读 DI0（CH_HEAT_OUT_HARD），勿翻译成写"])
        elif kind == "defect_can":
            draft.todo(["# 存量缺陷: 原文写 Cyclic ECU 通道（会被模型软 ECU 周期覆盖），勿翻译成写"])


def translate_wait(step, draft):
    secs = to_num(step["props"].get("TimeExpr"))
    if secs is None:
        draft.todo([f"# TODO Wait 时序非数值: TimeExpr={step['props'].get('TimeExpr')!r}"])
    else:
        draft.add("Wait", [f"time.sleep({secs:g})"])


def translate_call(step, draft):
    sd = step["props"].get("TS", {}).get("SData") or {}
    seq_name = str(sd.get("SeqName") or step["name"])
    sfpath = str(sd.get("SFPath") or "")
    name = str(step["name"])
    if sfpath:  # 库文件序列
        if seq_name in LIBSEQ_MAP:
            line = LIBSEQ_MAP[seq_name]
            draft.add(name, [line] if not line.startswith("#") else [f"{line}（生成器注释，非代码）"])
        else:
            draft.todo([f"# TODO 未知库序列调用: {sfpath} :: {seq_name}"])
    else:       # 同文件子序列
        if seq_name in SAMEFILE_MAP:
            draft.add(name, [SAMEFILE_MAP[seq_name]])
        else:
            draft.todo([f"# TODO 同文件子序列调用（多为 MainSequence 编排）: {seq_name}"])


def translate_limit(step, draft):
    name = str(step["name"])
    props = step["props"]
    low = to_num((props.get("Limits") or {}).get("Low"))
    comp = props.get("Comp")
    key = LIMIT_MAP.get(name)
    if key:
        draft.expects.append((key, low))
        note = "EQ 语义：实测 == Limits.Low" + (f"（Comp={comp}）" if comp and comp != "EQ" else "")
        draft.add(name, [f'assert out["{key}"] == {low:g}   # {note}'])
    elif LED_STEP_RE.search(name):
        draft.add(name, [f"# 原文 Skip（174/174 全跳）→ LED 判定不翻译，如需启用人工补：期望 Low={low:g}"])
    else:
        high = (props.get("Limits") or {}).get("High")
        draft.todo([f"# TODO 未归类限值步骤 {name}: Low={low} High={high} Comp={comp}"])


def gen_sequence(seq, idx, dump_file):
    draft = Draft(seq["name"], idx)
    steps_flat = []
    for g in ("Setup", "Main", "Cleanup"):
        for st in seq["groups"].get(g, []):
            steps_flat.append((g, st))

    i = 0
    while i < len(steps_flat):
        g, st = steps_flat[i]
        props = st["props"]
        name = str(st["name"])

        if props.get("NI_StepTypeName") == "NI_SetVariableValues":
            translate_setvar(st, draft)
        elif name == "Wait":
            translate_wait(st, draft)
        elif isinstance(props.get("TS", {}).get("SData"), dict) and props["TS"]["SData"].get("SeqName"):
            translate_call(st, draft)
        elif "Limits" in props:
            translate_limit(st, draft)
        else:
            tn = props.get("NI_StepTypeName") or ""
            if tn in ("NI_OpenVeriStandProject", "NI_FrameworkCreate", "NI_FrameworkCleanUp", "For", "End"):
                draft.add(name, [f"# 框架步骤（{tn}），pytest 体系由 conftest 承担，不翻译"])
            elif tn == "NI_GetVariableValues":
                draft.add(name, ["out = bench.read_heat_outputs()   # NI_GetVariableValues（有效读数 2 路）"])
            else:
                draft.todo([f"# TODO 未识别步骤类型: {name} (NI_StepTypeName={tn!r})"])
        i += 1
    return draft


def render_function(draft, module_label):
    """单条序列 → 一个测试函数（无模块头；由 main 拼进单一文件）"""
    lines = []
    a = lines.append
    a(f'# ----- dump 序列 {draft.idx}: {draft.name} -----')
    a("@allure.epic(\"P2546 HIL 测试\")")
    a(f"@allure.feature(\"{module_label}\")")
    a(f"@allure.title(\"{draft.name}\")")
    a(f"def {draft.func}(bench):")
    a(f'    """{draft.name}（dump 序号 {draft.idx}）：原文 Setup/Main/Cleanup 逐步翻译"""')
    for label, code in draft.body:
        if label == "TODO":
            for c in code:
                a(f"    {c}")
            a("")
        elif all(c.lstrip().startswith("#") or not c.strip() for c in code):
            # 纯注释步骤（初始化/结束/LED Skip 等）：不生成 with 块（空块是语法错误）
            a(f"    # [{label}]")
            for c in code:
                a(f"    {c}")
        else:
            a(f'    with allure.step("{label}"):')
            for c in code:
                a(f"        {c}")
    if not draft.body:
        a("    pass   # 空序列")
    return "\n".join(lines) + "\n\n\n", draft.todos


def render_module(parts, dump_file, module_label, n_gen):
    """全部用例拼成单一文件：顺序 = dump 序列顺序（用户规则，便于与用例 Excel/mapping 对照）"""
    lines = []
    a = lines.append
    a('# -*- coding: utf-8 -*-')
    a(f'"""【草稿·未复核】{module_label} 全部用例 —— tools/gen_tests.py 自动生成')
    a("")
    a(f"来源: {dump_file}；生成: {datetime.date.today().isoformat()}；共 {n_gen} 条")
    a("")
    a("**顺序规则（用户 2026-11-07 拍板）：用例严格按输入 dump 的序列顺序生成在同一文件，")
    a("函数名后缀 = dump 序号，与 gen_manifest.md 一一对应——后续用例 Excel/mapping 按此对照排查。**")
    a("")
    a("复核要点（生成器已按实证语义处理，仍需人工确认）:")
    a("  1. 判定为 EQ 精确等值（实测 == Limits.Low），High 不参与；")
    a("  2. request_heat 含 2s 内部等待，勿再补 sleep；")
    a("  3. TODO 项是语义未定/存量缺陷，逐条拍板后删除标记；")
    a("  4. 复核通过后：文件重命名为 test_*.py 迁入 tests/（函数名建议保留序号前缀）。")
    a('"""')
    a("import time")
    a("")
    a("import allure")
    a("import pytest")
    a("")
    a("pytestmark = pytest.mark.hil")
    a("")
    a("")
    return "\n".join(lines) + "".join(parts)


def main():
    ap = argparse.ArgumentParser(description="dump JSON → pytest 草稿")
    ap.add_argument("dump")
    ap.add_argument("-o", "--out", help="输出目录（默认 reports/gen/<dump名>/）")
    ap.add_argument("--only", help="只生成指定序列（逗号分隔）")
    ap.add_argument("--skip", help="跳过指定序列（逗号分隔，登记进 manifest）")
    args = ap.parse_args()

    dump_file = os.path.abspath(args.dump)
    d = json.load(open(dump_file, encoding="utf-8"))
    base = os.path.splitext(os.path.basename(dump_file))[0].replace("_dump", "")
    outdir = args.out or os.path.join("reports", "gen", base)
    os.makedirs(outdir, exist_ok=True)
    module_label = re.sub(r"^P\d+_", "", base)   # P2546_左后大屏加热 → 左后大屏加热

    only = set(filter(None, (args.only or "").split(",")))
    skip = set(filter(None, (args.skip or "").split(",")))

    known_paths = set()
    for suffix in VAR_MAP:
        known_paths.add(suffix)

    manifest = ["| dump序号 | 序列 | 函数 | TODO | 期望值 |", "|---|---|---|---|---|"]
    unmapped = {}
    parts = []
    n_gen = 0
    for idx, seq in enumerate(d["sequences"]):
        name = seq["name"]
        if only and name not in only:
            continue
        if name in skip:
            manifest.append(f"| {idx} | {name} | （--skip 跳过） | - | - |")
            continue
        if name in HELPERS and not only:
            manifest.append(f"| {idx} | {name} | （编排/公共子序列，不生成） | - | - |")
            continue

        # 收集未映射路径
        for gsteps in seq["groups"].values():
            for st in gsteps:
                for v in st["props"].get("Variables") or []:
                    if isinstance(v, dict) and v.get("VariableName"):
                        c, k = match_var(str(v["VariableName"]))
                        if k is None:
                            unmapped.setdefault(str(v["VariableName"]), set()).add(str(v.get("VariableValue")))

        draft = gen_sequence(seq, idx, dump_file)
        fn_text, todos = render_function(draft, module_label)
        parts.append(fn_text)
        exp = ", ".join(f"{k}=={v:g}" for k, v in draft.expects) or "-"
        manifest.append(f"| {idx} | {name} | {draft.func} | {todos} | {exp} |")
        n_gen += 1

    # 单一文件：顺序 = 输入 dump 顺序（用户规则，Excel/mapping 对照）
    all_file = os.path.join(outdir, "draft_all.py")
    with open(all_file, "w", encoding="utf-8") as f:
        f.write(render_module(parts, os.path.basename(dump_file), module_label, n_gen))

    # 未映射通道 → 常量草稿
    if unmapped:
        with open(os.path.join(outdir, "gen_channels_draft.py"), "w", encoding="utf-8") as f:
            f.write('# -*- coding: utf-8 -*-\n"""dump 中出现、channels.py 未覆盖的通道路径(自动生成)\n')
            f.write('复核后迁入 projects/<proj>/common/channels.py。\n"""\n')
            for i, (p, vals) in enumerate(sorted(unmapped.items()), 1):
                f.write(f'GEN_CH_{i} = r"{p}"   # 见过值: {sorted(vals)}\n')

    with open(os.path.join(outdir, "gen_manifest.md"), "w", encoding="utf-8") as f:
        f.write(f"# 生成清单 —— {base}（{datetime.date.today().isoformat()}）\n\n")
        f.write(f"来源: {os.path.basename(dump_file)}；生成 {n_gen} 条草稿 → {outdir}\n\n")
        f.write("\n".join(manifest) + "\n")
        if unmapped:
            f.write(f"\n未映射通道 {len(unmapped)} 条 → gen_channels_draft.py\n")

    print(f"[done] {n_gen} 条用例（单一文件,按输入顺序） -> {all_file}")
    print(f"[done] manifest: {os.path.join(outdir, 'gen_manifest.md')}")
    if unmapped:
        print(f"[warn] 未映射通道 {len(unmapped)} 条（见 gen_channels_draft.py）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
