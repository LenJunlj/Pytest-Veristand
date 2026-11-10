# -*- coding: utf-8 -*-
"""页面运行任务单测（无台架、不起真实 pytest）

覆盖 build_argv 的四种组合、台架锁/已有任务的互斥、状态推导、停止、日志尾、裁剪，
以及服务层的 /api/run* 参数校验。
"""
import json
import os

import pytest

from helpers import report_history as rh
from helpers import run_jobs as rj


def _mk_repo(tmp_path, lock_path=None):
    repo = tmp_path / "repo"
    (repo / "config").mkdir(parents=True)
    (repo / "projects" / "demo").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "reports").mkdir()
    lock = str(lock_path or (repo / "bench.lock")).replace("\\", "/")
    (repo / "config" / "bench.yaml").write_text(
        "lock:\n"
        "  path: '%s'\n"
        "report:\n"
        "  runner:\n"
        "    keep_jobs: 20\n"
        % lock,
        encoding="utf-8")
    (repo / "projects" / "demo" / "project.yaml").write_text(
        "id: demo\nname: 演示项目\nmodules:\n"
        "  - id: m1\n    name: 模块一\n  - id: m2\n    name: 模块二\n",
        encoding="utf-8")
    return str(repo)


def _job(repo, jid, status="running", pid=None):
    """在临时仓库里放一个任务目录（不真起进程）。"""
    p = os.path.join(rj.run_root(repo), jid)
    os.makedirs(p, exist_ok=True)
    job = {"id": jid, "project": "demo", "modules": [], "include_slow": False,
           "argv": ["pytest"], "started_at": "2026-11-09T20:00:00", "pid": pid,
           "status": status, "exit_code": None, "report_version": None}
    with open(os.path.join(p, "job.json"), "w", encoding="utf-8") as f:
        json.dump(job, f, ensure_ascii=False)
    return p, job


# ---------------------------------------------------------------- argv

def test_build_argv_whole_project(tmp_path):
    repo = _mk_repo(tmp_path)
    assert rj.build_argv(repo, "demo") == [
        "-u", "-m", "pytest", "projects/demo", "-m", "not slow",
        "-p", "no:cacheprovider"]


def test_build_argv_selected_modules(tmp_path):
    repo = _mk_repo(tmp_path)
    argv = rj.build_argv(repo, "demo", ["m2"])
    assert "projects/demo/m2" in argv and "projects/demo" not in argv
    assert "not slow" in argv


def test_build_argv_include_slow_drops_marker(tmp_path):
    repo = _mk_repo(tmp_path)
    argv = rj.build_argv(repo, "demo", ["m1"], include_slow=True)
    # 唯一的 -m 是 `python -m pytest` 那个；标记参数不再追加 → 跑全部（含 slow）
    assert "not slow" not in argv and argv[:2] == ["-u", "-m"] and argv.count("-m") == 1


def test_build_argv_framework(tmp_path):
    repo = _mk_repo(tmp_path)
    argv = rj.build_argv(repo, "framework")
    assert "tests" in argv and "not hil" in argv


def test_build_argv_unknown_module_and_project(tmp_path):
    repo = _mk_repo(tmp_path)
    with pytest.raises(rj.RunError):
        rj.build_argv(repo, "demo", ["nope"])
    with pytest.raises(rj.RunError):
        rj.build_argv(repo, "ghost")


# ---------------------------------------------------------------- 状态 / 互斥

def test_status_none_when_no_jobs(tmp_path):
    repo = _mk_repo(tmp_path)
    assert rj.status(repo) is None


def test_status_marks_interrupted_when_pid_gone(tmp_path):
    repo = _mk_repo(tmp_path)
    _job(repo, "20261109-200000", status="running", pid=999999)   # 必然不存在的 pid
    st = rj.status(repo)
    assert st["status"] == "interrupted" and "note" in st


def test_status_keeps_final_state(tmp_path):
    repo = _mk_repo(tmp_path)
    _job(repo, "20261109-200000", status="passed", pid=999999)
    assert rj.status(repo)["status"] == "passed"


def test_bench_state_reads_lock(tmp_path):
    repo = _mk_repo(tmp_path)
    lock = rj.bench_lock_path(repo)
    assert rj.bench_state(repo) == {"busy": False, "holder": None}

    with open(lock, "w", encoding="utf-8") as f:
        json.dump({"pid": os.getpid(), "machine": "m", "user": "u",
                   "time": "2026-11-09 20:00:00"}, f)
    st = rj.bench_state(repo)
    assert st["busy"] is True and st["holder"]["pid"] == os.getpid()

    with open(lock, "w", encoding="utf-8") as f:       # 陈锁（进程已死）不算占用
        json.dump({"pid": 999999, "machine": "m", "user": "u", "time": "x"}, f)
    assert rj.bench_state(repo)["busy"] is False


def test_start_refuses_when_bench_busy(tmp_path):
    repo = _mk_repo(tmp_path)
    with open(rj.bench_lock_path(repo), "w", encoding="utf-8") as f:
        json.dump({"pid": os.getpid(), "machine": "m", "user": "u", "time": "t"}, f)
    with pytest.raises(rj.RunBusy) as ei:
        rj.start(repo, "demo")
    assert "台架被占用" in str(ei.value)


def test_start_refuses_when_job_alive(tmp_path):
    repo = _mk_repo(tmp_path)
    _job(repo, "20261109-200000", status="running", pid=os.getpid())
    with pytest.raises(rj.RunBusy) as ei:
        rj.start(repo, "demo")
    assert "已有任务" in str(ei.value)


# ---------------------------------------------------------------- 停止 / 日志 / 裁剪

def test_stop_marks_stopped(tmp_path):
    repo = _mk_repo(tmp_path)
    p, _ = _job(repo, "20261109-200000", status="running", pid=999999)
    job = rj.stop(repo)
    assert job["status"] == "stopped"
    assert json.load(open(os.path.join(p, "job.json"), encoding="utf-8"))["status"] == "stopped"


def test_stop_unknown_job(tmp_path):
    repo = _mk_repo(tmp_path)
    with pytest.raises(rj.RunError):
        rj.stop(repo, "20260101-000000")


def test_tail_log(tmp_path):
    repo = _mk_repo(tmp_path)
    p, _ = _job(repo, "20261109-200000", status="running", pid=999999)
    with open(os.path.join(p, "stdout.log"), "wb") as f:
        f.write("\n".join("line%d" % i for i in range(300)).encode("utf-8"))
    tail = rj.tail_log(repo, lines=5)
    assert tail.splitlines() == ["line295", "line296", "line297", "line298", "line299"]


def test_tail_log_survives_gbk_garbage(tmp_path):
    repo = _mk_repo(tmp_path)
    p, _ = _job(repo, "20261109-200000", status="running", pid=999999)
    with open(os.path.join(p, "stdout.log"), "wb") as f:
        f.write(b"ok\n" + bytes([0xff, 0xfe]) + b"\nend")
    assert "ok" in rj.tail_log(repo)


def test_prune_keeps_recent(tmp_path):
    repo = _mk_repo(tmp_path)
    for i in range(5):
        _job(repo, "20261109-20000%d" % i, status="passed", pid=1)
    rj.prune(repo, keep=2)
    names = [n for n, _p in rj.list_jobs(repo)]
    assert names == ["20261109-200004", "20261109-200003"]


# ---------------------------------------------------------------- 服务层

@pytest.fixture
def live_server(tmp_path, monkeypatch):
    import threading
    from http.server import ThreadingHTTPServer
    from tools import serve_report as srv

    repo = _mk_repo(tmp_path)
    monkeypatch.setattr(srv, "REPO_ROOT", repo)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), srv.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        yield "http://127.0.0.1:%d" % httpd.server_address[1], repo
    finally:
        httpd.shutdown()
        httpd.server_close()


def _post(url, body):
    import urllib.error
    import urllib.request
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def test_api_run_status_empty(live_server):
    import urllib.request
    base, _repo = live_server
    with urllib.request.urlopen(base + "/api/run/status", timeout=10) as r:
        data = json.loads(r.read())
    assert data["job"] is None and data["bench"]["busy"] is False


def test_api_run_rejects_bad_input(live_server):
    base, _repo = live_server
    assert _post(base + "/api/run", {"project": "../x"})[0] == 400
    assert _post(base + "/api/run", {"project": "demo", "modules": "m1"})[0] == 400
    code, body = _post(base + "/api/run", {"project": "demo", "modules": ["nope"]})
    assert code == 400 and "模块不存在" in body["error"]


def test_api_run_409_when_bench_busy(live_server):
    base, repo = live_server
    with open(rj.bench_lock_path(repo), "w", encoding="utf-8") as f:
        json.dump({"pid": os.getpid(), "machine": "m", "user": "u", "time": "t"}, f)
    code, body = _post(base + "/api/run", {"project": "demo"})
    assert code == 409 and "台架被占用" in body["error"]


def test_api_run_stop_without_job(live_server):
    base, _repo = live_server
    assert _post(base + "/api/run/stop", {})[0] == 400


def test_api_run_log_returns_text(live_server):
    import urllib.request
    base, repo = live_server
    p, _ = _job(repo, "20261109-200000", status="passed", pid=1)
    with open(os.path.join(p, "stdout.log"), "w", encoding="utf-8") as f:
        f.write("collected 3 items\n32 passed\n")
    with urllib.request.urlopen(base + "/api/run/log?lines=10", timeout=10) as r:
        assert "32 passed" in r.read().decode("utf-8")
