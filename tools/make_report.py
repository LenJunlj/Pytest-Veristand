# -*- coding: utf-8 -*-
"""make_report.py —— 把 pytest 的 junit.xml 转成 TestStand 风格的 HTML 报告

模板：samples/P2546_左后大屏加热_Report[10 59 21][2026 11 3].html
（GBK 编码、charset=gb2312、状态色 Passed=#00FF00 / 序列标题 #00C4C4 / 步骤标题 #FF8000）

用法（台架机）：
  F:\\TongYuTestScript\\python.exe tools\\make_report.py reports\\junit.xml --suite P2546_左后大屏加热
输出：reports/P2546_左后大屏加热_Report[HH MM SS][YYYY M D].html（文件名格式照抄模板）

说明：
- 输入为 pytest 5.x/8.x 均可的 xunit1 junitxml（pytest.ini 已配 --junitxml）；
- failure/error 的断言消息与堆栈作为"步骤明细"展开，等价于 TestStand 的失败详情；
- 生成后建议浏览器直接打开（GBK 与模板一致，双击即看）。
"""
import argparse
import datetime
import os
import sys
import xml.etree.ElementTree as ET

# ---- 模板样式常量（照抄 samples 模板） ----
HTML_HEAD = """<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN"><html>
<head> <meta http-equiv="content-type" content="text/html; charset=gb2312"> <title>Report</title>
<style type="text/css">
div{left:40px;position:relative;}
table {border:1px solid;width:70%;}
table.hdr {border:none;width:70%;}
td {border:1px solid;}
td.hdr_name {border:none;white-space:nowrap;}
td.hdr_value {border:none;}
td.value {width:37%; font-size:82%; vertical-align:top;}
td.label {font-size:82%; vertical-align:top;}
td.separator {border-style:none; height:1px;}
pre.detail {font-size:82%; background-color:#F0F0F0; white-space:pre-wrap; word-wrap:break-word;}
</style>
</head>
<body style="font-family:verdana;">
"""

C_TITLE = "#00C4C4"      # 用例标题行（模板顶层序列）
C_PASS = "#00FF00"       # Passed
C_FAIL = "#FF0000"       # Failed / Error
C_SKIP = "#FFFF00"       # Skipped（模板无样例，取黄）
C_TIME = "#32FFFF"       # Module Time
C_SUM_ROW = "#D0D0D0"    # 摘要行底色


def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def status_of(tc):
    """返回 (状态文字, 颜色, 明细元素) —— 明细元素为 failure/error/skipped 或 None"""
    for tag, text, color in (("failure", "Failed", C_FAIL),
                             ("error", "Error", C_FAIL),
                             ("skipped", "Skipped", C_SKIP)):
        el = tc.find(tag)
        if el is not None:
            return text, color, el
    return "Passed", C_PASS, None


def parse_junit(path):
    root = ET.parse(path).getroot()
    # pytest xunit1 根节点即 testsuite；xunit2 外面套 testsuites —— 都取 testsuite
    suite = root if root.tag == "testsuite" else root.find("testsuite")
    cases = []
    for tc in suite.iter("testcase"):
        text, color, el = status_of(tc)
        cases.append({
            "name": tc.get("name", "?"),
            "cls": (tc.get("classname") or "").split(".")[-1],
            "time": float(tc.get("time") or 0.0),
            "status": text,
            "color": color,
            "msg": (el.get("message") if el is not None and el.get("message") else ""),
            "detail": ((el.text or "").strip() if el is not None else ""),
        })
    return {
        "time": float(suite.get("time") or 0.0),
        "timestamp": suite.get("timestamp") or "",
        "total": int(suite.get("tests") or len(cases)),
        "errors": int(suite.get("errors") or 0),
        "failures": int(suite.get("failures") or 0),
        "skips": int(suite.get("skips") or 0),
        "cases": cases,
    }


def build_html(suite_name, r, tester, out_path):
    now = datetime.datetime.now()
    passed = sum(1 for c in r["cases"] if c["status"] == "Passed")
    failed = sum(1 for c in r["cases"] if c["status"] == "Failed")
    errored = sum(1 for c in r["cases"] if c["status"] == "Error")
    skipped = sum(1 for c in r["cases"] if c["status"] == "Skipped")

    b = [HTML_HEAD]
    b.append("<br><a name=\"top\"></a><center> <h1>%s</h1></center><br><br>" % esc(suite_name))
    # ---- hdr 表（字段照抄模板） ----
    b.append("<table class='hdr'><tbody>")
    for k, v in (("Software Version", "pytest-Veristand"),
                 ("Hardware Verison", "P2546 HIL (VeriStand 2020)"),
                 ("Start Time", r["timestamp"] or now.strftime("%Y-%m-%d %H:%M:%S")),
                 ("Executed Time", "%.3f seconds" % r["time"]),
                 ("Tester", tester),
                 ("Total Tests", str(r["total"])),
                 ("Passed / Failed / Error / Skipped",
                  "%d / %d / %d / %d" % (passed, failed, errored, skipped))):
        b.append("<tr><td class='hdr_name'><b>%s:</b></td><td class='hdr_value'><b>%s</b></td></tr>"
                 % (k, esc(v)))
    b.append("</tbody></table><br>")

    # ---- 摘要表 ----
    b.append("<table><tbody>")
    for i, c in enumerate(r["cases"]):
        b.append(
            "<tr><td style=\"border-color:#000000;background-color:%s;\"><a href=\"#ResultID%d\">%s</td>"
            "<td style=\"border-color:#000000;background-color:%s;\">%s</a></td>"
            "<td style=\"border-color:#000000;background-color:%s;\">%s</td></tr>"
            % (C_SUM_ROW, i, esc(c["name"]), C_SUM_ROW, c["status"], C_SUM_ROW, esc(c["cls"])))
    b.append("</tbody></table><br><hr>")

    # ---- 明细块 ----
    for i, c in enumerate(r["cases"]):
        b.append("<div><table style=\"border-color:#000000;\"><tbody>")
        b.append("<tr><td colspan='2' style=\"border-color:#000000;background-color:%s;\">"
                 "<a name=\"ResultID%d\">%s</a></td></tr>" % (C_TITLE, i, esc(c["name"])))
        b.append("<tr><td class='label' style=\"border-color:#000000;background-color:#FFFFFF;\">"
                 "Status:                   </td>\n"
                 "<td class='value' style=\"border-color:#000000;background-color:%s;\">%s</td></tr>"
                 % (c["color"], c["status"]))
        b.append("<tr><td class='label' style=\"border-color:#000000;background-color:#FFFFFF;\">"
                 "Module Time:              </td>\n"
                 "<td class='value' style=\"border-color:#000000;background-color:%s;\">%.7f</td></tr>"
                 % (C_TIME, c["time"]))
        if c["msg"]:
            b.append("<tr><td class='label' style=\"border-color:#000000;background-color:#FFFFFF;\">"
                     "Message:                 </td>\n"
                     "<td class='value' style=\"border-color:#000000;background-color:#FFFFFF;\">%s</td></tr>"
                     % esc(c["msg"]))
        if c["detail"]:
            b.append("<tr><td colspan='2'><pre class='detail'>%s</pre></td></tr>" % esc(c["detail"]))
        b.append("<tr><td class='separator' style=\"background-color:#000000;\" colspan='2'></td></tr>")
        b.append("</tbody></table><br></div>")

    b.append("<h3>End UUT Report</h3> <hr style=\"color:#0000E0;background-color:#0000E0;"
             "border-width:0;width:90%;height:5px;\"></body></html>")

    # 模板为 GBK(charset=gb2312)，输出保持一致
    with open(out_path, "w", encoding="gbk", errors="replace") as f:
        f.write("".join(b))


def main():
    ap = argparse.ArgumentParser(description="junit.xml → TestStand 风格 HTML 报告")
    ap.add_argument("junit", help="pytest 生成的 junit.xml 路径")
    ap.add_argument("--suite", default="HIL功能测试", help="报告标题/套件名（默认模板同名）")
    ap.add_argument("--tester", default=os.environ.get("USERNAME", "?"), help="测试员")
    ap.add_argument("-o", "--outdir", default=None, help="输出目录（默认 junit 同目录）")
    args = ap.parse_args()

    r = parse_junit(args.junit)
    outdir = args.outdir or os.path.dirname(os.path.abspath(args.junit))
    os.makedirs(outdir, exist_ok=True)
    now = datetime.datetime.now()
    fname = "%s_Report[%d %d %d][%d %d %d].html" % (
        args.suite, now.hour, now.minute, now.second, now.year, now.month, now.day)
    out_path = os.path.join(outdir, fname)
    build_html(args.suite, r, args.tester, out_path)

    p = sum(1 for c in r["cases"] if c["status"] == "Passed")
    print("报告已生成: %s" % out_path)
    print("用例 %d 条: %d passed, %d failed/error, %d skipped"
          % (len(r["cases"]), p, r["failures"] + r["errors"], r["skips"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
