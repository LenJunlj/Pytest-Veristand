# -*- coding: utf-8 -*-
"""报告升级（A~E）单测：趋势账本 / 单文件导出 / 治理元数据 / 编号标签 / 通知

全部在 tmp_path 里造假仓库，不碰真实 reports/、不调 Java、不发网络请求。
"""
import json
import os
import xml.etree.ElementTree as ET

from helpers import case_ids, notify, report_history as rh, report_meta

RESULTS_JSON = '{"uuid": "u1", "name": "test_pass", "status": "passed", "start": 1, "stop": 2}'

JUNIT = """<?xml version="1.0" encoding="utf-8"?>
<testsuite name="pytest" errors="0" failures="1" skipped="0" tests="2"
           time="9.5" timestamp="2026-11-10T11:25:00">
<testcase classname="demo" name="test_01_a" time="1.0"/>
<testcase classname="demo" name="test_02_b" time="2.0"><failure message="boom">t</failure></testcase>
</testsuite>
"""


def _mk_repo(tmp_path, public_url="http://10.10.3.88:8899", notify_cfg=""):
    repo = tmp_path / "repo"
    (repo / "config").mkdir(parents=True)
    (repo / "projects" / "demo").mkdir(parents=True)
    (repo / "reports").mkdir()
    lines = ["report:", "  history:", "    enabled: true",
             "    dir: 'reports/report_history'", "    keep: 5", "    debug_keep: 2",
             "    max_generated: 2"]
    if public_url is not None:
        lines.append("  public_url: '%s'" % public_url)
    if notify_cfg:
        lines.append(notify_cfg)
    (repo / "config" / "bench.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (repo / "projects" / "demo" / "project.yaml").write_text(
        "name: 演示项目\nveristand:\n  system_definition: 'E:/项目/演示.nivssdf'\n",
        encoding="utf-8")
    return str(repo)


def _mk_results(tmp_path, name="allure-results"):
    d = tmp_path / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "u1-result.json").write_text(RESULTS_JSON, encoding="utf-8")
    return str(d)


# ---------------------------------------------------------------- B 趋势账本

def test_seed_history_first_run_returns_zero(tmp_path):
    repo = _mk_repo(tmp_path)
    results = _mk_results(tmp_path)
    assert rh.seed_history(repo, "demo", results) == 0
    assert not os.path.isdir(os.path.join(results, "history"))


def test_seed_and_harvest_roundtrip(tmp_path):
    repo = _mk_repo(tmp_path)
    ledger = rh.history_ledger(repo, "demo")
    os.makedirs(ledger)
    (tmp_path / "repo" / "seed.txt").write_text("x", encoding="utf-8")
    with open(os.path.join(ledger, "history-trend.json"), "w", encoding="utf-8") as f:
        json.dump([{"buildOrder": 1, "reportName": "old"}], f)

    results = _mk_results(tmp_path)
    assert rh.seed_history(repo, "demo", results) == 1
    assert os.path.isfile(os.path.join(results, "history", "history-trend.json"))

    # 本轮生成的新 history 收回账本
    rep = tmp_path / "allure-report"
    (rep / "history").mkdir(parents=True, exist_ok=True)
    (rep / "history" / "history-trend.json").write_text(
        '[{"buildOrder": 2}]', encoding="utf-8")
    (rep / "history" / "duration-trend.json").write_text("[]", encoding="utf-8")
    assert rh.harvest_history(repo, "demo", str(rep)) == 2
    with open(os.path.join(ledger, "history-trend.json"), encoding="utf-8") as f:
        assert json.load(f)[0]["buildOrder"] == 2      # 账本被新的一轮覆盖
    assert os.path.isfile(os.path.join(ledger, "duration-trend.json"))


def test_ledger_dir_is_not_listed_as_version(tmp_path):
    repo = _mk_repo(tmp_path)
    results = _mk_results(tmp_path)
    rh.archive_session(repo, "demo", results, version="20261110-120000")
    os.makedirs(rh.history_ledger(repo, "demo"), exist_ok=True)
    assert [v["version"] for v in rh.list_versions(repo, "demo")] == ["20261110-120000"]


# ---------------------------------------------------------------- 归档版本一致性

def test_archive_uses_given_version_and_syncs_ledger(tmp_path):
    repo = _mk_repo(tmp_path)
    ledger = rh.history_ledger(repo, "demo")
    os.makedirs(ledger)
    (tmp_path / "repo" / "h.json").write_text("[]", encoding="utf-8")
    with open(os.path.join(ledger, "history-trend.json"), "w", encoding="utf-8") as f:
        json.dump([{"buildOrder": 1}], f)

    results = _mk_results(tmp_path)
    junit = tmp_path / "junit.xml"
    junit.write_text(JUNIT, encoding="utf-8")
    meta = rh.archive_session(repo, "demo", results, str(junit), version="20261110-113000")
    assert meta["version"] == "20261110-113000"
    vd = rh.version_dir(repo, "demo", "20261110-113000")
    # 归档副本里也带趋势账本 → 单看这一版的报告同样有 Trends
    assert os.path.isfile(os.path.join(vd, "results", "history", "history-trend.json"))
    c = meta["counts"]
    assert (c["total"], c["passed"], c["failed"]) == (2, 1, 1)


# ---------------------------------------------------------------- C 治理元数据

def test_categories_shape():
    cats = report_meta.categories()
    assert len(cats) >= 3
    assert all(c.get("matchedStatuses") for c in cats)
    assert "messageRegex" not in cats[-1]          # 最后一条是兜底，不能有正则


def test_environment_xml_keeps_chinese_path(tmp_path):
    repo = _mk_repo(tmp_path)
    path = report_meta.write_environment(
        str(tmp_path), {"SDF": "E:/C206-10项目/Veristand项目/C026-10.nivssdf", "A&B": "<x>"})
    root = ET.parse(path).getroot()
    kv = {p.findtext("key"): p.findtext("value") for p in root.findall("parameter")}
    assert kv["SDF"] == "E:/C206-10项目/Veristand项目/C026-10.nivssdf"
    assert kv["A&B"] == "<x>"                        # 特殊字符被转义后仍能解析回原值


def test_executor_has_build_url(tmp_path):
    repo = _mk_repo(tmp_path)
    report_meta.write_executor(str(tmp_path), "demo", "20261110-120000", repo)
    with open(tmp_path / "executor.json", encoding="utf-8") as f:
        ex = json.load(f)
    assert ex["buildName"] == "20261110-120000"
    assert ex["buildUrl"] == "http://10.10.3.88:8899/r/demo/20261110-120000/"


def test_executor_without_public_url_has_no_link(tmp_path):
    repo = _mk_repo(tmp_path, public_url=None)
    report_meta.write_executor(str(tmp_path), "demo", "20261110-120000", repo)
    with open(tmp_path / "executor.json", encoding="utf-8") as f:
        ex = json.load(f)
    assert "buildUrl" not in ex and "url" not in ex


def test_write_results_meta_writes_three_files(tmp_path):
    repo = _mk_repo(tmp_path)
    out = report_meta.write_results_meta(repo, str(tmp_path), "demo", "20261110-120000")
    assert sorted(os.path.basename(p) for p in out) == \
        ["categories.json", "environment.xml", "executor.json"]


# ---------------------------------------------------------------- D 编号标签

def test_parse_seq():
    assert case_ids.parse_seq("test_22_exit_ntc_open") == 22
    assert case_ids.parse_seq("test_07_trigger_level2") == 7
    assert case_ids.parse_seq("test_undervoltage_inhibits") is None      # 手工命名，无序号
    assert case_ids.parse_seq("test_01") is None                          # P2546 的 test_01 不在本规则内
    assert case_ids.parse_seq(None) is None


def test_case_labels():
    labels = dict(case_ids.case_labels("c206_10", 22, "dtc"))
    assert labels["testcase"] == "c206_10#22"
    assert {"seq:22", "module:dtc"} <= set(
        v for k, v in case_ids.case_labels("c206_10", 22, "dtc") if k == "tag")
    assert case_ids.case_labels("c206_10", None) == []


def test_allure_listener_reads_our_label_marks():
    """契约测试：conftest 挂的 mark 必须能被 allure-pytest 的标签读取器解出来。

    allure 升级若改了 mark 名/参数形状，这条会先红 —— 否则报告里会静默少编号。
    """
    import pytest as _pytest
    from allure_pytest.utils import allure_labels

    class _Item(object):
        def __init__(self, marks):
            self._marks = marks

        def iter_markers(self, name=None):
            return [m for m in self._marks if name is None or m.name == name]

    marks = [_pytest.mark.allure_label(v, label_type=t)
             for t, v in case_ids.case_labels("c206_10", 22, "dtc")]
    labels = set(allure_labels(_Item(marks)))
    assert ("testcase", "c206_10#22") in labels
    assert ("tag", "seq:22") in labels
    assert ("tag", "module:dtc") in labels


# ---------------------------------------------------------------- E 通知

def test_notify_disabled_by_default():
    assert notify.send({}, "x") == {"sent": False, "reason": "disabled"}
    assert notify.send({"enabled": True, "webhook": ""}, "x")["reason"] == "no webhook"


def test_notify_payload_shape():
    assert notify.payload("wecom", "hi") == {"msgtype": "text", "text": {"content": "hi"}}
    dd = notify.payload("dingtalk", "hi", mention_all=True)
    assert dd["at"] == {"isAtAll": True}


def test_notify_text_summary():
    text = notify.build_text("c206_10", "20261110-113000",
                             {"passed": 61, "failed": 3, "skipped": 0},
                             ["右02 enable_8v5", "DTC05", "DTC06"],
                             url="http://x/r/c206_10/20261110-113000/",
                             duration_s=1274, status="failed")
    assert "c206_10 20261110-113000" in text and "有失败" in text
    assert "通过 61 / 失败 3" in text and "右02 enable_8v5" in text
    assert text.rstrip().endswith("20261110-113000/")
    long = notify.build_text("p", "v", {}, ["x" * 5000])
    assert len(long) <= notify._MAX_CONTENT


# ---------------------------------------------------------------- 回归：页面无限刷新

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_dashboard_auto_reload_needs_observed_running():
    """回归 2026-11-10：任务已结束的页面每次重载都满足"结束且有报告"→ 无限刷新。

    修法是加 sawRunning（本页亲眼看到过运行中才在结束时刷新一次）。这条锁住该条件。
    """
    src = open(os.path.join(REPO_ROOT, "tools", "serve_report.py"), encoding="utf-8").read()
    assert "let sawRunning = false" in src
    assert "if(running){ sawRunning = true; }" in src
    assert "job.report_version && sawRunning && !reloaded" in src
