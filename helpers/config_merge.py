# -*- coding: utf-8 -*-
"""配置合并纯函数（供 conftest 与单元测试共用）

reset_channels 三级合并（docs/通道分层方案.md §5）：
    bench.yaml（台架级安全值） → project.yaml（项目级，可选覆盖）
    → module.yaml（模块激励复位）——后者覆盖前者同名键
"""


def merge_reset_channels(bench_resets, project_resets=None, module_resets=()):
    """按 bench → project → module 顺序合并复位通道字典（后者覆盖）。"""
    merged = dict(bench_resets or {})
    if project_resets:
        merged.update(project_resets)
    for m in module_resets or ():
        if m:
            merged.update(m)
    return merged
