# -*- coding: utf-8 -*-
"""report_history.py —— 报告版本管理：每次 pytest 运行留档，可按版本回看与导出

**为什么需要**：pytest 每次运行前会清空 allure-results、结束时 `allure generate --clean`
重写 allure-report，junit.xml 也是单文件覆盖 —— 即上一轮的历史是被**删除**，不只是被覆盖。
本模块在会话结束时把这一轮的原始数据整份拷进仓库外挂的历史目录，从此每轮都留得下来。

目录布局（`report.history.dir`，默认 reports/report_history，已在 .gitignore 内）：

    reports/report_history/
        deleted.log                        # 删除审计（时间/项目/版本/释放字节）
        <project>/<YYYYmmdd-HHMMSS>/
            results/                       # allure-results 副本（事实源，约 1MB/次）
            junit.xml                      # 本次 junit 副本（约 27KB）
            meta.json                      # 版本元数据（含 counts / kind / git）
            report/                        # 按需生成的 Allure 站点（缓存，可再生）

**两类运行分开计数**（kind 由 argv 判定，见 classify_kind）：
    full  —— 全量/按目录跑，每项目保留 keep=50 份（不可再生的历史本体）
    debug —— 带 `::nodeid` / `-k` / `--lf` 的调试跑，单独保留 debug_keep=5 份
调试运行单独成桶，是为了不把 50 份名额挤满（调试一天能跑几十次，全是半截运行）。

**缓存与数据的边界（重要）**：
    report/ 只是用 allure CLI 从 results/ 现渲染出来的网页，删了随时能重建（3~5 秒）；
    results/ 与 junit.xml 是唯一事实源，任何裁剪路径都不会碰它们。

本模块不 import pytest，也不依赖台架，全部函数以 repo_root 参数定位目录，便于单测。
"""
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import zipfile
from datetime import datetime

import yaml

# 版本号 = 运行开始时刻（本地时间），形如 20261109-180703；撞秒时追加 -2/-3
_VER_RE = re.compile(r"^\d{8}-\d{6}(-\d+)?$")
# 项目号白名单：与目录名一致（projects/<id>/），拒绝路径分隔符与 ..
_PROJECT_RE = re.compile(r"^[A-Za-z0-9_]{1,40}$")

# 判定为"调试运行"的命令行特征（argv 里出现即算）
_DEBUG_FLAGS = ("-k", "--lf", "--last-failed", "--ff", "--failed-first",
                "--sw", "--stepwise", "--co", "--collect-only")

# 渲染任务的进程内互斥：同一时刻只让一个版本调用 Java，
# 也用于删除接口对"正在生成"的版本返回 409 而不是硬删
_GEN_LOCK = threading.Lock()

DEFAULT_CFG = {
    "enabled": True,
    "dir": "reports/report_history",
    "keep": 50,
    "debug_keep": 5,
    "max_generated": 3,
}


class ReportError(Exception):
    """报告操作的业务异常（服务层据此回 4xx/5xx）。"""


class ReportBusy(ReportError):
    """正在生成报告，拒绝删除。"""


# ---------------------------------------------------------------- 配置 / 项目

def load_cfg(repo_root):
    """读 bench.yaml 的 report.history 段；缺项用 DEFAULT_CFG 补齐。"""
    cfg = dict(DEFAULT_CFG)
    try:
        with open(os.path.join(repo_root, "config", "bench.yaml"), "r", encoding="utf-8") as f:
            doc = (yaml.safe_load(f) or {}).get("report", {}) or {}
        cfg.update(doc.get("history") or {})
    except Exception:
        pass
    return cfg


def _allure_cfg(repo_root):
    """读 bench.yaml 的 report.allure 段（生成历史版本报告要用的 CLI 与 Java 路径）。"""
    try:
        with open(os.path.join(repo_root, "config", "bench.yaml"), "r", encoding="utf-8") as f:
            return ((yaml.safe_load(f) or {}).get("report", {}) or {}).get("allure", {}) or {}
    except Exception:
        return {}


def report_cfg(repo_root):
    """读 bench.yaml 的 report 段（public_url / notify 等跨功能配置）。

    与 load_cfg 的区别：load_cfg 只取 report.history（归档行为），这里取整个 report。
    """
    try:
        with open(os.path.join(repo_root, "config", "bench.yaml"), "r", encoding="utf-8") as f:
            return (yaml.safe_load(f) or {}).get("report", {}) or {}
    except Exception:
        return {}


def public_url(repo_root):
    """报告中心的局域网入口（末尾不带斜杠）；未配置时返回空串。

    用在 executor.json 的 Build 链接和通知消息里 —— 报告里的链接必须指回**这台机器**，
    不能写成 localhost（别人点开就是自己的机器）。
    """
    return str((report_cfg(repo_root) or {}).get("public_url") or "").rstrip("/")


def history_root(repo_root, cfg=None):
    cfg = cfg or load_cfg(repo_root)
    d = cfg.get("dir") or DEFAULT_CFG["dir"]
    return d if os.path.isabs(d) else os.path.join(repo_root, d)


def discover_projects(repo_root):
    """扫 projects/*/project.yaml，返回 [{id, name, modules}]（按目录名排序）。

    id 一律取**目录名**：归档目录、URL 路径都用它，避免 project.yaml 里的 id
    与目录名不一致时出现两个桶。name 取 yaml 的正式名，仅用于展示。
    """
    out = []
    proj_root = os.path.join(repo_root, "projects")
    if not os.path.isdir(proj_root):
        return out
    for name in sorted(os.listdir(proj_root)):
        yml = os.path.join(proj_root, name, "project.yaml")
        if not os.path.isfile(yml):
            continue
        try:
            with open(yml, "r", encoding="utf-8") as f:
                doc = yaml.safe_load(f) or {}
        except Exception:
            doc = {}
        out.append({
            "id": name,
            "name": doc.get("name") or name,
            # 模块带 name：页面上的运行按钮要让用户勾"左后三排加热"而不是 left_rear_heating
            "modules": [{"id": m.get("id"), "name": m.get("name") or m.get("id")}
                        for m in (doc.get("modules") or []) if m.get("id")],
        })
    return out


def project_name(repo_root, project):
    """展示名：project.yaml 的 name，框架级 tests/ 记「框架单元测试」。"""
    for p in discover_projects(repo_root):
        if p["id"] == project:
            return p["name"]
    return "框架单元测试" if project == "framework" else project


# ---------------------------------------------------------------- 归档

def classify_kind(argv):
    """由命令行判定 full / debug：出现 `::nodeid`、`-k`、`--lf` 等即为调试运行。"""
    for a in (argv or []):
        if "::" in str(a):
            return "debug"
        s = str(a)
        if s in _DEBUG_FLAGS or s.startswith("-k"):
            return "debug"
    return "full"


def _version_stamp(now):
    return now.strftime("%Y%m%d-%H%M%S")


def version_dir(repo_root, project, version, cfg=None):
    return os.path.join(history_root(repo_root, cfg), project, version)


# ---------------------------------------------------------------- 跨轮趋势账本
# Allure 2 的趋势不是服务端存的，而是靠**上一份报告的 history/ 目录**续上：
# generate 时若 results/history 存在，就把 history-trend / retries-trend 等并进去，
# 新报告的 Trends / History / Retries 三页才有数据。
#
# 我们的链：本轮 results ←(灌)← 账本 ←(收)← 本轮 report/history
# 账本放在 <报告历史根>/<项目>/_history（下划线前缀，_VER_RE 不会把它当版本）。

def history_ledger(repo_root, project, cfg=None):
    return os.path.join(history_root(repo_root, cfg), project, "_history")


def seed_history(repo_root, project, results_dir, cfg=None):
    """把账本灌进本轮 results/history。返回复制的文件数（0 = 首轮，没有可续的历史）。"""
    led = history_ledger(repo_root, project, cfg)
    if not os.path.isdir(led):
        return 0
    dst = os.path.join(results_dir, "history")
    os.makedirs(dst, exist_ok=True)
    n = 0
    for name in os.listdir(led):
        src = os.path.join(led, name)
        if not os.path.isfile(src):
            continue
        try:
            shutil.copy2(src, os.path.join(dst, name))
            n += 1
        except OSError:
            pass
    return n


def harvest_history(repo_root, project, report_dir, cfg=None):
    """把 generate 出来的 report/history 收回账本（账本唯一写入口）。返回文件数。"""
    src = os.path.join(report_dir, "history")
    if not os.path.isdir(src):
        return 0
    led = history_ledger(repo_root, project, cfg)
    os.makedirs(led, exist_ok=True)
    n = 0
    for name in os.listdir(src):
        p = os.path.join(src, name)
        if not os.path.isfile(p):
            continue
        try:
            shutil.copy2(p, os.path.join(led, name))
            n += 1
        except OSError:
            pass
    return n


def sync_history_into(repo_root, project, results_dir, cfg=None):
    """把账本同步进某个 results 副本（归档版本用，让该版本单独渲染时也带趋势）。"""
    return seed_history(repo_root, project, results_dir, cfg)


def dir_size(path):
    total = 0
    for dp, _dns, fns in os.walk(path):
        for f in fns:
            try:
                total += os.path.getsize(os.path.join(dp, f))
            except OSError:
                pass
    return total


def _counts_from_junit(junit_path):
    """复用 make_report 的解析，避免两套 junit 读取逻辑。失败返回 None。"""
    try:
        from tools.make_report import parse_junit
        r = parse_junit(junit_path)
    except Exception:
        return None
    passed = sum(1 for c in r["cases"] if c["status"] == "Passed")
    return {
        "total": len(r["cases"]) or r["total"],
        "passed": passed,
        "failed": r["failures"],
        "error": r["errors"],
        "skipped": r["skips"],
        "duration_s": round(r["time"], 3),
    }


def _git_head(repo_root):
    try:
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=repo_root,
                           capture_output=True, text=True, timeout=5)
        return (r.stdout or "").strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def archive_session(repo_root, project, results_dir, junit_path=None,
                    started_at=None, exit_status=0, argv=None, cfg=None,
                    now=None, extra=None, version=None):
    """把一次运行的 allure-results / junit.xml / meta 归档成一个版本。

    version：报告生成阶段算好的版本号（executor.json 的 Build 链接要指到它），
    不传则按 now 现算 —— 两边必须一致，否则报告里的链接会指向不存在的版本。

    返回 meta dict；不需要归档（未启用、看不到结果、已被 --no-allure 关掉）时返回 None。
    归档失败抛异常（由调用方决定是否吞掉——conftest 里是吞掉，绝不影响用例结果）。
    """
    cfg = cfg or load_cfg(repo_root)
    if cfg.get("enabled", True) is False:
        return None
    if not (os.path.isdir(results_dir)
            and any(f.endswith(".json") for f in os.listdir(results_dir))):
        return None

    now = now or datetime.now()
    version = version or _version_stamp(now)
    dest = version_dir(repo_root, project, version, cfg)
    if os.path.exists(dest):                     # 同一秒跑两次：追加序号，绝不覆盖
        i = 2
        while os.path.exists("%s-%d" % (dest, i)):
            i += 1
        version, dest = "%s-%d" % (version, i), "%s-%d" % (dest, i)
    os.makedirs(dest, exist_ok=True)

    # results 是唯一事实源：整份拷走，之后 junit 覆盖/清空都与它无关
    shutil.copytree(results_dir, os.path.join(dest, "results"),
                    ignore=shutil.ignore_patterns("__pycache__"))
    # 把趋势账本也带进归档副本：单独渲染这个版本时 Trends 页同样有数
    sync_history_into(repo_root, project, os.path.join(dest, "results"), cfg)

    counts = None
    junit_copied = False
    if junit_path and os.path.isfile(junit_path):
        try:
            shutil.copy2(junit_path, os.path.join(dest, "junit.xml"))
            junit_copied = True
            counts = _counts_from_junit(os.path.join(dest, "junit.xml"))
        except Exception:
            counts = None

    meta = {
        "version": version,
        "project": project,
        "project_name": project_name(repo_root, project),
        "kind": classify_kind(argv),
        "started_at": started_at.isoformat(timespec="seconds") if isinstance(started_at, datetime)
        else (started_at or ""),
        "finished_at": now.isoformat(timespec="seconds"),
        "exit_status": int(exit_status),
        "counts": counts,
        "junit_archived": junit_copied,
        "argv": [str(a) for a in (argv or [])],
        "git_head": _git_head(repo_root),
        "host": socket.gethostname(),
        "user": os.environ.get("USERNAME") or os.environ.get("USER") or "",
        "bytes": 0,
    }
    if extra:
        meta.update(extra)

    with open(os.path.join(dest, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    meta["bytes"] = dir_size(dest)
    with open(os.path.join(dest, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    prune(repo_root, project, cfg)
    return meta


def list_versions(repo_root, project, cfg=None):
    """返回该项目的版本列表，**按版本号倒序**（时间戳格式可字典序排）。

    没有 meta.json 的目录（历史残留/手工放入）用目录名补一个最小 meta，保证仍可见。
    """
    root = os.path.join(history_root(repo_root, cfg), project)
    out = []
    if not os.path.isdir(root):
        return out
    for name in os.listdir(root):
        d = os.path.join(root, name)
        if not (os.path.isdir(d) and _VER_RE.match(name)):
            continue
        meta = {"version": name, "project": project, "kind": "full"}
        mp = os.path.join(d, "meta.json")
        if os.path.isfile(mp):
            try:
                with open(mp, "r", encoding="utf-8") as f:
                    meta.update(json.load(f) or {})
            except Exception:
                pass
        meta["version"] = name
        meta["path"] = d
        meta.setdefault("counts", None)
        out.append(meta)
    out.sort(key=lambda m: m["version"], reverse=True)
    return out


def latest_version(repo_root, project, cfg=None):
    vs = list_versions(repo_root, project, cfg)
    return vs[0] if vs else None


def resolve_version(repo_root, project, version, cfg=None):
    """把 "latest" 解析成具体版本号（导出/命名都用它，避免同名文件互相覆盖）。

    导出侧的 latest = **最近一次已归档运行**；页面上的 /r/<项目>/latest/ 仍是仓库根
    allure-report（零延迟），两者在正常流程下指向同一轮（每轮结束都会归档）。
    """
    if version and version != "latest":
        return version
    v = latest_version(repo_root, project, cfg)
    if not v:
        raise ReportError("项目 %s 还没有历史版本，无法确定 latest（先跑一次或 --import-current）"
                          % project)
    return v["version"]


def prune(repo_root, project, cfg=None):
    """按 kind 分桶裁剪：full 留 keep、debug 留 debug_keep，删最旧。返回删除的版本号列表。"""
    cfg = cfg or load_cfg(repo_root)
    limits = {"full": int(cfg.get("keep", 50)), "debug": int(cfg.get("debug_keep", 5))}
    removed = []
    for kind, limit in limits.items():
        items = [v for v in list_versions(repo_root, project, cfg) if v.get("kind") == kind]
        for v in items[limit:]:                  # 已按倒序，超出部分即最旧
            shutil.rmtree(v["path"], ignore_errors=True)
            removed.append(v["version"])
    return removed


# ---------------------------------------------------------------- 生成报告

def ensure_report(repo_root, project, version, cfg=None):
    """确保某版本的 Allure 站点已存在，返回其目录（latest 直接返回仓库根的 allure-report）。

    生成是一次性的：首次访问现渲染 3~5 秒，之后直接读缓存；缓存按项目只留
    max_generated 份（超出删最旧），删的只是可再生网页，不动 results/。
    """
    if version == "latest":
        d = os.path.join(repo_root, "allure-report")
        if not os.path.isfile(os.path.join(d, "index.html")):
            raise ReportError("当前没有最新报告（allure-report/index.html 不存在）")
        return d

    cfg = cfg or load_cfg(repo_root)
    vd = version_dir(repo_root, project, version, cfg)
    if not os.path.isdir(vd):
        raise ReportError("版本不存在: %s/%s" % (project, version))
    rep = os.path.join(vd, "report")
    if os.path.isfile(os.path.join(rep, "index.html")):
        os.utime(rep, None)                      # 触碰 mtime，作为 LRU 依据
        return rep

    acfg = _allure_cfg(repo_root)
    allure_bin = acfg.get("bin") or shutil.which("allure")
    if not allure_bin or not os.path.exists(allure_bin):
        raise ReportError("未找到 allure CLI（配置 config/bench.yaml report.allure.bin）")
    java_home = os.environ.get("JAVA_HOME") or acfg.get("java_home")
    if not java_home or not os.path.isdir(java_home):
        raise ReportError("未找到 Java（设置 JAVA_HOME 或 bench.yaml report.allure.java_home）")

    if not _GEN_LOCK.acquire(blocking=False):
        raise ReportBusy("另一个报告生成任务在进行中，请稍后重试")
    try:
        if os.path.isfile(os.path.join(rep, "index.html")):   # 等锁期间别人已生成
            return rep
        env = dict(os.environ)
        env["JAVA_HOME"] = java_home
        cmd = ([allure_bin, "generate", os.path.join(vd, "results"), "-o", rep, "--clean"]
               if sys.platform != "win32" else
               ["cmd", "/c", allure_bin, "generate", os.path.join(vd, "results"), "-o", rep, "--clean"])
        r = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            shutil.rmtree(rep, ignore_errors=True)
            raise ReportError("allure generate 失败: %s" % ((r.stderr or r.stdout or "")[-300:]))
        try:                                      # 中文界面，失败不影响报告可用
            from tools.allure_i18n import inject
            inject(rep)
        except Exception:
            pass
        _trim_generated(repo_root, project, cfg)
        return rep
    finally:
        _GEN_LOCK.release()


def _trim_generated(repo_root, project, cfg):
    """每项目只保留最近生成的 max_generated 份站点，按 mtime 判 LRU。"""
    limit = int(cfg.get("max_generated", 3))
    root = os.path.join(history_root(repo_root, cfg), project)
    if not os.path.isdir(root):
        return
    gens = []
    for name in os.listdir(root):
        rep = os.path.join(root, name, "report")
        if os.path.isfile(os.path.join(rep, "index.html")):
            try:
                gens.append((os.path.getmtime(rep), rep))
            except OSError:
                pass
    gens.sort(reverse=True)
    for _mt, rep in gens[limit:]:
        shutil.rmtree(rep, ignore_errors=True)


# ---------------------------------------------------------------- 导出

_LAUNCH_BAT = """@echo off
chcp 936 >nul
rem 报告中心的导出版：Allure 站点不能直接双击 index.html 打开（浏览器禁止 file:// 读 data/*.json），
rem 必须起一个本地 HTTP 服务。本脚本开在 8901 端口，看完直接关窗口即可。
cd /d "%~dp0report"
echo 正在启动本地服务(8901)，浏览器稍后自动打开...
start "" /min python -m http.server 8901 --bind 127.0.0.1
timeout /t 2 >nul
start "" http://127.0.0.1:8901/
"""

_README_TXT = """Allure 交互式报告（离线包）
================================

用法：
  1. 解压本压缩包
  2. 双击「启动查看.bat」
  3. 浏览器自动打开 http://127.0.0.1:8901/
  4. 看完关闭黑色命令行窗口即可

为什么不能直接双击 report/index.html：
  Allure 是前端应用，要用浏览器 fetch 读取同目录 data/*.json；
  浏览器对 file:// 协议禁止这类请求，直接双击只会白屏。

依赖：
  需要接收方已安装 Python 3（bat 里用 python -m http.server）。
  没有 Python 时，任意静态服务器都行：
      cd report && python -m http.server 8901
  或把 report/ 目录放到任意 web 服务器下。

如果要一份不需要任何环境的版本，改用同一次运行的「导出HTML」（单文件，双击即开）。
"""


def build_zip(repo_root, project, version, cfg=None):
    """打包某版本的 Allure 站点 + 启动脚本，返回 (zip 路径, 下载文件名)。

    临时目录由系统管理，调用方用完删或不删都无碍。
    """
    cfg = cfg or load_cfg(repo_root)
    version = resolve_version(repo_root, project, version, cfg)
    rep = ensure_report(repo_root, project, version, cfg)
    stamp = version
    name = "%s_%s" % (project, stamp)
    tmp = tempfile.mkdtemp(prefix="hilreport_")
    zip_path = os.path.join(tmp, name + ".zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for dp, _dns, fns in os.walk(rep):
            for f in fns:
                p = os.path.join(dp, f)
                z.write(p, "%s/report/%s" % (name, os.path.relpath(p, rep).replace("\\", "/")))
        # bat 用 GBK：cmd 默认代码页 936，UTF-8 的中文注释会乱码
        z.writestr("%s/%s" % (name, "启动查看.bat"), _LAUNCH_BAT.replace("\n", "\r\n").encode("gbk", "replace"))
        z.writestr("%s/%s" % (name, "说明.txt"), _README_TXT.replace("\n", "\r\n").encode("gbk", "replace"))
    return zip_path, name + ".zip"


def _allure_tool(repo_root):
    """返回 (allure 命令行前缀, JAVA_HOME)；缺 CLI 或 Java 时抛 ReportError。"""
    acfg = _allure_cfg(repo_root)
    allure_bin = acfg.get("bin") or shutil.which("allure")
    if not allure_bin or not os.path.exists(allure_bin):
        raise ReportError("未找到 allure CLI（配置 config/bench.yaml report.allure.bin）")
    java_home = os.environ.get("JAVA_HOME") or acfg.get("java_home")
    if not java_home or not os.path.isdir(java_home):
        raise ReportError("未找到 Java（设置 JAVA_HOME 或 bench.yaml report.allure.java_home）")
    cmd = [allure_bin] if sys.platform != "win32" else ["cmd", "/c", allure_bin]
    return cmd, java_home


def build_single_file(repo_root, project, version, cfg=None):
    """导出 Allure **官方单文件报告**（自包含 index.html，双击即开、不需要任何本地服务）。

    `--single-file` 是 Allure 2.24+ 的功能（本机 2.29.0 已支持），取代了原先
    「打包 ZIP + 启动查看.bat 起 http.server」的绕行方案。
    两个已知边界：
      1) 单文件模式**不产出 history/**（Allure2 官方限制，allure2#2740），所以趋势页要在
         多文件站点（/r/<项目>/<版本>/）看；导出件里是否带趋势取决于生成前的账本灌入。
      2) 附件都内联进 HTML，体量随附件增长 —— 只有日志/截图类的运行才明显变大。
    做法：把归档的 results 复制到临时目录 → 灌入趋势账本 → 生成 → 读回 index.html。
    临时目录用完即删，绝不写归档本体。
    """
    cfg = cfg or load_cfg(repo_root)
    version = resolve_version(repo_root, project, version, cfg)
    vd = version_dir(repo_root, project, version, cfg)
    src = os.path.join(vd, "results")
    if not os.path.isdir(src):
        raise ReportError("该版本没有归档 results，无法导出单文件报告: %s/%s" % (project, version))
    cmd_prefix, java_home = _allure_tool(repo_root)

    tmp = tempfile.mkdtemp(prefix="hilsingle_")
    try:
        work = os.path.join(tmp, "results")
        shutil.copytree(src, work, ignore=shutil.ignore_patterns("__pycache__"))
        seed_history(repo_root, project, work, cfg)
        out = os.path.join(tmp, "out")
        env = dict(os.environ)
        env["JAVA_HOME"] = java_home
        r = subprocess.run(cmd_prefix + ["generate", work, "-o", out, "--clean", "--single-file"],
                           env=env, capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            raise ReportError("allure --single-file 失败: %s"
                              % ((r.stderr or r.stdout or "")[-300:]))
        idx = os.path.join(out, "index.html")
        if not os.path.isfile(idx):
            raise ReportError("allure --single-file 未产出 index.html")
        try:                                          # 中文界面；改的就是 index.html，需重读
            from tools.allure_i18n import inject
            inject(out)
        except Exception:
            pass
        with open(idx, "rb") as f:
            return f.read(), "%s_%s.html" % (project, version)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def build_html(repo_root, project, version, cfg=None):
    """生成单文件 TestStand 风格 HTML（GBK，双击即开，可打印 PDF）。

    输入是归档的 junit.xml —— 所以只有归档了 junit 的版本能导出 HTML；
    allure-results 里没有逐条用例的极限值文本，不适合做这份报告。
    """
    from tools.make_report import parse_junit, render_html

    cfg = cfg or load_cfg(repo_root)
    version = resolve_version(repo_root, project, version, cfg)
    junit = os.path.join(version_dir(repo_root, project, version, cfg), "junit.xml")
    if not os.path.isfile(junit):
        raise ReportError("该版本没有归档 junit.xml，无法生成单文件 HTML（请改用导出 ZIP）")
    r = parse_junit(junit)
    pname = project_name(repo_root, project)
    html = render_html(pname, r, os.environ.get("USERNAME", "?"),
                       hardware="%s HIL (VeriStand 2020)" % pname)
    return html.encode("gbk", "replace")


# ---------------------------------------------------------------- 删除

def delete_versions(repo_root, project, versions=None, kind=None, all_=False,
                    dry_run=False, cfg=None, by=""):
    """删除指定版本，返回 {deleted:[...], freed_bytes:int, dry_run:bool}。

    三种粒度：versions=[...] 精确删 / kind="debug"|"full" 按类删 / all_=True 全删。
    dry_run 只统计不落删（CLI 没给 --yes 时用）。每次真删写 deleted.log 留痕。
    """
    cfg = cfg or load_cfg(repo_root)
    if _GEN_LOCK.locked():
        raise ReportBusy("正在生成历史报告，暂不能删除（稍后重试）")

    allv = list_versions(repo_root, project, cfg)
    if all_:
        targets = allv
    elif kind:
        targets = [v for v in allv if v.get("kind") == kind]
    elif versions:
        wanted = set(versions)
        targets = [v for v in allv if v["version"] in wanted]
        missing = wanted - {v["version"] for v in targets}
        if missing:
            raise ReportError("版本不存在: %s" % ",".join(sorted(missing)))
    else:
        raise ReportError("未指定删除范围（versions / kind / all）")

    sizes = {v["version"]: dir_size(v["path"]) for v in targets}
    freed = sum(sizes.values())
    if not dry_run and targets:
        log = os.path.join(history_root(repo_root, cfg), "deleted.log")
        os.makedirs(os.path.dirname(log), exist_ok=True)
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log, "a", encoding="utf-8") as f:
            for v in targets:
                shutil.rmtree(v["path"], ignore_errors=True)
                f.write("[%s] project=%s version=%s kind=%s bytes=%d by=%s\n"
                        % (stamp, project, v["version"], v.get("kind", "?"),
                           sizes[v["version"]], by or "-"))
    return {"deleted": [v["version"] for v in targets],
            "freed_bytes": freed, "dry_run": bool(dry_run)}


# ---------------------------------------------------------------- 一次性导入

def import_current(repo_root, project, cfg=None):
    """把当前仓库里现存的一轮报告（allure-results + reports/junit.xml + allure-report）
    导成一个历史版本。

    用途：本功能上线前跑的那一轮（例如 2026-11-09 18:07 的 C206-10 基线）还躺在
    会被下次 pytest 清掉的位置；上线时先导一次，它就成了不可再生的第一份历史。
    幂等：同一时刻已导入过则直接返回既有 meta。
    """
    cfg = cfg or load_cfg(repo_root)
    results = os.path.join(repo_root, "allure-results")
    junit = os.path.join(repo_root, "reports", "junit.xml")
    if not (os.path.isdir(results) and any(f.endswith(".json") for f in os.listdir(results))):
        raise ReportError("仓库根没有 allure-results，无可导入的运行")

    # 用 junit 的 mtime 当运行时刻，版本号才与真实跑批时间对应
    base = junit if os.path.isfile(junit) else results
    now = datetime.fromtimestamp(os.path.getmtime(base))
    existing = [v for v in list_versions(repo_root, project, cfg)
                if v["version"] == _version_stamp(now)]
    if existing:
        return existing[0]

    meta = archive_session(repo_root, project, results, junit,
                           started_at=None, exit_status=0,
                           argv=["(imported current run)"], cfg=cfg, now=now,
                           extra={"imported": True})
    if meta is None:
        raise ReportError("归档未启用或没有结果可导入")
    # 现成的 allure-report 一起搬进来，省一次 Java 渲染
    src_rep = os.path.join(repo_root, "allure-report")
    dst_rep = os.path.join(version_dir(repo_root, project, meta["version"], cfg), "report")
    if os.path.isfile(os.path.join(src_rep, "index.html")):
        shutil.copytree(src_rep, dst_rep, dirs_exist_ok=True)
        _trim_generated(repo_root, project, cfg)
    return meta
