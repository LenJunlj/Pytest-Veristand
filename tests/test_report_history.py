# -*- coding: utf-8 -*-
"""报告版本管理单测（无台架、无 Java、无 Allure CLI）

覆盖 helpers/report_history 的归档/检索/裁剪/删除/导出，以及服务层的参数白名单。
全部在 tmp_path 里造假仓库，不碰真实 reports/。
"""
import json
import os
import zipfile
from datetime import datetime, timedelta

import pytest

from helpers import report_history as rh


JUNIT = """<?xml version="1.0" encoding="utf-8"?>
<testsuite name="pytest" errors="1" failures="1" skipped="1" tests="4"
           time="12.345" timestamp="2026-11-09T18:07:00">
<testcase classname="demo.tests" name="test_pass" time="1.0"/>
<testcase classname="demo.tests" name="test_fail" time="2.0"><failure message="boom">trace</failure></testcase>
<testcase classname="demo.tests" name="test_err" time="3.0"><error message="e">tb</error></testcase>
<testcase classname="demo.tests" name="test_skip" time="0.5"><skipped message="s"/></testcase>
</testsuite>
"""


def _mk_repo(tmp_path, keep=2, debug_keep=1, max_generated=1):
    """造一个最小仓库：config/bench.yaml + projects/demo + allure-results + junit.xml"""
    repo = tmp_path / "repo"
    (repo / "config").mkdir(parents=True)
    (repo / "projects" / "demo").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "reports").mkdir()
    (repo / "config" / "bench.yaml").write_text(
        "report:\n"
        "  allure:\n"
        "    bin: ''\n"
        "    java_home: ''\n"
        "  history:\n"
        "    enabled: true\n"
        "    dir: 'reports/report_history'\n"
        "    keep: %d\n"
        "    debug_keep: %d\n"
        "    max_generated: %d\n" % (keep, debug_keep, max_generated),
        encoding="utf-8")
    (repo / "projects" / "demo" / "project.yaml").write_text(
        "id: demo\nname: 演示项目\nmodules:\n  - id: m1\n    name: 模块一\n",
        encoding="utf-8")
    results = repo / "allure-results"
    results.mkdir()
    (results / "abc-result.json").write_text('{"name":"test_pass","status":"passed"}',
                                             encoding="utf-8")
    (repo / "reports" / "junit.xml").write_text(JUNIT, encoding="utf-8")
    return str(repo)


def _archive(repo, when, kind_argv=("-m", "pytest", "projects/demo"), project="demo"):
    return rh.archive_session(
        repo, project, os.path.join(repo, "allure-results"),
        os.path.join(repo, "reports", "junit.xml"),
        started_at=when - timedelta(minutes=1), exit_status=1,
        argv=list(kind_argv), now=when)


# ---------------------------------------------------------------- 基础

def test_classify_kind():
    assert rh.classify_kind(["-m", "pytest", "projects/demo"]) == "full"
    assert rh.classify_kind(["projects/demo/tests/test_all.py::test_01_x"]) == "debug"
    assert rh.classify_kind(["-k", "欠压"]) == "debug"
    assert rh.classify_kind(["-k欠压"]) == "debug"
    assert rh.classify_kind(["--lf"]) == "debug"
    assert rh.classify_kind([]) == "full"


def test_discover_projects(tmp_path):
    repo = _mk_repo(tmp_path)
    got = rh.discover_projects(repo)
    assert [p["id"] for p in got] == ["demo"]      # id 取目录名，与 URL/归档目录一致
    assert got[0]["name"] == "演示项目"
    assert got[0]["modules"] == [{"id": "m1", "name": "模块一"}]
    assert rh.project_name(repo, "demo") == "演示项目"
    assert rh.project_name(repo, "framework") == "框架单元测试"


# ---------------------------------------------------------------- 归档

def test_archive_creates_version_with_counts(tmp_path):
    repo = _mk_repo(tmp_path)
    when = datetime(2026, 11, 9, 18, 7, 3)
    meta = _archive(repo, when)

    assert meta["version"] == "20261109-180703"
    assert meta["kind"] == "full"
    d = os.path.join(rh.history_root(repo), "demo", meta["version"])
    assert os.path.isfile(os.path.join(d, "results", "abc-result.json"))   # 事实源整份拷走
    assert os.path.isfile(os.path.join(d, "junit.xml"))
    with open(os.path.join(d, "meta.json"), encoding="utf-8") as f:
        saved = json.load(f)
    assert saved["counts"] == {"total": 4, "passed": 1, "failed": 1, "error": 1,
                              "skipped": 1, "duration_s": 12.345}
    assert saved["exit_status"] == 1
    assert saved["project_name"] == "演示项目"


def test_archive_twice_in_same_second_does_not_overwrite(tmp_path):
    repo = _mk_repo(tmp_path)
    when = datetime(2026, 11, 9, 18, 7, 3)
    a = _archive(repo, when)
    b = _archive(repo, when)
    assert a["version"] != b["version"]
    assert len(rh.list_versions(repo, "demo")) == 2


def test_archive_skipped_without_allure_results(tmp_path):
    repo = _mk_repo(tmp_path)
    empty = os.path.join(repo, "empty")
    os.makedirs(empty)
    assert rh.archive_session(repo, "demo", empty, None, now=datetime.now()) is None


def test_archive_disabled(tmp_path):
    repo = _mk_repo(tmp_path)
    cfg = dict(rh.load_cfg(repo), enabled=False)
    assert rh.archive_session(repo, "demo", os.path.join(repo, "allure-results"),
                             None, cfg=cfg) is None


def test_list_versions_desc_and_latest(tmp_path):
    repo = _mk_repo(tmp_path)
    base = datetime(2026, 11, 9, 18, 0, 0)
    _archive(repo, base)
    _archive(repo, base + timedelta(minutes=5))
    vs = rh.list_versions(repo, "demo")
    assert [v["version"] for v in vs] == ["20261109-180500", "20261109-180000"]
    assert rh.latest_version(repo, "demo")["version"] == "20261109-180500"


def test_prune_keeps_two_buckets_separately(tmp_path):
    # keep=2 / debug_keep=1：调试运行不能挤掉全量名额
    repo = _mk_repo(tmp_path, keep=2, debug_keep=1)
    base = datetime(2026, 11, 9, 18, 0, 0)
    for i in range(4):
        _archive(repo, base + timedelta(minutes=i))                 # full
    for i in range(3):
        _archive(repo, base + timedelta(minutes=10 + i),
                 kind_argv=["x.py::test_a"])                       # debug
    vs = rh.list_versions(repo, "demo")
    full = [v for v in vs if v["kind"] == "full"]
    debug = [v for v in vs if v["kind"] == "debug"]
    assert len(full) == 2 and len(debug) == 1
    assert full[0]["version"] == "20261109-180300"                  # 留最新的
    assert debug[0]["version"] == "20261109-181200"


# ---------------------------------------------------------------- 删除

def test_delete_dry_run_then_real(tmp_path):
    repo = _mk_repo(tmp_path, keep=10)
    base = datetime(2026, 11, 9, 18, 0, 0)
    _archive(repo, base)
    _archive(repo, base + timedelta(minutes=1))

    dry = rh.delete_versions(repo, "demo", versions=["20261109-180000"], dry_run=True)
    assert dry["deleted"] == ["20261109-180000"] and dry["freed_bytes"] > 0
    assert len(rh.list_versions(repo, "demo")) == 2                 # dry-run 不落删

    real = rh.delete_versions(repo, "demo", versions=["20261109-180000"], by="test")
    assert real["deleted"] == ["20261109-180000"]
    assert [v["version"] for v in rh.list_versions(repo, "demo")] == ["20261109-180100"]
    log = os.path.join(rh.history_root(repo), "deleted.log")
    assert os.path.isfile(log) and "20261109-180000" in open(log, encoding="utf-8").read()


def test_delete_by_kind_only_hits_that_bucket(tmp_path):
    repo = _mk_repo(tmp_path, keep=10, debug_keep=10)
    base = datetime(2026, 11, 9, 18, 0, 0)
    _archive(repo, base)
    _archive(repo, base + timedelta(minutes=1), kind_argv=["a.py::test_b"])
    r = rh.delete_versions(repo, "demo", kind="debug")
    assert r["deleted"] == ["20261109-180100"]
    assert [v["kind"] for v in rh.list_versions(repo, "demo")] == ["full"]


def test_delete_unknown_version_raises(tmp_path):
    repo = _mk_repo(tmp_path)
    _archive(repo, datetime(2026, 11, 9, 18, 0, 0))
    with pytest.raises(rh.ReportError):
        rh.delete_versions(repo, "demo", versions=["20200101-000000"])


# ---------------------------------------------------------------- 导出

def _seed_report(repo, version):
    """手工放一份假站点，绕开 allure CLI（单测不依赖 Java）。"""
    d = rh.version_dir(repo, "demo", version)
    os.makedirs(os.path.join(d, "report", "data"), exist_ok=True)
    with open(os.path.join(d, "report", "index.html"), "w", encoding="utf-8") as f:
        f.write("<html>report</html>")
    with open(os.path.join(d, "report", "data", "x.json"), "w", encoding="utf-8") as f:
        f.write("{}")


def test_build_zip_contains_site_and_launcher(tmp_path):
    repo = _mk_repo(tmp_path)
    meta = _archive(repo, datetime(2026, 11, 9, 18, 7, 3))
    _seed_report(repo, meta["version"])

    path, name = rh.build_zip(repo, "demo", meta["version"])
    assert name == "demo_20261109-180703.zip"
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        assert "demo_20261109-180703/report/index.html" in names
        assert "demo_20261109-180703/启动查看.bat" in names
        assert "demo_20261109-180703/说明.txt" in names
        bat = z.read("demo_20261109-180703/启动查看.bat").decode("gbk")
    assert "http.server" in bat                       # 必须起本地服务，否则 file:// 白屏


def test_build_html_contains_cases(tmp_path):
    repo = _mk_repo(tmp_path)
    meta = _archive(repo, datetime(2026, 11, 9, 18, 7, 3))
    data = rh.build_html(repo, "demo", meta["version"])
    text = data.decode("gbk")
    assert "演示项目" in text
    assert "test_fail" in text and "boom" in text
    assert "4" in text                                # Total Tests


def test_build_html_without_junit_raises(tmp_path):
    repo = _mk_repo(tmp_path)
    meta = rh.archive_session(repo, "demo", os.path.join(repo, "allure-results"),
                             None, now=datetime(2026, 11, 9, 18, 7, 3))
    with pytest.raises(rh.ReportError):
        rh.build_html(repo, "demo", meta["version"])


def test_import_current_and_idempotent(tmp_path):
    repo = _mk_repo(tmp_path)
    rep = os.path.join(repo, "allure-report")
    os.makedirs(rep)
    with open(os.path.join(rep, "index.html"), "w", encoding="utf-8") as f:
        f.write("<html>old</html>")

    a = rh.import_current(repo, "demo")
    assert a["imported"] is True
    d = rh.version_dir(repo, "demo", a["version"])
    assert os.path.isfile(os.path.join(d, "report", "index.html"))   # 现成站点一起搬进来

    b = rh.import_current(repo, "demo")                              # 幂等
    assert b["version"] == a["version"]
    assert len(rh.list_versions(repo, "demo")) == 1


# ---------------------------------------------------------------- 服务层白名单

def test_path_whitelist_rejects_traversal():
    from tools import serve_report as srv
    assert srv.valid_project("c206_10") and srv.valid_project("p2546")
    assert not srv.valid_project("../etc")
    assert not srv.valid_project("a/b")
    assert not srv.valid_project("")
    assert srv.valid_version("latest")
    assert srv.valid_version("20261109-180703")
    assert srv.valid_version("20261109-180703-2")
    assert not srv.valid_version("../../allure-report")
    assert not srv.valid_version("2026-11-09")


# ---------------------------------------------------------------- 服务端到端（本地起服务）

@pytest.fixture
def live_server(tmp_path, monkeypatch):
    """在临时端口起真正的报告中心 handler，指向临时仓库。"""
    import threading
    from http.server import ThreadingHTTPServer
    from tools import serve_report as srv

    repo = _mk_repo(tmp_path, keep=10, debug_keep=10)
    meta = _archive(repo, datetime(2026, 11, 9, 18, 7, 3))
    _seed_report(repo, meta["version"])
    monkeypatch.setattr(srv, "REPO_ROOT", repo)

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), srv.Handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        yield "http://127.0.0.1:%d" % httpd.server_address[1], repo, meta
    finally:
        httpd.shutdown()
        httpd.server_close()


def _get(url):
    import urllib.request
    with urllib.request.urlopen(url, timeout=10) as r:
        return r.status, r.read(), dict(r.headers)


def test_server_dashboard_and_apis(live_server):
    base, _repo, meta = live_server

    status, body, hdr = _get(base + "/")
    assert status == 200 and "报告中心" in body.decode("utf-8")
    assert "演示项目" in body.decode("utf-8")
    assert meta["version"] in body.decode("utf-8")          # 版本表里能看到这一轮

    status, body, _ = _get(base + "/api/projects")
    assert status == 200
    projects = json.loads(body)
    assert projects[0]["id"] == "demo" and projects[0]["versions"] == 1

    status, body, _ = _get(base + "/api/versions?project=demo")
    data = json.loads(body)
    assert data["count"] == 1
    assert data["versions"][0]["counts"]["passed"] == 1
    assert data["versions"][0]["url"] == "/r/demo/%s/" % meta["version"]


def test_server_serves_version_site(live_server):
    base, _repo, meta = live_server
    status, body, _ = _get(base + "/r/demo/%s/" % meta["version"])
    assert status == 200 and b"report" in body


def test_server_export_html_and_zip(live_server):
    base, _repo, meta = live_server

    status, body, hdr = _get(base + "/api/export?project=demo&version=%s&format=html" % meta["version"])
    assert status == 200
    assert hdr.get("Content-Disposition", "").startswith("attachment")
    assert "test_fail" in body.decode("gbk")

    status, body, hdr = _get(base + "/api/export?project=demo&version=%s&format=zip" % meta["version"])
    assert status == 200 and body[:2] == b"PK"


def test_server_rejects_bad_params(live_server):
    import urllib.error
    base, _repo, _meta = live_server
    for url in ("/api/versions?project=../x",
                "/api/export?project=demo&version=../../etc&format=zip",
                "/api/export?project=demo&version=latest&format=pdf"):
        with pytest.raises(urllib.error.HTTPError) as ei:
            _get(base + url)
        assert ei.value.code == 400


def test_server_delete_endpoint(live_server):
    import urllib.request
    base, repo, meta = live_server
    req = urllib.request.Request(
        base + "/api/delete",
        data=json.dumps({"project": "demo", "versions": [meta["version"]]}).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as r:
        out = json.loads(r.read())
    assert out["deleted"] == 1 and out["freed_bytes"] > 0
    assert rh.list_versions(repo, "demo") == []
