#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""两端口交互元素 id 集合双向差集断言（简报标准 11 的 id 半边）。纯标准库。

为什么需要它：标准 11 明文要求 `python3 tools/check_ids.py` 断言「两端口交互元素 id
集合差集为空」。sample_route_status.py 只比对路由状态码，不覆盖 id。

本脚本对每个端口做两路取集合，再做双向差集（removed = baseline 有而运行期没有，
added = 运行期有而 baseline 没有）：

  8080（SPA，id 分散在 index.html + app/*.js 的模板字符串里）
    [assets] 主判定：从服务端「实际发出的文件」抓 id —— GET / 拿页面壳，GET /app/main.js
             起按 import/import() 递归抓模块，用与 gen_baseline_ids.py 完全相同的正则提取。
             比对的是构建产物里真正下发给浏览器的代码，不是仓库工作区。
    [dom]    辅判定：CDP 渲染首屏后的真实 document DOM。SPA 只渲染当前路由，因此这里只断言
             「DOM 里的 id 不得出现 baseline 之外的新 id」（added 必须为空），
             baseline 里未渲染的 id 逐条列为 informational，不当失败。
  9500（launcher 面板，单页静态 HTML）
    [dom]    主判定：CDP 渲染后 DOM 全部 id 与 baseline 双向差集，必须为空。
    [source] 兜底：直接解析服务端发出的 GET / HTML。

新增 id 的声明机制：本任务按简报 7/8 要求给两端口加了语言切换锚点 `lang-switch`，
它在 baseline（改前）里当然不存在。所以 added 允许出现在 `--allow-added`（默认
`lang-switch`）中，并逐条打印成 declared；不在此列的 added 仍判失败。

跨机器用法（9500 本机起不来，走两级）：
    # Windows（在仓库根，launcher 已起在 9500）
    python tools\\check_ids.py --port 9500 --dump-ids ids_9500.json
    # 把 ids_9500.json 带回本机
    python3 tools/check_ids.py --port 9500 --from-json ids_9500.json

用法：
    python3 tools/check_ids.py                      # 8080，默认 http://127.0.0.1:8080
    python3 tools/check_ids.py --port 8080 --url http://127.0.0.1:8080
    python3 tools/check_ids.py --port 9500 --url http://127.0.0.1:9500
    python3 tools/check_ids.py --port 8080 --no-dom          # 只要静态资源那一路
    python3 tools/check_ids.py --port 8080 --dump-ids out.json

退出码：0 = 差集为空（除已声明新增）；1 = 有 removed 或未声明的 added；2 = 环境问题
（服务没起 / 拿不到 CDP / baseline 读不了）。环境问题不算通过，也不会假通过。
"""
import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urljoin

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from check_page import WS, cdp_http  # noqa: E402  复用纯标准库 WebSocket 客户端

# 与 gen_baseline_ids.py 完全相同的两条提取正则（保证同口径可比）
ADMIN_ID_ATTR = re.compile(r"""id\s*:\s*(['"])([A-Za-z][\w.-]*)\1""")
ADMIN_ID_HTML = re.compile(r"""id="([A-Za-z][\w.-]*)\"""")
IMPORT_SPEC = re.compile(
    r"""(?:from\s+['"]([^'"]+)['"]|import\s*\(\s*['"]([^'"]+)['"]\s*\)|import\s+['"]([^'"]+)['"])""")

INTERACTIVE_TAGS = {"button", "input", "select", "textarea", "a", "form", "details", "summary"}
ID_LOOKS_INTERACTIVE = re.compile(
    r"(btn|Button|toggle|menu|Menu|input|Input|select|Select|login|reload|tab|switch|Switch|"
    r"save|Save|cancel|search|filter|upload|download|link|Link|nav|Nav)", re.IGNORECASE)

DEFAULT_BASELINE = os.path.join(HERE, "baseline_ids.json")
DEFAULT_ALLOW = "lang-switch"

DOM_COLLECT_JS = r"""
JSON.stringify((function(){
  var out = [];
  var nodes = document.querySelectorAll('[id]');
  for (var i = 0; i < nodes.length; i++) {
    var e = nodes[i];
    out.push({id: e.id, tag: (e.tagName || '').toLowerCase(),
              text: (e.innerText || '').trim().slice(0, 60)});
  }
  return out;
})())
"""


class PanelIds(HTMLParser):
    """从 HTML 源里取 id（标签名 + 行号），用于 9500 这类静态页。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("id"):
            self.rows.append({"id": a["id"], "tag": tag, "line": self.getpos()[0]})


def http_get(url, timeout=10):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.status, r.read().decode("utf-8", "replace")


def find_browser():
    exe = os.environ.get("RF4_BROWSER")
    if exe and os.path.exists(exe):
        return exe
    cands = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for c in cands:
        if os.path.exists(c):
            return c
    for name in ("chromium", "chromium-browser", "google-chrome", "chrome", "msedge"):
        p = shutil.which(name)
        if p:
            return p
    return None


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class CdpSession:
    """优先用平台 CDP（RAKAZO_CDP_PORT，默认 9222）；没有就自己拉一个浏览器。"""

    def __init__(self):
        self.proc = None
        self.prof = None
        self.port = None

    def open(self):
        env_port = int(os.environ.get("RAKAZO_CDP_PORT", "9222") or 9222)
        try:
            cdp_http(env_port, "/json/version")
            self.port = env_port
            return True
        except Exception:
            pass
        exe = find_browser()
        if not exe:
            return False
        self.port = free_port()
        self.prof = tempfile.mkdtemp(prefix="rf4-ids-")
        cmd = [exe, "--headless=new", "--disable-gpu", "--no-first-run",
               "--no-default-browser-check", "--remote-debugging-port=%d" % self.port,
               "--user-data-dir=" + self.prof, "about:blank"]
        try:
            self.proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            return False
        deadline = time.time() + 20
        while time.time() < deadline:
            try:
                cdp_http(self.port, "/json/version")
                return True
            except Exception:
                time.sleep(0.4)
        return False

    def close(self):
        if self.proc:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=5)
            except Exception:
                pass
        if self.prof:
            shutil.rmtree(self.prof, ignore_errors=True)


def dom_ids(url, port):
    """CDP 渲染后取 DOM 全部带 id 的元素。"""
    target = cdp_http(port, "/json/new?about:blank", method="PUT")
    ws = WS("127.0.0.1", port, "/devtools/page/" + target["id"])
    try:
        mid = 0

        def call(method, params):
            nonlocal mid
            mid += 1
            ws.send({"id": mid, "method": method, "params": params})
            while True:
                msg = json.loads(ws.recv())
                if msg.get("id") == mid:
                    return msg

        call("Page.enable", {})
        call("Page.navigate", {"url": url})
        deadline = time.time() + 25
        while time.time() < deadline:
            try:
                ws.sock.settimeout(3)
                msg = json.loads(ws.recv())
            except Exception:
                break
            if msg.get("method") == "Page.loadEventFired":
                break
        time.sleep(2.0)  # SPA 模块 + 首屏 API 渲染稳定
        out = call("Runtime.evaluate", {"expression": DOM_COLLECT_JS, "returnByValue": True})
        val = out["result"]["result"].get("value") or "[]"
        return json.loads(val), None
    except Exception as e:
        return None, str(e)
    finally:
        try:
            ws.sock.close()
        except Exception:
            pass
        try:
            cdp_http(port, "/json/close/" + target["id"])
        except Exception:
            pass


def admin_asset_ids(base):
    """8080：抓服务端实际发出的页面壳 + 全部可递归到达的 ES 模块，用 baseline 同款正则取 id。"""
    _st, shell = http_get(base)
    rows = {}
    shell_parser = PanelIds()
    shell_parser.feed(shell)
    for r in shell_parser.rows:
        rows.setdefault(r["id"], {"id": r["id"], "tag": r["tag"], "from": "GET /"})
    todo = [urljoin(base, "app/main.js")]
    fetched = set()
    while todo:
        u = todo.pop()
        if u in fetched:
            continue
        fetched.add(u)
        try:
            _s, txt = http_get(u)
        except Exception:
            continue
        rel = u[len(base):] if u.startswith(base) else u
        for m in ADMIN_ID_ATTR.finditer(txt):
            tag = None
            for hm in re.finditer(r"""h\(\s*['"]([a-zA-Z][a-zA-Z0-9]*)['"]""",
                                  txt[max(0, m.start() - 400):m.start()]):
                tag = hm.group(1)
            rows.setdefault(m.group(2), {"id": m.group(2), "tag": tag or "unknown", "from": rel})
        for m in IMPORT_SPEC.finditer(txt):
            spec = m.group(1) or m.group(2) or m.group(3)
            if spec and spec.startswith("."):
                todo.append(urljoin(u, spec))
    return list(rows.values()), len(fetched)


def launcher_source_ids(base):
    """9500：服务端发出的 / 就是整页 HTML，直接解析 id（CDP 不可用时的兜底）。"""
    _st, html = http_get(base)
    p = PanelIds()
    p.feed(html)
    seen = {}
    for r in p.rows:
        seen.setdefault(r["id"], r)
    return list(seen.values())


def is_interactive(row):
    tag = (row.get("tag") or "").lower()
    return tag in INTERACTIVE_TAGS or bool(ID_LOOKS_INTERACTIVE.search(row.get("id", "")))


def diff(base_rows, run_rows, allow_added):
    base = {r["id"]: r for r in base_rows}
    run = {r["id"]: r for r in run_rows}
    removed = sorted(set(base) - set(run))
    added = sorted(set(run) - set(base))
    declared = [i for i in added if i in allow_added]
    undeclared = [i for i in added if i not in allow_added]
    return base, run, removed, added, declared, undeclared


def report_section(name, base_rows, run_rows, allow_added, extra=""):
    base, run, removed, added, declared, undeclared = diff(base_rows, run_rows, allow_added)
    print("[%s] %s" % (name, extra))
    print("  baseline ids: %d (interactive %d)"
          % (len(base), sum(1 for r in base.values() if is_interactive(r))))
    print("  runtime  ids: %d (interactive %d)"
          % (len(run), sum(1 for r in run.values() if is_interactive(r))))
    print("  removed: %d" % len(removed))
    for i in removed:
        print("    - %s (%s in baseline, tag=%s)"
              % (i, base[i].get("file", base[i].get("from", "?")), base[i].get("tag")))
    print("  added: %d (declared %d / undeclared %d)" % (len(added), len(declared), len(undeclared)))
    for i in added:
        mark = "declared" if i in allow_added else "UNDECLARED"
        print("    + %s [%s] tag=%s" % (i, mark, run[i].get("tag")))
    ok = not removed and not undeclared
    print("  verdict: %s" % ("PASS" if ok else "FAIL"))
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", choices=["8080", "9500"], default="8080")
    ap.add_argument("--url", default=None)
    ap.add_argument("--baseline", default=DEFAULT_BASELINE)
    ap.add_argument("--allow-added", default=DEFAULT_ALLOW,
                    help="允许的新增 id（逗号分隔，默认 lang-switch：简报 7/8 要求的语言切换锚点）")
    ap.add_argument("--no-dom", action="store_true", help="跳过 CDP，只跑静态资源/HTML 源那一路")
    ap.add_argument("--dump-ids", metavar="FILE", help="把运行期 id 集合导出 JSON（跨机比对用）")
    ap.add_argument("--from-json", metavar="FILE", help="用导出的 id JSON 代替现场渲染")
    a = ap.parse_args()

    allow_added = {x.strip() for x in a.allow_added.split(",") if x.strip()}
    base_url = a.url or ("http://127.0.0.1:%s/" % a.port)

    try:
        data = json.loads(open(a.baseline, encoding="utf-8").read())
        base_rows = data["ports"][a.port]["ids"]
    except Exception as e:
        print("verdict: ERROR (baseline unreadable: %s)" % e)
        return 2

    print("check_ids.py — port %s (%s)" % (a.port, base_url))
    print("baseline: %s (repo_head %s, %d ids / %d interactive)"
          % (a.baseline, str(data.get("meta", {}).get("repo_head", "?"))[:7],
             len(base_rows), sum(1 for r in base_rows if is_interactive(r))))
    print("allow-added: %s" % (", ".join(sorted(allow_added)) or "(none)"))

    # ---------- 1) 静态资源 / HTML 源那一路 ----------
    src_rows = None
    if a.port == "8080":
        try:
            src_rows, nfiles = admin_asset_ids(base_url)
            print("")
            ok_src = report_section(
                "assets", base_rows, src_rows, allow_added,
                "served files: %d (GET / + recursive import of app/*.js)" % nfiles)
        except Exception as e:
            print("")
            print("[assets] ERROR: 拿不到服务端静态资源（%s）" % e)
            print("verdict: ERROR (service not up?)")
            return 2
    else:
        try:
            src_rows = launcher_source_ids(base_url)
            print("")
            ok_src = report_section("source", base_rows, src_rows, allow_added,
                                    "served GET / panel HTML")
        except Exception as e:
            print("")
            print("[source] ERROR: 拿不到 9500 页面（%s）" % e)
            print("verdict: ERROR (launcher not up? launcher 是 Windows-only，Linux 上起不来)")
            return 2

    # ---------- 2) DOM 那一路 ----------
    dom_rows = None
    dom_note = ""
    if a.from_json:
        try:
            dumped = json.loads(open(a.from_json, encoding="utf-8").read())
            dom_rows = dumped["ids"]
            dom_note = "from-json: %s (collected_at %s)" % (a.from_json, dumped.get("collected_at", "?"))
        except Exception as e:
            print("verdict: ERROR (from-json unreadable: %s)" % e)
            return 2
    elif not a.no_dom:
        sess = CdpSession()
        if not sess.open():
            print("")
            print("[dom] ERROR: 拿不到 CDP（平台 9222 不通且本机找不到可自动拉起的浏览器）")
            print("verdict: ERROR (no renderer)")
            return 2
        try:
            dom_rows, err = dom_ids(base_url, sess.port)
        finally:
            sess.close()
        if dom_rows is None:
            print("")
            print("[dom] ERROR: 渲染失败（%s）" % err)
            print("verdict: ERROR (render failed)")
            return 2
        dom_note = "CDP render %s" % base_url

    ok_dom = True
    if dom_rows is not None:
        if a.port == "8080":
            run_ids = {r["id"] for r in dom_rows}
            base_ids = {r["id"] for r in base_rows}
            undeclared = sorted(run_ids - base_ids - allow_added)
            declared = sorted((run_ids - base_ids) & allow_added)
            not_rendered = sorted(base_ids - run_ids)
            print("")
            print("[dom] %s" % dom_note)
            print("  rendered ids: %d" % len(run_ids))
            print("  not-in-baseline: %d (declared %d / undeclared %d)"
                  % (len(declared) + len(undeclared), len(declared), len(undeclared)))
            for i in undeclared:
                print("    + %s [UNDECLARED]" % i)
            for i in declared:
                print("    + %s [declared]" % i)
            print("  baseline-not-rendered: %d（SPA 当前路由以外的页面 id，由 assets 段做双向差集）"
                  % len(not_rendered))
            ok_dom = not undeclared
            print("  verdict: %s" % ("PASS" if ok_dom else "FAIL"))
        else:
            print("")
            ok_dom = report_section("dom", base_rows, dom_rows, allow_added, dom_note)

    if a.dump_ids:
        payload = {
            "port": a.port,
            "url": base_url,
            "collected_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "source": "dom" if dom_rows is not None else "source",
            "ids": dom_rows if dom_rows is not None else src_rows,
        }
        with open(a.dump_ids, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
        print("")
        print("dumped ids: %s (%d ids, source=%s)" % (a.dump_ids, len(payload["ids"]), payload["source"]))

    ok = ok_src and ok_dom
    print("")
    print("RESULT: %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())