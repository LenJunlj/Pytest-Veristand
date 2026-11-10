# -*- coding: utf-8 -*-
"""notify.py —— 跑完推一条消息到群（企业微信 / 钉钉机器人；默认关闭）

配置在 config/bench.yaml 的 report.notify：

    notify:
      enabled: false       # 默认关：没填 webhook 不会发任何请求
      kind: wecom          # wecom=企业微信 / dingtalk=钉钉 / json=自定义 webhook
      webhook: ""          # 群机器人地址（含 key），属台架本地配置，别提交
      mention_all: false   # 钉钉是否 @所有人

只用标准库 urllib（本环境没装 requests，也不想为一条通知加依赖）。
**发送失败只返回结果，不抛异常、不改退出码** —— 通知是锦上添花，绝不能影响测试结论。
"""
import json
import urllib.request

_MAX_CONTENT = 1800          # 企业微信 text 上限 2048 字节，留出余量


def payload(kind, text, mention_all=False):
    """企业微信与钉钉的 text 消息形状一致；kind=json 时原样发这个结构。"""
    text = (text or "")[:_MAX_CONTENT]
    body = {"msgtype": "text", "text": {"content": text}}
    if kind == "dingtalk":
        body["at"] = {"isAtAll": bool(mention_all)}
    return body


def build_text(project, version, counts, failed_names=(), url="", duration_s=None,
               status=""):
    """拼一条能直接看懂的摘要：结论 + 计数 + 前几条失败 + 报告链接。"""
    c = counts or {}
    head = "【HIL】%s %s" % (project, version)
    verdict = {"passed": "全部通过", "failed": "有失败", "error": "有异常"}.get(status, "结束")
    lines = ["%s %s" % (head, verdict)]
    lines.append("通过 %s / 失败 %s / 跳过 %s"
                 % (c.get("passed", "-"), c.get("failed", "-"), c.get("skipped", "-")))
    if duration_s:
        lines.append("耗时 %s 秒" % duration_s)
    names = list(failed_names or [])
    if names:
        lines.append("失败：" + "、".join(names[:5]) + ("…" if len(names) > 5 else ""))
    if url:
        lines.append("报告：%s" % url)
    return "\n".join(lines)[:_MAX_CONTENT]


def send(cfg, text, timeout=5):
    """按配置发一条；返回 {"sent": bool, "reason": str}。cfg = report.notify 段。"""
    cfg = cfg or {}
    if cfg.get("enabled") is not True:
        return {"sent": False, "reason": "disabled"}
    webhook = (cfg.get("webhook") or "").strip()
    if not webhook:
        return {"sent": False, "reason": "no webhook"}
    kind = (cfg.get("kind") or "wecom").lower()
    data = json.dumps(payload(kind, text, cfg.get("mention_all")),
                      ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(webhook, data=data,
                                 headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return {"sent": True, "status": getattr(r, "status", 200)}
    except Exception as e:                      # noqa: BLE001 - 网络问题一律不外抛
        return {"sent": False, "reason": str(e)}
