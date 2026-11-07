# -*- coding: utf-8 -*-
"""全局 fixture 分层（P1 骨架核心）：

  session 级：bench_config → bench_lock（台架互斥）→ veristand（连接/部署，整个会话一次）
  function 级：vs / channel（每个用例前后把关键通道压回安全状态，防状态泄漏）
"""
import os
import shutil
import subprocess
import sys

import pytest
import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from helpers.bench_lock import BenchLock, LockBusy          # noqa: E402
from helpers.channel import ChannelHelper                    # noqa: E402
from helpers.config_merge import merge_reset_channels       # noqa: E402

# 仓库根 = conftest.py 所在目录。所有相对路径锚定到这里，与运行时 cwd 解耦
# （PyCharm 右键单文件运行时 cwd 是 tests\，不锚定就会找错 config、写歪 reports）
_REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
BENCH_CONFIG_PATH = os.environ.get(
    "HIL_BENCH_CONFIG", os.path.join(_REPO_ROOT, "config", "bench.yaml"))

# junitxml 输出目录预创建（旧版 pytest 不会自动建目录；且不依赖运行时 cwd）
os.makedirs(os.path.join(_REPO_ROOT, "reports"), exist_ok=True)


def pytest_configure(config):
    """把相对路径输出锚定到仓库根（默认相对 cwd，PyCharm 右键运行时会写到 tests\ 下）。
    注意 --junitxml 的 dest 是 xmlpath（pytest 5.x/8.x 相同）。"""
    xml = getattr(config.option, "xmlpath", None)
    if xml and not os.path.isabs(xml):
        config.option.xmlpath = os.path.join(_REPO_ROOT, xml)
    # allure-pytest 的 --alluredir 实际 dest 是 allure_report_dir（2.9.x/2.13.x 一致）
    alluredir = getattr(config.option, "allure_report_dir", None)
    if alluredir and not os.path.isabs(alluredir):
        config.option.allure_report_dir = os.path.join(_REPO_ROOT, alluredir)
    # 未显式传 --alluredir（PyCharm 右键运行就是这样）时，按 bench.yaml 配置自动启用，
    # 避免"跑了却只有 HTML 报告"。--no-allure 可关闭
    if not alluredir and not config.getoption("--no-allure"):
        cfg = _load_allure_cfg()
        if cfg.get("enabled", True) is not False:
            auto = cfg.get("results_dir", "allure-results")
            if not os.path.isabs(auto):
                auto = os.path.join(_REPO_ROOT, auto)
            _clean_dir(auto)                 # 等价 --clean-alluredir，防止历史用例混入本次报告
            config.option.allure_report_dir = auto


def pytest_addoption(parser):
    parser.addoption("--no-allure", action="store_true", default=False,
                     help="不自动启用 Allure（默认未传 --alluredir 时也会生成）")


def _load_allure_cfg():
    """读 bench.yaml 的 report.allure 配置（读不到就用空配置 = 全部默认值）。"""
    try:
        with open(BENCH_CONFIG_PATH, "r", encoding="utf-8") as f:
            return ((yaml.safe_load(f) or {}).get("report", {}) or {}).get("allure", {}) or {}
    except Exception:
        return {}


def _clean_dir(path):
    """清空目录内容（不删目录本身），用于每次运行前重置 allure-results。"""
    try:
        for name in os.listdir(path):
            target = os.path.join(path, name)
            if os.path.isdir(target):
                shutil.rmtree(target, ignore_errors=True)
            else:
                try:
                    os.remove(target)
                except OSError:
                    pass
    except OSError:
        pass


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """会话结束后自动生成 Allure 报告（TestStand 风格 HTML 已按用户要求停用）。
    报告失败只打印提示，绝不影响测试结果与退出码。"""
    _generate_allure_report(terminalreporter, config)


def _generate_allure_report(terminalreporter, config):
    """仅当本次传了 --alluredir 时，会话结束自动执行 allure generate（配置见 bench.yaml report.allure）。"""
    alluredir = getattr(config.option, "allure_report_dir", None)
    if not alluredir:
        return
    if not (os.path.isdir(alluredir)
            and any(f.endswith(".json") for f in os.listdir(alluredir))):
        return
    cfg = _load_allure_cfg()
    if cfg.get("enabled", True) is False:
        return

    allure_bin = cfg.get("bin") or shutil.which("allure")
    if not allure_bin or not os.path.exists(allure_bin):
        terminalreporter.write_line("[allure] 未找到 allure CLI（配置 bench.yaml report.allure.bin）")
        return
    outdir = cfg.get("outdir", "allure-report")
    if not os.path.isabs(outdir):
        outdir = os.path.join(_REPO_ROOT, outdir)
    java_home = os.environ.get("JAVA_HOME") or cfg.get("java_home")
    if not java_home or not os.path.isdir(java_home):
        terminalreporter.write_line("[allure] 未找到 Java（设置 JAVA_HOME 或 bench.yaml report.allure.java_home）")
        return

    env = dict(os.environ)
    env["JAVA_HOME"] = java_home
    try:
        r = subprocess.run(
            ["cmd", "/c", allure_bin, "generate", alluredir, "-o", outdir, "--clean"],
            env=env, capture_output=True, text=True, timeout=300)
        if r.returncode == 0:
            try:                                # 注入中文界面（失败不影响报告可用）
                from tools.allure_i18n import inject
                inject(outdir)
            except Exception:
                pass
            terminalreporter.write_line("[allure] 报告: %s" % os.path.join(outdir, "index.html"))
        else:
            terminalreporter.write_line(
                "[allure] 生成失败（不影响测试结果）: %s" % (r.stderr or r.stdout)[-300:])
    except Exception as e:                      # noqa: BLE001
        terminalreporter.write_line("[allure] 生成异常（不影响测试结果）: %s" % e)


@pytest.fixture(scope="session")
def bench_config(request):
    """台架配置 = bench.yaml 基础 + 本次会话涉及项目的 project.yaml 覆盖。

    多项目支持：projects/<项目ID>/project.yaml 的 veristand 段（system_definition、
    model_target 等）覆盖 bench.yaml 的同名键——不同项目指向各自的 .nivssdf。
    一次会话只允许跑一个项目（跨项目混跑会串台架配置，直接报错）。

    reset_channels 例外：按 bench → project → module 三级**字典合并**（后者覆盖，
    docs/通道分层方案.md §5），module 取用例所在模块的 module.yaml 的 reset 段。
    """
    with open(BENCH_CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    roots = sorted(getattr(request.config, "_hil_project_roots", []) or [])
    if len(roots) > 1:
        raise pytest.UsageError(
            "一次 pytest 会话只能跑一个项目，检出了 %s；请分开运行" % roots)
    bench_resets = (cfg.get("veristand") or {}).get("reset_channels") or {}
    proj = {}
    if roots:
        with open(os.path.join(roots[0], "project.yaml"), "r", encoding="utf-8") as f:
            proj = yaml.safe_load(f) or {}
    override = proj.get("veristand") or {}
    module_resets = []
    for mod_root in sorted(getattr(request.config, "_hil_module_roots", []) or []):
        mod_path = os.path.join(mod_root, "module.yaml")
        if os.path.isfile(mod_path):
            with open(mod_path, "r", encoding="utf-8") as f:
                doc = yaml.safe_load(f) or {}
            module_resets.append(doc.get("reset") or {})
    if override:
        cfg["veristand"] = {**(cfg.get("veristand") or {}), **override}
        print(f"[bench] 项目配置覆盖: {roots[0]}（veristand: {sorted(override)}）")
    # reset_channels 三级合并：project 的同名 dict 是逐键覆盖，不是整体替换
    cfg.setdefault("veristand", {})["reset_channels"] = merge_reset_channels(
        bench_resets, override.get("reset_channels"), module_resets)
    n_mod = sum(len(m) for m in module_resets)
    print(f"[bench] 复位通道: bench {len(bench_resets)} + 项目 {len(override.get('reset_channels') or {})}"
          f" + 模块 {n_mod} 条 → 合并 {len(cfg['veristand']['reset_channels'])} 条")
    return cfg


def pytest_collection_finish(session):
    """收集完成后定位本次会话涉及的 project.yaml（项目层）与 module.yaml（模块层）。

    判定规则：从每个用例文件向上分别找最近的 project.yaml / module.yaml，
    其所在目录即项目根 / 模块根。框架级用例（tests/ 下）两者都没有，不参与。
    """
    import pathlib
    roots, mods = set(), set()
    for item in session.items:
        p = pathlib.Path(str(item.fspath))
        proj_found = mod_found = False
        for anc in p.parents:
            if not mod_found and (anc / "module.yaml").is_file():
                mods.add(str(anc))
                mod_found = True
            if not proj_found and (anc / "project.yaml").is_file():
                roots.add(str(anc))
                proj_found = True
            if proj_found and mod_found:
                break
    session.config._hil_project_roots = sorted(roots)
    session.config._hil_module_roots = sorted(mods)


@pytest.fixture(scope="session")
def bench_lock(bench_config):
    """台架互斥：整个 pytest 会话持有；被占用时按 lock.on_busy 决定 fail 或 skip。"""
    cfg = bench_config.get("lock", {})
    lock = BenchLock(
        cfg.get("path", "C:/HIL/bench.lock"),
        cfg.get("stale_after_s", 43200),
    )
    try:
        lock.acquire()
    except LockBusy as busy:
        if cfg.get("on_busy", "fail") == "skip":
            pytest.skip(f"[锁] {busy}")
        raise
    yield lock
    lock.release()


@pytest.fixture(scope="session")
def veristand(bench_config, bench_lock):
    """连接 Gateway 并按配置部署/附加；整个会话只做一次，结束断开。

    mode=attach  附加到已部署系统（白天人工调试的安全默认，不会踢掉别人的会话）
    mode=deploy  完整部署系统定义（CI 夜间回归用；会独占台架——但我们持有锁）

    实证（P2546 台架，niveristand 4.0.0 + VS2020）：前台 VeriStand 已部署时
    connect_to_system 反而失败（ERunConfiguration 3090002）。attach 的正确姿势是
    先 get_system_state 探测：已有活动系统且路径匹配 → 直接复用，不 connect；
    否则才 connect_to_system（deploy=False 附加 / deploy=True 部署）。
    """
    cfg = bench_config["veristand"]
    from niveristand.clientapi import Factory, SystemState   # 延迟导入：纯单元测试不需要装 VeriStand
    ws = Factory().get_iworkspace2()
    deploy = str(cfg.get("mode", "attach")).lower() == "deploy"
    connected = False
    if not deploy:
        try:
            state, active_sdf, _targets = ws.get_system_state()
            want = os.path.normcase(os.path.normpath(cfg["system_definition"]))
            have = os.path.normcase(os.path.normpath(active_sdf)) if active_sdf else ""
            if state == SystemState.ACTIVE and want == have:
                print(f"[veristand] 附加到已运行系统: {active_sdf}")
                yield ws
                return                     # 复用会话，不做 disconnect（不是我们连接的）
        except Exception as e:
            print(f"[veristand] 探测活动系统失败，回退 connect_to_system: {e}")
    ws.connect_to_system(
        cfg["system_definition"], deploy, int(cfg.get("deploy_timeout_ms", 120000)))
    connected = True
    yield ws
    if connected:
        try:
            ws.disconnect_from_system("", False)   # 不 undeploy，系统留给台架
        except Exception as e:
            print(f"[veristand] 断开时出现异常（不掩盖测试结果）: {e}")


@pytest.fixture(scope="session")
def model_manager(bench_config):
    """模型参数读写接口 —— 激励写入的唯一正确通道（实证：Parameters 通道层只读，
    TestStand 存量等价机制即 ModelManager 参数 API；见 helpers/channel.py 头注）。"""
    from niveristand.clientapi import Factory
    return Factory().get_imodel_manager2(
        bench_config["veristand"].get("gateway", "localhost"))


@pytest.fixture
def vs(veristand, bench_config, model_manager):
    """function 级：用例前 + 用例后都把 reset_channels 压回安全状态。

    两侧都执行是刻意的：setup 侧保证上一条用例（或手工操作）的残留被清掉，
    teardown 侧保证本条用例的注入不泄漏给下一条。故障注入通道加进 reset_channels 即可。
    """
    vc = bench_config["veristand"]
    helper = ChannelHelper(veristand, vc.get("channel_prefix", "Aliases/"),
                           model_manager=model_manager,
                           target=vc.get("model_target", "Controller"))

    def apply_resets():
        # 走 ChannelHelper：反斜杠全路径自动转正斜杠 + 前缀规则单一来源
        for name, value in vc.get("reset_channels", {}).items():
            try:
                helper.set(name, value)
            except Exception as e:
                print(f"[vs] 复位 {name} 失败: {e}")

    apply_resets()
    yield veristand
    apply_resets()


@pytest.fixture
def channel(vs, bench_config, model_manager):
    """便捷读写通道；稳态等待用 channel.wait_near(...)。
    模型参数路径的 set 自动走 ModelManager 参数 API（见 ChannelHelper）。"""
    vc = bench_config["veristand"]
    return ChannelHelper(vs, vc.get("channel_prefix", "Aliases/"),
                         model_manager=model_manager,
                         target=vc.get("model_target", "Controller"))
