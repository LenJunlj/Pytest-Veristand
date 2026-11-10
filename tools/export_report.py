# -*- coding: utf-8 -*-
"""export_report.py —— 报告历史的命令行出口（导出 / 删除 / 一次性导入）

报告中心和它共用 helpers/report_history.py，两种用法结果完全一致；
不连局域网服务、或想批量清理时用这个。

用法（都在仓库根执行）：
  # 看有哪些版本
  F:\\TongYuTestScript\\python.exe tools\\export_report.py --list --project c206_10

  # 导出（默认 ZIP 交互包；--format html 出单文件 HTML）
  F:\\TongYuTestScript\\python.exe tools\\export_report.py --project c206_10 --version latest --format zip
  F:\\TongYuTestScript\\python.exe tools\\export_report.py --project c206_10 --version 20261109-180703 --format html -o D:\\报告

  # 删除（不加 --yes 只做 dry-run，打印将删什么、能腾多少）
  F:\\TongYuTestScript\\python.exe tools\\export_report.py --delete --project c206_10 --kind debug
  F:\\TongYuTestScript\\python.exe tools\\export_report.py --delete --project c206_10 --kind debug --yes
  F:\\TongYuTestScript\\python.exe tools\\export_report.py --delete --project c206_10 --version 20261109-180703,20261109-181022 --yes
  F:\\TongYuTestScript\\python.exe tools\\export_report.py --delete --project c206_10 --all --yes

  # 把仓库里现存的那一轮报告导成第一份历史（功能上线时跑一次，之后就不用了）
  F:\\TongYuTestScript\\python.exe tools\\export_report.py --import-current --project c206_10
"""
import argparse
import os
import re
import shutil
import sys
from datetime import datetime

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from helpers import report_history as rh  # noqa: E402


def _fmt_bytes(n):
    n = int(n or 0)
    return "%.1f MB" % (n / 1048576.0) if n >= 1048576 else "%.0f KB" % (n / 1024.0)


def cmd_list(project):
    vs = rh.list_versions(REPO_ROOT, project)
    if not vs:
        print("项目 %s 还没有历史版本。" % project)
        print("先把仓库里现存的那一轮导进来：--import-current --project %s" % project)
        return 0
    print("项目 %s（%s）共 %d 个版本，目录 %s"
          % (project, rh.project_name(REPO_ROOT, project), len(vs),
             os.path.join(rh.history_root(REPO_ROOT), project)))
    print("%-18s %-6s %6s %6s %6s %9s %10s  %s"
          % ("版本", "类型", "通过", "失败", "跳过", "耗时", "大小", "git"))
    for v in vs:
        c = v.get("counts") or {}
        print("%-18s %-6s %6s %6s %6s %9s %10s  %s"
              % (v["version"], "调试" if v.get("kind") == "debug" else "全量",
                 c.get("passed", "-"), c.get("failed", "-"), c.get("skipped", "-"),
                 ("%ss" % c["duration_s"]) if c.get("duration_s") else "-",
                 _fmt_bytes(rh.dir_size(v["path"])), v.get("git_head") or "-"))
    return 0


def cmd_export(args):
    outdir = args.outdir or os.path.join(REPO_ROOT, "reports", "exports")
    os.makedirs(outdir, exist_ok=True)
    ver = rh.resolve_version(REPO_ROOT, args.project, args.version)
    if args.format == "html":
        data = rh.build_html(REPO_ROOT, args.project, ver)
        name = "%s_%s.html" % (args.project, ver)
        path = os.path.join(outdir, name)
        with open(path, "wb") as f:
            f.write(data)
        print("已导出单文件 HTML: %s（%s）" % (path, _fmt_bytes(len(data))))
    else:
        tmp, name = rh.build_zip(REPO_ROOT, args.project, ver)
        path = os.path.join(outdir, name)
        shutil.move(tmp, path)
        print("已导出 ZIP 交互包: %s（%s）" % (path, _fmt_bytes(os.path.getsize(path))))
        print("  接收方解压后双击「启动查看.bat」即可（不能直接双击 report/index.html）")
    return 0


def cmd_delete(args):
    versions = [v.strip() for v in (args.version or "").split(",") if v.strip()]
    r = rh.delete_versions(REPO_ROOT, args.project, versions=versions,
                           kind=args.kind, all_=args.all,
                           dry_run=not args.yes,
                           by="%s@%s" % (os.environ.get("USERNAME", "-"), "cli"))
    if not r["deleted"]:
        print("没有匹配的版本可删。")
        return 0
    head = "将删除" if r["dry_run"] else "已删除"
    print("%s %d 个版本，释放 %s：%s"
          % (head, len(r["deleted"]), _fmt_bytes(r["freed_bytes"]),
             ", ".join(r["deleted"])))
    if r["dry_run"]:
        print("这是 dry-run（未落删）。确认无误后加 --yes 再执行一次。")
        return 0
    print("删除记录已写入 %s" % os.path.join(rh.history_root(REPO_ROOT), "deleted.log"))
    return 0


def cmd_import(args):
    meta = rh.import_current(REPO_ROOT, args.project)
    c = meta.get("counts") or {}
    print("已导入为历史版本 %s/%s（%s，%s 条，%s）"
          % (args.project, meta["version"],
             "调试" if meta.get("kind") == "debug" else "全量",
             c.get("total", "-"), _fmt_bytes(meta.get("bytes", 0))))
    print("查看：http://<台架机>:8899/?project=%s" % args.project)
    return 0


def main():
    ap = argparse.ArgumentParser(
        description="报告历史：导出 / 删除 / 导入（与报告中心共用同一份归档）")
    ap.add_argument("--project", required=True, help="项目目录名，如 c206_10 / p2546")
    ap.add_argument("--list", action="store_true", help="列出版本")
    ap.add_argument("--version", default="latest",
                    help="版本号 20261109-180703 / latest；删除时可逗号分隔多个")
    ap.add_argument("--format", choices=("zip", "html"), default="zip",
                    help="zip=Allure 交互包(需本地服务打开) / html=单文件 HTML(双击即开)")
    ap.add_argument("-o", "--outdir", default=None,
                    help="导出目录（默认 reports/exports）")
    ap.add_argument("--delete", action="store_true", help="删除版本")
    ap.add_argument("--kind", choices=("debug", "full"), default=None,
                    help="配合 --delete：按类型删（debug=调试运行）")
    ap.add_argument("--all", action="store_true", help="配合 --delete：删该项目全部版本")
    ap.add_argument("--yes", action="store_true", help="删除时确认执行（不加只做 dry-run）")
    ap.add_argument("--import-current", action="store_true",
                    help="把仓库根现存的 allure-results/allure-report 导成一个历史版本")
    args = ap.parse_args()

    if not re.match(r"^[A-Za-z0-9_]{1,40}$", args.project):
        print("项目名非法: %s" % args.project)
        return 2
    try:
        if args.import_current:
            return cmd_import(args)
        if args.delete:
            return cmd_delete(args)
        if args.list:
            return cmd_list(args.project)
        return cmd_export(args)
    except rh.ReportError as e:
        print("失败: %s" % e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
