# -*- coding: utf-8 -*-
"""报告中心（Allure 局域网常驻服务 + 历史版本管理）

原先是 74 行的纯静态 handler，只把仓库根 allure-report/ 发出去；每次 pytest 都会
覆盖它，看不到历史。现在多了一层"报告中心"：

    GET  /                                → 报告中心页（项目切换 / 版本表 / 查看 / 导出 / 删除）
    GET  /r/<project>/latest/...          → 直接服务仓库根 allure-report/（零延迟，老入口兼容）
    GET  /r/<project>/<version>/...       → 服务某个归档版本（首次访问用 allure CLI 现生成）
    GET  /api/projects                    → 项目清单
    GET  /api/versions?project=<id>       → 版本清单（含 counts/kind/大小）
    GET  /api/export?project=&version=&format=single|html|zip   → 下载导出件
                          single=Allure 单文件报告（双击即开，推荐）
                          html  =TestStand 风格单文件（GBK，可打印）
                          zip   =Allure 站点压缩包（旧方案，需起本地服务才能看）
    POST /api/delete                      → 删除版本（body: {project, versions|kind|all}）

设计要点（改动前请先读）：
- 删除只走 POST：GET 会被浏览器预取/爬虫命中，破坏性操作绝不能用 GET 触发。
- 参数一律过白名单（项目 ^[A-Za-z0-9_]+$、版本 ^{时间戳|latest}$），杜绝 ../ 穿越。
- 沿用 QuietHandler：计划任务用 pythonw 无窗口启动时 sys.stderr 是 None，
  基类逐请求写 stderr 会把响应打断成空回复（2026-11-07 踩过的坑）。
- 历史数据与渲染缓存的边界由 helpers/report_history.py 负责，
  这里只做 HTTP 适配，不碰文件布局。

观众入口（台架机双网段）：http://10.10.3.88:8899  http://192.168.100.114:8899
"""
import html
import json
import mimetypes
import os
import re
import socket
import sys
import traceback
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlsplit

PORT = 8899
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 计划任务用 pythonw 从系统目录启动，cwd 不是仓库根；helpers/tools 都要能 import
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from helpers import report_history as rh  # noqa: E402
from helpers import run_jobs as rj       # noqa: E402

LOG = os.path.join(REPO_ROOT, "reports", "serve_report.log")

_PROJECT_RE = re.compile(r"^[A-Za-z0-9_]{1,40}$")
_VERSION_RE = re.compile(r"^(latest|\d{8}-\d{6}(-\d+)?)$")


def valid_project(s):
    return bool(s and _PROJECT_RE.match(s))


def valid_version(s):
    return bool(s and _VERSION_RE.match(s))


def log(msg):
    """写服务日志。pythonw 下 stderr 为 None，绝不能 print 到 stderr。"""
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write("[%s] %s\n" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg))
    except Exception:
        pass


def lan_ips():
    """枚举本机非回环 IPv4（启动日志展示观众入口用）"""
    ips = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except Exception:
        pass
    return sorted(ip for ip in ips if not ip.startswith("127."))


def _fmt_bytes(n):
    n = int(n or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return ("%d %s" % (n, unit)) if unit == "B" else ("%.1f %s" % (n, unit))
        n /= 1024.0
    return "%d B" % n


def _fmt_time(version):
    """版本号 20261109-180703 → 11-09 18:07:03（解析失败就原样显示）。"""
    try:
        d = datetime.strptime(version.split("-")[0], "%Y%m%d")
        t = version.split("-")[1]
        return "%s %s:%s:%s" % (d.strftime("%m-%d"), t[0:2], t[2:4], t[4:6])
    except Exception:
        return version


def _ver_size(v):
    try:
        return rh.dir_size(v["path"])
    except Exception:
        return int(v.get("bytes") or 0)


# ---------------------------------------------------------------- 页面

_CSS = """
*{box-sizing:border-box}
body{margin:0;font:14px/1.6 "Microsoft YaHei",system-ui,-apple-system,"Segoe UI",sans-serif;
     color:#1f2328;background:#f6f8fa}
header{padding:16px 24px;background:#1f2d3d;color:#fff;display:flex;align-items:baseline;gap:12px}
header h1{margin:0;font-size:18px;font-weight:600}
header .sub{color:#9fb0c3;font-size:12px}
.tabs{padding:12px 24px 0;display:flex;gap:8px;flex-wrap:wrap}
.tab{padding:6px 14px;border:1px solid #d0d7de;border-radius:6px 6px 0 0;background:#fff;
     color:#57606a;text-decoration:none}
.tab.on{background:#fff;border-bottom-color:#fff;color:#0969da;font-weight:600}
.panel{margin:0 24px 24px;background:#fff;border:1px solid #d0d7de;border-radius:0 6px 6px 6px;
       padding:16px}
.toolbar{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:12px}
.toolbar .grow{flex:1}
button{font:inherit;padding:5px 12px;border:1px solid #d0d7de;border-radius:6px;background:#f6f8fa;
       cursor:pointer}
button:hover{background:#eef1f4}
button.danger{color:#cf222e;border-color:#ffcecb;background:#fff5f5}
button.danger:hover{background:#ffe9e9}
a.act{color:#0969da;text-decoration:none;margin-right:10px;white-space:nowrap}
a.act:hover{text-decoration:underline}
a.act.warn{color:#cf222e}
table{width:100%;border-collapse:collapse}
th,td{padding:8px 10px;border-bottom:1px solid #eaeef2;text-align:left;white-space:nowrap}
th{background:#f6f8fa;font-weight:600;color:#57606a;font-size:13px}
tr.latest td{background:#f0f9ff}
tr:hover td{background:#fafbfc}
td.num{text-align:right;font-variant-numeric:tabular-nums}
.pill{display:inline-block;padding:1px 8px;border-radius:10px;font-size:12px}
.pill.full{background:#ddf4e4;color:#1a7f37}
.pill.debug{background:#fff4d6;color:#9a6700}
.pill.latest{background:#0969da;color:#fff}
.empty{padding:32px;text-align:center;color:#57606a;line-height:2}
code{background:#f6f8fa;border:1px solid #eaeef2;border-radius:4px;padding:1px 5px;font-size:13px}
footer{padding:0 24px 24px;color:#57606a;font-size:12px}
.runbar{display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin:0 0 12px;
        padding:10px 12px;background:#f6f8fa;border:1px solid #eaeef2;border-radius:6px}
.runbar label{display:inline-flex;align-items:center;gap:5px;cursor:pointer}
button.primary{background:#1f883d;border-color:#1a7f37;color:#fff;font-weight:600}
button.primary:hover{background:#1a7f37}
button.primary:disabled{background:#94d3a2;border-color:#94d3a2;cursor:not-allowed}
.panel-job{margin:0 0 14px;padding:12px;border-radius:6px;border:1px solid #d0d7de;background:#fff}
.panel-job.running{border-color:#54aeff;background:#f0f7ff}
.panel-job.passed{border-color:#94d3a2;background:#f2fbf4}
.panel-job.failed,.panel-job.error{border-color:#ffcecb;background:#fff5f5}
.panel-job .head{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.panel-job pre{max-height:220px;overflow:auto;background:#1f2328;color:#d0d7de;padding:10px;
               border-radius:6px;font-size:12px;margin:10px 0 0}
.hint{color:#57606a;font-size:12px}
"""

_JS = """
const PROJ = %(proj)s;
const MODULES = %(mods)s;
const CANRUN = %(canrun)s;
const FINAL = ['passed','failed','error','stopped','interrupted'];
const KIND = {passed:'通过', failed:'有失败', error:'无法执行', stopped:'已停止',
              interrupted:'中断', running:'运行中', pending:'启动中'};
let reloaded = false;          // 本次页面实例内只自动刷新一次
let sawRunning = false;        // 本页是否亲眼看到过"运行中"——只有真看到过才在结束时刷新

function selRows(){return Array.from(document.querySelectorAll('input.row:checked'));}
function updCount(){var n=selRows().length;var e=document.getElementById('seln');
  if(e){e.textContent=n;} var b=document.getElementById('delbtn'); if(b){b.disabled=(n===0);}}
function fmtB(b){b=Number(b)||0;return b>=1048576?(b/1048576).toFixed(1)+' MB':(b/1024).toFixed(0)+' KB';}
async function postDelete(body){
  const r = await fetch('/api/delete',{method:'POST',headers:{'Content-Type':'application/json'},
                                      body:JSON.stringify(body)});
  let j = {}; try { j = await r.json(); } catch(e) { j = {error:'HTTP '+r.status}; }
  if(!r.ok){ alert('删除失败：'+(j.error||r.status)); return; }
  alert('已删除 '+j.deleted+' 个版本，释放 '+fmtB(j.freed_bytes));
  location.reload();
}
function delSel(){
  const v = selRows().map(x=>x.dataset.v);
  if(!v.length){ alert('请先勾选要删除的版本'); return; }
  if(!confirm('确认删除选中的 '+v.length+' 个版本？\\n删除后不可恢复。')) return;
  postDelete({project:PROJ, versions:v});
}
function delKind(k,label){
  if(!confirm('确认删除该项目全部「'+label+'」运行？\\n删除后不可恢复。')) return;
  postDelete({project:PROJ, kind:k});
}
function delOne(v){
  if(!confirm('确认删除版本 '+v+'？\\n删除后不可恢复。')) return;
  postDelete({project:PROJ, versions:[v]});
}

// ---- 运行 ----
function pickedModules(){
  return Array.from(document.querySelectorAll('input.mod:checked')).map(x=>x.dataset.id);
}
function runNow(){
  if(!CANRUN){ return; }
  const mods = MODULES.length ? pickedModules() : [];
  if(MODULES.length && !mods.length){ alert('至少勾选一个模块'); return; }
  const slow = document.getElementById('slow') && document.getElementById('slow').checked;
  const names = MODULES.filter(m=>mods.indexOf(m.id)>=0).map(m=>m.name).join(' / ') || '全部';
  const msg = '即将在台架上运行：\\n\\n项目：' + document.getElementById('projname').textContent +
              '\\n模块：' + names + '\\n含 slow：' + (slow?'是（可能数小时）':'否') +
              '\\n\\n注意：DUT 会真实上电，运行期间请勿手动操作台架。\\n确认开始？';
  if(!confirm(msg)) return;
  const btn = document.getElementById('runbtn');
  if(btn){ btn.disabled = true; btn.textContent = '启动中…'; }
  fetch('/api/run',{method:'POST',headers:{'Content-Type':'application/json'},
                    body:JSON.stringify({project:PROJ, modules:mods, include_slow:slow})})
    .then(async r=>{ let j={}; try{j=await r.json();}catch(e){}
                     if(!r.ok){ alert('启动失败：'+(j.error||('HTTP '+r.status))); }
                     pollRun(); })
    .catch(e=>alert('启动失败：'+e));
}
function stopRun(){
  if(!confirm('确认停止当前运行？\\n正在执行的用例会被强制中断。')) return;
  fetch('/api/run/stop',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'})
    .then(()=>pollRun());
}
function fmtDur(sec){
  sec = Math.max(0, Math.round(sec));
  const m = Math.floor(sec/60), s = sec - m*60;
  return m ? (m + ' 分 ' + s + ' 秒') : (s + ' 秒');
}
function renderJob(j){
  const box = document.getElementById('runpanel');
  if(!box) return;
  const job = j.job, bench = j.bench || {};
  if(!job){
    box.innerHTML = bench.busy
      ? '<div class="panel-job"><div class="head"><b style="color:#cf222e">台架被占用</b>' +
        '<span class="hint">pid ' + (bench.holder?bench.holder.pid:'?') + ' / ' +
        (bench.holder?bench.holder.user:'?') + ' / ' +
        (bench.holder?bench.holder.time:'?') + '（可能是别人在用，也可能是命令行正在跑）</span></div></div>'
      : '';
    if(CANRUN){ setRunEnabled(true); }
    return;
  }
  const running = FINAL.indexOf(job.status) < 0;
  if(running){ sawRunning = true; }
  // 任务是全局单槽位：别的项目正在跑要显示（否则用户不知道台架为何被动），
  // 但别的项目已经结束的旧任务与本页无关，直接不显示
  if(job.project !== PROJ && !running){
    box.innerHTML = '';
    if(CANRUN){ setRunEnabled(true); }
    return;
  }
  const cls = running ? 'running' : (job.status === 'passed' ? 'passed' : 'failed');
  let dur = '';
  if(job.started_at){
    const t0 = new Date(job.started_at).getTime();
    if(!isNaN(t0)){ dur = fmtDur(((job.ended_at ? new Date(job.ended_at).getTime() : Date.now()) - t0)/1000); }
  }
  let head = '<b>' + (KIND[job.status] || job.status) + '</b>' +
             '<span class="hint">' + job.project +
             (job.modules && job.modules.length ? ' · ' + job.modules.join(',') : '') +
             (job.include_slow ? ' · 含 slow' : '') +
             ' · ' + dur + (job.exit_code !== null && job.exit_code !== undefined ? ' · exit ' + job.exit_code : '') +
             '</span>';
  if(job.project !== PROJ){ head = '<b style="color:#9a6700">其他项目正在运行</b> ' + head; }
  let acts = '';
  if(running){ acts += '<button class="danger" onclick="stopRun()">停止</button>'; }
  if(job.report_version){
    acts += '<a class="act" href="/r/' + job.project + '/' + job.report_version + '/" target="_blank">查看本次报告</a>';
  }
  box.innerHTML = '<div class="panel-job ' + cls + '"><div class="head">' + head +
                  '<span class="grow" style="flex:1"></span>' + acts + '</div>' +
                  (job.note ? '<div class="hint">' + job.note + '</div>' : '') +
                  '<pre id="joblog">加载日志…</pre></div>';
  if(CANRUN){ setRunEnabled(!running); }
  loadLog();
  // 只在"本页看到过运行中 → 现在结束"时刷新一次（新版本落到表格顶部）。
  // 必须带 sawRunning：任务早已结束的页面若也刷新，每次重载后又满足条件 → 无限刷新。
  if(!running && job.report_version && sawRunning && !reloaded){
    reloaded = true;
    setTimeout(function(){ location.reload(); }, 2500);
  }
}
function setRunEnabled(on){
  const b = document.getElementById('runbtn');
  if(b){ b.disabled = !on; b.textContent = '▶ 运行'; }
}
async function loadLog(){
  const pre = document.getElementById('joblog');
  if(!pre) return;
  try{
    const r = await fetch('/api/run/log?lines=120');
    const t = await r.text();
    pre.textContent = t || '（暂无输出）';
    pre.scrollTop = pre.scrollHeight;
  }catch(e){ pre.textContent = '（日志读取失败）'; }
}
async function pollRun(){
  if(!CANRUN){ return; }
  try{
    const r = await fetch('/api/run/status');
    renderJob(await r.json());
  }catch(e){}
}
if(CANRUN){ pollRun(); setInterval(pollRun, 3000); }
"""


def _render_dashboard(project, projects, versions):
    pname = rh.project_name(REPO_ROOT, project)
    tabs = "".join(
        '<a class="tab%s" href="/?project=%s">%s</a>'
        % (" on" if p["id"] == project else "", html.escape(p["id"]), html.escape(p["name"]))
        for p in projects)
    # 框架级单测（tests/）不在 projects/ 下，有历史时才补一个标签，否则切不回来
    if rh.list_versions(REPO_ROOT, "framework"):
        tabs += ('<a class="tab%s" href="/?project=framework">框架单元测试</a>'
                 % (" on" if project == "framework" else ""))
    if not tabs:
        tabs = '<span class="tab on">暂无项目目录</span>'

    if versions:
        rows = []
        for i, v in enumerate(versions):
            c = v.get("counts") or {}
            kind = v.get("kind", "full")
            pill = ('<span class="pill debug">调试</span>' if kind == "debug"
                    else '<span class="pill full">全量</span>')
            if i == 0:
                pill += ' <span class="pill latest">最新</span>'
            rows.append(
                '<tr class="%s">'
                '<td><input type="checkbox" class="row" data-v="%s" onchange="updCount()"></td>'
                '<td>%s</td><td>%s</td>'
                '<td class="num">%s</td><td class="num">%s</td><td class="num">%s</td>'
                '<td class="num">%s</td><td>%s</td><td>%s</td>'
                '<td><a class="act" href="/r/%s/%s/" target="_blank">查看</a>'
                '<a class="act" href="/api/export?project=%s&version=%s&format=single">导出报告</a>'
                '<a class="act" href="/api/export?project=%s&version=%s&format=html">导出HTML</a>'
                '<a class="act warn" href="#" onclick="delOne(\'%s\');return false;">删除</a></td>'
                '</tr>' % (
                    "latest" if i == 0 else "", html.escape(v["version"]),
                    _fmt_time(v["version"]), pill,
                    html.escape(str((c or {}).get("passed", "-"))),
                    html.escape(str((c or {}).get("failed", "-"))),
                    html.escape(str((c or {}).get("skipped", "-"))),
                    ("%ss" % c["duration_s"]) if (c or {}).get("duration_s") else "-",
                    html.escape(v.get("git_head") or "-"),
                    _fmt_bytes(_ver_size(v)),
                    html.escape(project), html.escape(v["version"]),
                    html.escape(project), html.escape(v["version"]),
                    html.escape(project), html.escape(v["version"]),
                    html.escape(v["version"])))
        body = ("<table><thead><tr>"
                '<th style="width:34px"><input type="checkbox" id="all" onclick="'
                'document.querySelectorAll(\'input.row\').forEach(function(x){x.checked='
                'document.getElementById(\'all\').checked;});updCount();"></th>'
                "<th>时间</th><th>类型</th><th>通过</th><th>失败</th><th>跳过</th>"
                "<th>耗时</th><th>git</th><th>大小</th><th>操作</th></tr></thead><tbody>"
                + "".join(rows) + "</tbody></table>")
    else:
        cfg = rh.load_cfg(REPO_ROOT)
        body = ('<div class="empty">该项目还没有历史版本。<br>'
                '跑一次用例即自动留档；'
                '想先把仓库里现存的那一轮导进来：<br>'
                '<code>python tools\\export_report.py --import-current --project %s</code><br>'
                '<span style="color:#8b949e">留档位置：%s（全量 %s 份 / 调试 %s 份）</span></div>'
                % (html.escape(project), html.escape(rh.history_root(REPO_ROOT, cfg)),
                   cfg.get("keep"), cfg.get("debug_keep")))

    total = sum(_ver_size(v) for v in versions)
    proj_json = json.dumps(project if project != "framework" else "framework")

    # 运行栏：hil 项目按模块勾选（默认全选），框架自检只有 tests/-m "not hil"
    mods = []
    runnable = False
    if project == "framework":
        runnable = True
        mods_html = '<span class="hint">框架自检：tests/ · 排除 hil（不需要台架）</span>'
    else:
        mods = next((p["modules"] for p in projects if p["id"] == project), [])
        runnable = project in [p["id"] for p in projects]
        mods_html = "".join(
            '<label><input type="checkbox" class="mod" data-id="%s" checked> %s</label>'
            % (html.escape(m["id"]), html.escape(m["name"])) for m in mods)
        if not mods:
            mods_html = '<span class="hint">该项目未登记模块（project.yaml modules 为空）</span>'
    runbar = ("""<div class="runbar">
      <b>模块</b> %s
      <label><input type="checkbox" id="slow"> 含 slow（耐久/长跑）</label>
      <button id="runbtn" class="primary" onclick="runNow()">▶ 运行</button>
      <span class="hint">后台任务，关掉页面不会中断；同一时刻只能跑一个</span>
    </div>
    <div id="runpanel"></div>""" % mods_html) if runnable else ""

    return """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>报告中心 · %(pname)s</title><style>%(css)s</style></head><body>
<header><h1>报告中心</h1><span class="sub">HIL 测试报告 · 端口 %(port)s · 每次运行自动留档</span></header>
<div class="tabs">%(tabs)s</div>
<div class="panel">
  <div class="toolbar">
    <b id="projname">%(pname)s</b>
    <span style="color:#57606a">%(n)d 个版本 · 共 %(total)s</span>
    <span class="grow"></span>
    <a class="act" href="/r/%(pid)s/latest/" target="_blank">查看最新报告</a>
    <button id="delbtn" class="danger" disabled onclick="delSel()">删除选中(<span id="seln">0</span>)</button>
    <button class="danger" onclick="delKind('debug','调试')">删除全部调试运行</button>
    <button onclick="location.reload()">刷新</button>
  </div>
  %(runbar)s
  %(body)s
</div>
<footer>历史数据存于 %(root)s（不可再生）；点「查看」时现渲染的网页缓存只留最近 %(gen)s 份，删了会自动重建。</footer>
<script>%(js)s</script>
</body></html>""" % {
        "pname": html.escape(pname), "css": _CSS, "tabs": tabs, "port": PORT,
        "n": len(versions), "total": _fmt_bytes(total), "body": body,
        "pid": html.escape(project), "root": html.escape(rh.history_root(REPO_ROOT)),
        "gen": rh.load_cfg(REPO_ROOT).get("max_generated", 3),
        "runbar": runbar,
        "js": _JS % {"proj": proj_json,
                     "mods": json.dumps(mods, ensure_ascii=False),
                     "canrun": "true" if runnable else "false"},
    }


# ---------------------------------------------------------------- HTTP

class Handler(BaseHTTPRequestHandler):
    server_version = "HILReportCenter/1.0"

    def log_message(self, *args, **kwargs):
        """pythonw 无窗口运行时 sys.stderr=None，基类逐请求写 stderr 会崩 —— 静默。"""
        pass

    # ---- 基础输出 ----
    def _send(self, status, body, ctype="text/html; charset=utf-8", headers=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        try:
            self.wfile.write(body)
        except Exception:
            pass

    def _json(self, obj, status=200):
        self._send(status, json.dumps(obj, ensure_ascii=False, indent=1),
                   "application/json; charset=utf-8")

    def _fail(self, status, msg):
        self._json({"error": msg}, status)

    # ---- 路由 ----
    def do_GET(self):
        try:
            u = urlsplit(self.path)
            path = unquote(u.path)
            qs = parse_qs(u.query)

            if path in ("/", "/index.html"):
                return self._page(qs)
            if path == "/favicon.ico":
                return self._send(204, b"", "image/x-icon")
            if path == "/api/projects":
                return self._api_projects()
            if path == "/api/versions":
                return self._api_versions(qs)
            if path == "/api/export":
                return self._api_export(qs)
            if path == "/api/run/status":
                return self._api_run_status()
            if path == "/api/run/log":
                return self._api_run_log(qs)
            if path.startswith("/r/"):
                return self._serve_version(path[len("/r/"):])
            return self._send(404, "<h3>404</h3><p>没有这个地址，返回 <a href='/'>报告中心</a></p>")
        except Exception:
            log("GET %s 异常: %s" % (self.path, traceback.format_exc()))
            return self._send(500, "<h3>500 内部错误</h3><pre>%s</pre>"
                              % html.escape(traceback.format_exc()[-800:]))

    def do_POST(self):
        try:
            u = urlsplit(self.path)
            route = u.path.rstrip("/")
            if route not in ("/api/delete", "/api/run", "/api/run/stop"):
                return self._fail(404, "没有这个接口")
            try:
                n = int(self.headers.get("Content-Length") or 0)
                payload = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            except Exception:
                return self._fail(400, "请求体不是合法 JSON")
            if route == "/api/delete":
                return self._api_delete(payload)
            if route == "/api/run":
                return self._api_run(payload)
            return self._api_run_stop(payload)
        except Exception:
            log("POST %s 异常: %s" % (self.path, traceback.format_exc()))
            return self._fail(500, "内部错误（详见 reports/serve_report.log）")

    # ---- 页面 ----
    def _page(self, qs):
        want = (qs.get("project") or [None])[0]
        projects = rh.discover_projects(REPO_ROOT)
        known = [p["id"] for p in projects]

        if valid_project(want) and want not in known:
            known.append(want)                  # 允许看已被删除目录的历史项目
        if not valid_project(want):
            # 未指定项目：优先挑有历史的（含 framework），否则第一个项目
            with_hist = [p["id"] for p in projects if rh.list_versions(REPO_ROOT, p["id"])]
            if not with_hist and rh.list_versions(REPO_ROOT, "framework"):
                with_hist = ["framework"]
            want = (with_hist or known or ["framework"])[0]
        versions = rh.list_versions(REPO_ROOT, want)
        self._send(200, _render_dashboard(want, projects, versions))

    # ---- 接口 ----
    def _api_projects(self):
        out = []
        for p in rh.discover_projects(REPO_ROOT):
            vs = rh.list_versions(REPO_ROOT, p["id"])
            out.append({**p, "versions": len(vs),
                        "latest": vs[0]["version"] if vs else None,
                        "bytes": sum(_ver_size(v) for v in vs)})
        fw = rh.list_versions(REPO_ROOT, "framework")
        if fw:
            out.append({"id": "framework", "name": "框架单元测试", "modules": [],
                        "versions": len(fw), "latest": fw[0]["version"],
                        "bytes": sum(_ver_size(v) for v in fw)})
        self._json(out)

    def _api_versions(self, qs):
        project = (qs.get("project") or [None])[0]
        if not valid_project(project):
            return self._fail(400, "project 参数缺失或非法")
        vs = []
        for v in rh.list_versions(REPO_ROOT, project):
            item = {k: v.get(k) for k in
                    ("version", "project", "project_name", "kind", "started_at", "finished_at",
                     "exit_status", "counts", "argv", "git_head", "host", "user")}
            item["bytes"] = _ver_size(v)
            item["url"] = "/r/%s/%s/" % (project, v["version"])
            item["single"] = "/api/export?project=%s&version=%s&format=single" % (project, v["version"])
            item["zip"] = "/api/export?project=%s&version=%s&format=zip" % (project, v["version"])
            item["html"] = "/api/export?project=%s&version=%s&format=html" % (project, v["version"])
            vs.append(item)
        self._json({"project": project, "count": len(vs), "versions": vs})

    def _api_export(self, qs):
        project = (qs.get("project") or [None])[0]
        version = (qs.get("version") or ["latest"])[0]
        fmt = ((qs.get("format") or ["single"])[0] or "single").lower()
        if not valid_project(project):
            return self._fail(400, "project 参数缺失或非法")
        if not valid_version(version):
            return self._fail(400, "version 参数非法")
        if fmt not in ("zip", "html", "single"):
            return self._fail(400, "format 只支持 single / html / zip")
        try:
            if fmt == "single":
                # Allure 官方单文件报告：一个 HTML 双击即开，不需要 bat / 本地服务
                data, name = rh.build_single_file(REPO_ROOT, project, version)
                log("导出单文件 %s/%s -> %s (%d B)" % (project, version, name, len(data)))
                return self._send(200, data, "text/html; charset=utf-8",
                                  {"Content-Disposition": 'attachment; filename="%s"' % name})
            if fmt == "html":
                data = rh.build_html(REPO_ROOT, project, version)
                name = "%s_%s.html" % (project, version)
                return self._send(200, data, "text/html; charset=gb2312",
                                  {"Content-Disposition": 'attachment; filename="%s"' % name})
            path, name = rh.build_zip(REPO_ROOT, project, version)
            with open(path, "rb") as f:
                data = f.read()
            log("导出 ZIP %s/%s -> %s (%d B)" % (project, version, name, len(data)))
            return self._send(200, data, "application/zip",
                              {"Content-Disposition": 'attachment; filename="%s"' % name})
        except rh.ReportBusy as e:
            return self._fail(409, str(e))
        except rh.ReportError as e:
            return self._fail(400, str(e))
        except Exception as e:
            log("导出失败 %s/%s: %s" % (project, version, traceback.format_exc()))
            return self._fail(500, "导出失败: %s" % e)

    def _api_delete(self, payload):
        project = payload.get("project")
        if not valid_project(project):
            return self._fail(400, "project 参数缺失或非法")
        versions = payload.get("versions") or []
        kind = payload.get("kind")
        all_ = bool(payload.get("all"))
        if not (versions or kind or all_):
            return self._fail(400, "未指定删除范围")
        if kind and kind not in ("debug", "full"):
            return self._fail(400, "kind 只支持 debug / full")
        for v in versions:
            if not valid_version(v) or v == "latest":
                return self._fail(400, "version 参数非法: %s" % v)
        try:
            r = rh.delete_versions(REPO_ROOT, project, versions=versions, kind=kind,
                                   all_=all_, by=(self.client_address or ("",))[0])
        except rh.ReportBusy as e:
            return self._fail(409, str(e))
        except rh.ReportError as e:
            return self._fail(400, str(e))
        log("删除 %s: versions=%s kind=%s all=%s -> %d 个, 释放 %d B"
            % (project, versions, kind, all_, len(r["deleted"]), r["freed_bytes"]))
        self._json({"deleted": len(r["deleted"]), "versions": r["deleted"],
                    "freed_bytes": r["freed_bytes"]})

    # ---- 运行任务 ----
    def _api_run(self, payload):
        project = payload.get("project")
        if not valid_project(project):
            return self._fail(400, "project 参数缺失或非法")
        modules = payload.get("modules") or []
        if not isinstance(modules, list) or not all(isinstance(m, str) for m in modules):
            return self._fail(400, "modules 必须是模块 id 数组")
        try:
            job = rj.start(REPO_ROOT, project, modules, bool(payload.get("include_slow")))
        except rj.RunBusy as e:
            return self._fail(409, str(e))
        except rj.RunError as e:
            return self._fail(400, str(e))
        log("启动运行 %s modules=%s slow=%s -> job %s pid %s: %s"
            % (project, modules, bool(payload.get("include_slow")), job["id"],
               job["pid"], " ".join(job["argv"])))
        self._json(job, 202)

    def _api_run_stop(self, payload):
        try:
            job = rj.stop(REPO_ROOT, payload.get("job_id"))
        except rj.RunError as e:
            return self._fail(400, str(e))
        log("停止运行 job %s（pid %s）" % (job.get("id"), job.get("pid")))
        self._json(job)

    def _api_run_status(self):
        self._json({"job": rj.status(REPO_ROOT), "bench": rj.bench_state(REPO_ROOT)})

    def _api_run_log(self, qs):
        job_id = (qs.get("job_id") or [None])[0]
        try:
            lines = int((qs.get("lines") or ["120"])[0])
        except ValueError:
            lines = 120
        if job_id and not valid_version(job_id):
            return self._fail(400, "job_id 非法")
        self._send(200, rj.tail_log(REPO_ROOT, job_id, min(max(lines, 10), 2000)),
                   "text/plain; charset=utf-8")

    # ---- 静态：某版本的 Allure 站点 ----
    def _serve_version(self, rest):
        parts = rest.split("/", 2)
        if len(parts) < 2:
            return self._fail(400, "路径应为 /r/<project>/<version>/...")
        project, version = parts[0], parts[1]
        rel = parts[2] if len(parts) > 2 else ""
        if not valid_project(project):
            return self._fail(400, "项目名非法")
        if not valid_version(version):
            return self._fail(400, "版本号非法")
        try:
            root = rh.ensure_report(REPO_ROOT, project, version)
        except rh.ReportBusy as e:
            return self._fail(503, "%s（请几秒后刷新）" % e)
        except rh.ReportError as e:
            return self._fail(404, str(e))

        target = os.path.abspath(os.path.join(root, rel or "index.html"))
        root_abs = os.path.abspath(root)
        if not (target == root_abs or target.startswith(root_abs + os.sep)):
            return self._fail(403, "越界路径")
        if os.path.isdir(target):
            target = os.path.join(target, "index.html")
        if not os.path.isfile(target):
            return self._fail(404, "文件不存在: %s" % rel)

        ctype = mimetypes.guess_type(target)[0] or "application/octet-stream"
        if ctype.startswith("text/"):
            ctype += "; charset=utf-8"
        try:
            with open(target, "rb") as f:
                data = f.read()
        except OSError as e:
            return self._fail(500, "读取失败: %s" % e)
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        try:
            self.wfile.write(data)
        except Exception:
            pass


def main():
    # 首次部署时先占位，避免根路径 404
    os.makedirs(os.path.join(REPO_ROOT, "allure-report"), exist_ok=True)

    # 单实例：绑定失败 = 已有服务在跑，安静退出（计划任务重复触发不会起第二份）
    try:
        httpd = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    except OSError as e:
        print(f"[skip] 端口 {PORT} 已被占用（{e}），假定服务已在运行")
        return 0

    log("服务启动 :%d -> 报告中心（历史目录 %s）"
        % (PORT, rh.history_root(REPO_ROOT)))
    print(f"[ok] http://0.0.0.0:{PORT} -> 报告中心")
    for ip in lan_ips():
        print(f"     http://{ip}:{PORT}")
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
