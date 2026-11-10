# -*- coding: utf-8 -*-
"""run_jobs.py —— 报告中心页面上的"运行本项目"后台任务

为什么单独一层：报告中心跑在 pythonw（无控制台）下，跑一轮用例是 20 分钟级的长任务，
必须起独立进程、把输出落到文件，页面只轮询状态读尾巴。任务与浏览器解绑——
关掉页面任务继续跑（台架上跑一轮不该因为关浏览器而中断）。

任务目录 reports/run_jobs/<YYYYmmdd-HHMMSS>/：
    job.json    {id, project, modules, include_slow, argv, python, started_at, pid,
                 status, exit_code, ended_at, duration_s, report_version}
    stdout.log  pytest 原始输出（PYTHONIOENCODING=utf-8 + python -u，页面读尾巴用）

互斥是三层（台架只有一台，绝不允许两个会话同时驱动）：
    1. 已有存活任务（job.json 里的 pid 还在）
    2. 台架锁被他人持有（C:/HIL/bench.lock，文件内记 pid/机器/用户/时间）
    3. 模块名不在 project.yaml 里 —— 直接 400，不猜路径

状态推导（status()）：
    job.json 记了终态 → 原样返回；否则 pid 还活着 → running；pid 没了但没 exit_code
    → interrupted（服务重启/被外部杀掉，用例进程本身可能还在跑，不代为处理）
"""
import json
import os
import shutil
import subprocess
import sys
import threading
from datetime import datetime

from helpers.bench_lock import _pid_alive

RUN_DIRNAME = os.path.join("reports", "run_jobs")
DEFAULT_KEEP_JOBS = 20
DEFAULT_BENCH_LOCK = "C:/HIL/bench.lock"

# 终态：不再变化，页面可直接展示结论
FINAL = ("passed", "failed", "error", "stopped", "interrupted")


class RunError(Exception):
    """任务级业务异常（服务层据此回 4xx/409）。"""


class RunBusy(RunError):
    """已有任务在跑，或台架被占用。"""


# ---------------------------------------------------------------- 配置

def _read_yaml_cfg(repo_root):
    try:
        import yaml
        with open(os.path.join(repo_root, "config", "bench.yaml"), "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def bench_lock_path(repo_root):
    cfg = _read_yaml_cfg(repo_root)
    return ((cfg.get("lock") or {}).get("path")) or DEFAULT_BENCH_LOCK


def _runner_cfg(repo_root):
    cfg = _read_yaml_cfg(repo_root)
    return ((cfg.get("report") or {}).get("runner")) or {}


def python_exe(repo_root):
    """跑 pytest 用的解释器。

    服务是 pythonw 起的，直接用它拉子进程会没有控制台（日志重定向还是能用，但
    pythonw 对 sys.stdout 的处理更容易踩坑），所以默认换成同目录的 python.exe。
    可在 bench.yaml 的 report.runner.python 显式指定。
    """
    want = str(_runner_cfg(repo_root).get("python") or "")
    if want and os.path.isfile(want):
        return want
    exe = sys.executable or "python"
    base = os.path.basename(exe).lower()
    if base.startswith("pythonw"):
        cand = os.path.join(os.path.dirname(exe), "python.exe")
        if os.path.isfile(cand):
            return cand
    return exe


def run_root(repo_root):
    return os.path.join(repo_root, RUN_DIRNAME)


# ---------------------------------------------------------------- 命令行

def build_argv(repo_root, project, modules=None, include_slow=False):
    """构造 pytest 参数（不含解释器）。纯函数，便于单测。

    framework → 跑 tests/ 并排除 hil（框架自检，不需要台架）
    hil 项目 → projects/<项目>/<模块...>；默认排除 slow（耐久 1800s/2696s 这类）
    """
    from helpers import report_history as rh

    modules = list(modules or [])
    if project == "framework":
        if modules:
            raise RunError("框架自检不接受模块参数")
        targets, marker = ["tests"], "not hil"
    else:
        proj = next((p for p in rh.discover_projects(repo_root) if p["id"] == project), None)
        if proj is None:
            raise RunError("项目不存在: %s" % project)
        known = [m["id"] for m in proj["modules"]]
        bad = [m for m in modules if m not in known]
        if bad:
            raise RunError("模块不存在: %s（可选: %s）" % (",".join(bad), ",".join(known) or "-"))
        if modules:
            targets = ["projects/%s/%s" % (project, m) for m in modules]
        else:
            targets = ["projects/%s" % project]
        marker = None if include_slow else "not slow"

    # -u 是解释器参数（python -u），必须在 -m 之前；写进 pytest 参数会被判非法
    argv = ["-u", "-m", "pytest"] + targets
    if marker:
        argv += ["-m", marker]
    argv += ["-p", "no:cacheprovider"]
    return argv


# ---------------------------------------------------------------- 任务目录

def _job_dir(repo_root, job_id):
    return os.path.join(run_root(repo_root), job_id)


def _read_job(path):
    try:
        with open(os.path.join(path, "job.json"), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _write_job(path, job):
    tmp = os.path.join(path, "job.json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(job, f, ensure_ascii=False, indent=2)
    os.replace(tmp, os.path.join(path, "job.json"))


def list_jobs(repo_root):
    """按任务 id 倒序（id 是时间戳，字典序即时间序）。"""
    root = run_root(repo_root)
    if not os.path.isdir(root):
        return []
    out = []
    for name in sorted(os.listdir(root), reverse=True):
        p = os.path.join(root, name)
        if os.path.isdir(p) and os.path.isfile(os.path.join(p, "job.json")):
            out.append((name, p))
    return out


def _derive(job):
    """按 pid 存活情况修正状态（进程没了但没记 exit_code = 服务重启/被外部杀）。"""
    if not job or job.get("status") in FINAL:
        return job
    if _pid_alive(int(job.get("pid") or 0)):
        job["status"] = "running"
    else:
        job["status"] = "interrupted"
        job.setdefault("note", "跟踪丢失：服务重启或进程被外部结束，日志仍在任务目录")
    return job


def status(repo_root):
    """当前/最近一个任务的状态；没有任务返回 None。"""
    jobs = list_jobs(repo_root)
    if not jobs:
        return None
    _name, path = jobs[0]
    return _derive(_read_job(path))


def bench_state(repo_root):
    """台架是否被占用（展示用，不参与加锁——真正的锁由 pytest 会话自己去抢）。"""
    path = bench_lock_path(repo_root)
    if not os.path.isfile(path):
        return {"busy": False, "holder": None}
    try:
        with open(path, "r", encoding="utf-8") as f:
            holder = json.load(f)
    except Exception:
        holder = None
    alive = bool(holder) and _pid_alive(int(holder.get("pid") or 0))
    return {"busy": alive, "holder": holder if alive else None}


# ---------------------------------------------------------------- 启动 / 停止

_threads = {}


def start(repo_root, project, modules=None, include_slow=False):
    """起一个后台 pytest 任务，返回 job dict。互斥不满足时抛 RunBusy。"""
    cur = status(repo_root)
    if cur and cur.get("status") not in FINAL:
        raise RunBusy("已有任务在跑：%s（%s，pid %s），先等它结束或点停止"
                      % (cur.get("project"), cur.get("id"), cur.get("pid")))
    bench = bench_state(repo_root)
    if bench["busy"]:
        h = bench["holder"] or {}
        raise RunBusy("台架被占用：pid %s / %s / %s / %s（锁文件 %s）"
                      % (h.get("pid"), h.get("machine"), h.get("user"), h.get("time"),
                         bench_lock_path(repo_root)))

    argv = build_argv(repo_root, project, modules, include_slow)
    root = run_root(repo_root)
    os.makedirs(root, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    job_id, path = stamp, os.path.join(root, stamp)
    i = 2
    while os.path.exists(path):
        job_id, path = "%s-%d" % (stamp, i), os.path.join(root, "%s-%d" % (stamp, i))
        i += 1
    os.makedirs(path)

    py = python_exe(repo_root)
    log_path = os.path.join(path, "stdout.log")
    job = {
        "id": job_id,
        "project": project,
        "modules": list(modules or []),
        "include_slow": bool(include_slow),
        "argv": [py] + argv,
        "python": py,
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "pid": None,
        "status": "pending",
        "exit_code": None,
        "report_version": None,
    }

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"      # 子进程按 utf-8 写日志，页面按 utf-8 读
    env["PYTHONUNBUFFERED"] = "1"
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
    log = open(log_path, "ab")
    try:
        proc = subprocess.Popen(
            [py] + argv, cwd=repo_root, stdout=log, stderr=subprocess.STDOUT,
            env=env, creationflags=creationflags, close_fds=True)
    except Exception as e:
        log.close()
        job.update(status="error", note="启动失败: %s" % e)
        _write_job(path, job)
        raise RunError("启动 pytest 失败: %s" % e)
    log.close()

    job.update(pid=proc.pid, status="running")
    _write_job(path, job)
    t = threading.Thread(target=_watch, args=(path, job["id"], proc, repo_root),
                         daemon=True, name="run-job-%s" % job_id)
    _threads[job_id] = t
    t.start()
    prune(repo_root)
    return job


def _watch(path, job_id, proc, repo_root):
    """等子进程结束，回填状态/退出码/耗时，并挂上本次运行产生的报告版本。"""
    proc.wait()
    job = _read_job(path) or {}
    # 停止哨兵由 stop() 在杀进程之前落下：被杀的子进程退出码是 1，不能当成 failed
    stopped = os.path.isfile(os.path.join(path, "stopped.flag"))
    if stopped:
        job.update(exit_code=proc.returncode, status="stopped",
                   ended_at=datetime.now().isoformat(timespec="seconds"))
    else:
        code = proc.returncode
        job.update(
            exit_code=code,
            ended_at=datetime.now().isoformat(timespec="seconds"),
            status={0: "passed", 1: "failed", 2: "interrupted", 3: "interrupted",
                    4: "error", 5: "passed"}.get(code, "error"),
        )
    try:
        job["duration_s"] = round(
            (datetime.fromisoformat(job["ended_at"])
             - datetime.fromisoformat(job["started_at"])).total_seconds(), 1)
    except Exception:
        pass
    job["report_version"] = _newest_version_since(repo_root, job)
    _write_job(path, job)
    _threads.pop(job_id, None)


def _newest_version_since(repo_root, job):
    """本次运行结束后新出现的归档版本（页面用来给"查看这份报告"链接）。

    只认"开始时间不早于本次任务"的版本——失败/中断的任务没产生新报告时返回 None，
    不能随手把上一次的旧报告当成本次结果。
    """
    try:
        from helpers import report_history as rh
        start = job.get("started_at") or ""
        for v in rh.list_versions(repo_root, job["project"]):     # 已按倒序
            began = v.get("started_at") or ""
            if began and began >= start:
                return v["version"]
        return None
    except Exception:
        return None


def stop(repo_root, job_id=None):
    """终止任务进程树（含 pytest 派生的 allure/java 子进程）。"""
    jobs = list_jobs(repo_root)
    if not jobs:
        raise RunError("当前没有任务")
    if job_id:
        path = _job_dir(repo_root, job_id)
        if not os.path.isdir(path):
            raise RunError("任务不存在: %s" % job_id)
    else:
        _job_id, path = jobs[0]
    job = _read_job(path) or {}
    pid = int(job.get("pid") or 0)
    # 先落哨兵再杀进程：被杀的子进程退出码是 1，watcher 靠它区分"用户停止"和"失败"
    try:
        with open(os.path.join(path, "stopped.flag"), "w", encoding="utf-8") as f:
            f.write(datetime.now().isoformat(timespec="seconds"))
    except OSError:
        pass
    if pid and _pid_alive(pid):
        cmd = ["taskkill", "/PID", str(pid), "/T", "/F"] if os.name == "nt" else ["kill", "-9", str(pid)]
        subprocess.run(cmd, capture_output=True)
    job.update(status="stopped", exit_code=job.get("exit_code"),
               ended_at=datetime.now().isoformat(timespec="seconds"))
    _write_job(path, job)
    return job


def tail_log(repo_root, job_id=None, lines=120):
    """日志尾部（页面实时看进度用）。解码失败按替换处理，绝不因为编码报错。"""
    if job_id:
        path = os.path.join(_job_dir(repo_root, job_id), "stdout.log")
    else:
        jobs = list_jobs(repo_root)
        if not jobs:
            return ""
        path = os.path.join(jobs[0][1], "stdout.log")
    if not os.path.isfile(path):
        return ""
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        return ""
    text = data.decode("utf-8", "replace")
    rows = text.splitlines()
    return "\n".join(rows[-int(lines):]) if lines else text


def prune(repo_root, keep=None):
    """只保留最近 keep 个任务目录（日志可能很大：含 slow 的一轮能到几十 MB）。"""
    limit = int(keep or _runner_cfg(repo_root).get("keep_jobs") or DEFAULT_KEEP_JOBS)
    for _name, path in list_jobs(repo_root)[limit:]:
        shutil.rmtree(path, ignore_errors=True)
