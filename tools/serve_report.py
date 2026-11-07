# -*- coding: utf-8 -*-
"""Allure 报告局域网常驻服务（多人同时观看）。

- 服务目录：仓库根的 allure-report/（pytest 每次运行后钩子自动重新生成，观众刷新即最新）
- 端口 8899（防火墙规则"Allure报告8899"已放行）；绑定 0.0.0.0，局域网可访问
- 多线程：多人并发访问互不阻塞
- 单实例：端口已被占用则直接退出（计划任务重复触发不会起第二份）
- 由计划任务"AllureReport8899"开机自启（pythonw.exe 无窗口运行）；本文件同时支持手动前台调试

用法：
    手动前台（调试，有日志输出）：F:\\TongYuTestScript\\python.exe tools\\serve_report.py
    常驻（计划任务已配）：schtasks /Run /TN AllureReport8899
    停止：taskkill /IM pythonw.exe /F（会影响所有 pythonw，精确停用任务管理器找 8899）
    删除自启：schtasks /Delete /TN AllureReport8899 /F

观众入口（台架机双网段）：
    http://10.10.3.88:8899    http://192.168.100.114:8899
"""
import os
import socket
import sys
from datetime import datetime
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

PORT = 8899
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC_ROOT = os.path.join(REPO_ROOT, "allure-report")
LOG = os.path.join(REPO_ROOT, "reports", "serve_report.log")


def lan_ips():
    """枚举本机非回环 IPv4（启动日志展示观众入口用）"""
    ips = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except Exception:
        pass
    return sorted(ip for ip in ips if not ip.startswith("127."))


class QuietHandler(SimpleHTTPRequestHandler):
    """pythonw 无窗口运行时 sys.stderr=None，基类逐请求写 stderr 会崩 —— 静默日志。"""
    def log_message(self, *args, **kwargs):
        pass


def main():
    if not os.path.isdir(DOC_ROOT):
        os.makedirs(DOC_ROOT, exist_ok=True)   # 首次尚未生成报告时先占位，避免 404 根路径

    # 单实例：绑定失败 = 已有服务在跑，安静退出
    try:
        httpd = ThreadingHTTPServer(("0.0.0.0", PORT),
                                    partial(QuietHandler, directory=DOC_ROOT))
    except OSError as e:
        print(f"[skip] 端口 {PORT} 已被占用（{e}），假定服务已在运行")
        return 0

    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 服务启动 :{PORT} -> {DOC_ROOT}\n")
        for ip in lan_ips():
            f.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}]   http://{ip}:{PORT}\n")

    print(f"[ok] http://0.0.0.0:{PORT} -> {DOC_ROOT}")
    for ip in lan_ips():
        print(f"     http://{ip}:{PORT}")
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
