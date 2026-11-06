# -*- coding: utf-8 -*-
"""allure_i18n.py —— 给 Allure 静态报告注入"自动中文"脚本

Allure 2.x 内置官方多语言（语言存于 localStorage），但静态报告默认英文。
这里在 allure generate 之后：
1. 把 allure_i18n_zh.js 拷到报告目录；
2. 在 index.html </head> 前插入 <script> 引用（幂等，重复注入不会叠加）。

脚本在 app.js 之前执行，把语言预设为 zh，任意端口/origin 打开都是中文界面。
只改界面语言，不触碰报告数据/图表。
"""
import os
import shutil

_JS_NAME = "allure_i18n_zh.js"
_TAG = '<script src="%s"></script>' % _JS_NAME


def inject(report_dir):
    """返回 True=已注入/已存在；False=报告结构不符（例如非 Allure 报告）。"""
    index = os.path.join(report_dir, "index.html")
    if not os.path.exists(index):
        return False
    src = os.path.join(os.path.dirname(os.path.abspath(__file__)), _JS_NAME)
    dst = os.path.join(report_dir, _JS_NAME)
    shutil.copyfile(src, dst)

    with open(index, "r", encoding="utf-8") as f:
        html = f.read()
    if _TAG in html:
        return True
    # 必须插在 <head> 内、app.js 之前：语言设置要在 Allure 应用初始化前写入 localStorage
    marker = "</head>"
    if marker not in html:
        return False
    html = html.replace(marker, _TAG + "\n" + marker, 1)
    with open(index, "w", encoding="utf-8") as f:
        f.write(html)
    return True
