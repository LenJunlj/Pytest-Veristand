# -*- coding: utf-8 -*-
"""report_meta.py —— Allure 报告的三份治理元数据（写进 results 再 generate）

    categories.json   失败自动归类：台架/环境异常、原文期望与时序边界、其他
    environment.xml   报告 Environment 面板：台架机、sdf、DUT 口、依赖版本、git commit
    executor.json     报告头部的 Build 信息 + 指回报告中心的链接

为什么用 environment.xml 而不是 environment.properties：
    properties 走 Java Properties 编码（ISO-8859-1），中文 sdf 路径会乱码；
    environment.xml 是 UTF-8，路径里带「C206-10项目/Veristand项目」也不会有问题。

设计原则：**只描述事实，不改变判定**。分类只是让一片红里能分出"环境问题/待裁定的期望
偏差"，用例本身是 pass 还是 fail 完全不受影响。
"""
import json
import os
import platform
import socket
import sys
from xml.sax.saxutils import escape

# 分类顺序有意义：Allure 从上往下匹配，第一个命中的生效，所以兜底的放最后。
# messageRegex 只匹配置信度高的特征串（连接类异常、断言文本），宁缺毋滥。
CATEGORIES = [
    {
        "name": "台架/环境异常",
        "matchedStatuses": ["broken", "failed"],
        "messageRegex": ".*(PcanCan|PCAN|VeriStand|VeriStandError|attach|3090|"
                        "Connection|Timeout|timeout|NS_ERROR).*",
    },
    {
        "name": "原文期望/时序边界（登记表核对，勿直接改用例）",
        "matchedStatuses": ["failed"],
        # 本项目 EQ 断言与 DTC 断言的全部失败文案；遇到真实的档位/灯逻辑错误同样落在
        # 这里，所以名字写"核对"，由人对照 docs 的已知偏差登记判断，不做自动背书。
        "messageRegex": ".*(硬线输出|实测 '.*' != 期望|实测 .* != 期望|DTC 检测).*",
    },
    {
        "name": "其他失败",
        "matchedStatuses": ["failed", "broken"],
    },
]


def categories():
    """返回 categories.json 内容（每次覆盖写，保证分类规则随代码走）。"""
    return list(CATEGORIES)


def _pkg_version(mod_name):
    try:
        mod = __import__(mod_name)
        return str(getattr(mod, "__version__", "") or "")
    except Exception:
        return ""


def collect_environment(repo_root, project, extra=None):
    """收集 Environment 面板要显示的事实（全部来自本机，不碰台架）。

    project.yaml 的 veristand 段能拿到 sdf 路径与 DUT 所在 CAN 口 —— 报告离开这台机器后，
    这两项是唯一能说明"这份结果跑的是什么工程"的信息。
    """
    from helpers import report_history as rh

    env = {
        "Project": project,
        "ProjectName": rh.project_name(repo_root, project),
        "Host": socket.gethostname(),
        "User": os.environ.get("USERNAME") or os.environ.get("USER") or "",
        "OS": "%s %s" % (platform.system(), platform.release()),
        "Python": "%s (%s)" % (platform.python_version(), os.path.basename(sys.executable)),
        "pytest": _pkg_version("pytest"),
        "allure-pytest": _pkg_version("allure_pytest"),
        "niveristand": _pkg_version("niveristand"),
        "GitCommit": rh._git_head(repo_root),
        "ReportCenter": rh.public_url(repo_root) or "-",
    }
    try:
        import yaml
        yml = os.path.join(repo_root, "projects", project, "project.yaml")
        if os.path.isfile(yml):
            with open(yml, "r", encoding="utf-8") as f:
                doc = yaml.safe_load(f) or {}
            vs = doc.get("veristand") or {}
            for key, label in (("system_definition", "SDF"),
                               ("model_target", "ModelTarget")):
                if vs.get(key):
                    env[label] = str(vs[key])
    except Exception:
        pass
    env.update({str(k): str(v) for k, v in (extra or {}).items()})
    return env


def write_environment(results_dir, env):
    """写 environment.xml（Allure 的 UTF-8 版本，中文路径安全）。"""
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<environment>"]
    for k in sorted(env):
        lines.append("  <parameter>")
        lines.append("    <key>%s</key>" % escape(str(k)))
        lines.append("    <value>%s</value>" % escape(str(env[k])))
        lines.append("  </parameter>")
    lines.append("</environment>")
    path = os.path.join(results_dir, "environment.xml")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return path


def write_categories(results_dir):
    path = os.path.join(results_dir, "categories.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(categories(), f, ensure_ascii=False, indent=2)
    return path


def write_executor(results_dir, project, version, repo_root, report_name=None):
    """写 executor.json —— 报告头部会出现 Build 号，并链回报告中心的这个版本。

    没有 public_url 时退化成只写报告名，不编造 localhost 链接（别人点开是自己的机器）。
    """
    base = os.path.basename(project) if project else "report"
    ex = {
        "name": "Pytest-Veristand",
        "type": "pytest",
        "reportName": report_name or "%s %s" % (project, version),
        "buildName": version,
    }
    url = ""
    try:
        from helpers import report_history as rh
        url = rh.public_url(repo_root)
    except Exception:
        url = ""
    if url:
        ex["url"] = url
        ex["buildUrl"] = "%s/r/%s/%s/" % (url, project, version)
    path = os.path.join(results_dir, "executor.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(ex, f, ensure_ascii=False, indent=2)
    return path


def write_results_meta(repo_root, results_dir, project, version, extra=None):
    """一次性写三份元数据，返回写出的路径列表（失败只抛给调用方决定吞还是报）。"""
    out = [write_categories(results_dir)]
    out.append(write_environment(results_dir,
                                 collect_environment(repo_root, project, extra=extra)))
    out.append(write_executor(results_dir, project, version, repo_root))
    return out
