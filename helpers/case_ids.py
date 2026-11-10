# -*- coding: utf-8 -*-
"""case_ids.py —— 用例编号 → Allure 标签（v3 §4 的追溯外键），**不改任何用例文件**

dump 序号已经编在函数名里（test_22_exit_ntc_open），conftest 在收集阶段解析出来挂标签：

    testcase = c206_10#22      报告里显示为用例编号，可与台账/Excel/Allure 三方对照
    tag      = seq:22          报告里是可见的筛选项（点一下只留这一条）
    tag      = module:dtc      区分同项目下的模块

为什么不写进用例文件：用例函数是 .seq 的忠实翻译，加装饰器会让"逐字对照原文"多出噪声；
标签是报告层的事，由框架统一挂载，用例文件保持零改动（也避免 68 处重复）。
"""
import re

_SEQ_RE = re.compile(r"^test_(\d+)_")


def parse_seq(func_name):
    """从 test_<NN>_xxx 取 dump 序号；不符合命名规则（框架级用例）返回 None。"""
    m = _SEQ_RE.match(func_name or "")
    return int(m.group(1)) if m else None


def case_labels(project, seq, module=None):
    """返回 [(label_type, value)]；seq 为 None 时返回空列表（不挂任何标签）。"""
    if seq is None:
        return []
    out = [("testcase", "%s#%02d" % (project, seq)), ("tag", "seq:%02d" % seq)]
    if module:
        out.append(("tag", "module:%s" % module))
    return out
