#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""9500 控制面板（launcher）双语运行期校验包 —— Windows 用，纯标准库。

为什么要在 Windows 上跑：cmd/launcher 是 Windows-only 目标（hosts.go 直接 import
golang.org/x/sys/windows），在 Linux 上构建不出这个二进制，所以 9500 的运行期实测
只能在 Windows 机器上做。这个脚本就是那半边验收的载体。

它检查什么（每项都给 PASS/FAIL + 实测数字，末尾打「摘要块」）：
  1. routes-9500   baseline 里 9500 端口 15 条路由的状态码差集（只打标记为可采样的，
                  有副作用的路由按 baseline 的 sample_policy=skip 跳过并写明）
  2. lang-switch   原始 HTML 里语言切换锚点数（lang-switch / ?lang=zh / ?lang=en 去重）
  3. cookie-set    ?lang=en 响应回写 Set-Cookie: lang=en; Path=/; Max-Age=31536000
  4. cookie-en     不带任何 URL 参数、只带 Cookie: lang=en 时页面壳是 en
  5. en-cjk        en 页渲染后 UI 文本节点 CJK 命中数（要求 0）
  6. zh-cjk        zh 页渲染后 CJK 命中数（要求 >= 20，确认中文没被改坏）
  7. fallback      缺 key 回退：字典里没有的整句原样返回，不出现空串/裸 key/undefined
  8. acceptlang-*  Accept-Language 协商（标准 6 的 9500 半边）：无头→zh 壳、
                   en-US→en 壳、zh-CN→zh 壳；断言的是 9500 自己的 <html lang> /
                   <title> / window.RF4_LANG。纯 HTTP，不依赖浏览器。
                   ↑ 这一项是本轮追加的：判定逻辑写在同目录 check_acceptlang.py，
                     win_verify 原 9 项（service/routes-9500/lang-switch/cookie-set/
                     cookie-en/en-cjk/zh-cjk/cookie-en-render/fallback）逻辑与字段名未改。

口径说明（请连同结果一起贴回，验收主管要按这个判）：
  - en-cjk 统计的是「用户看得见的 UI 文字」：遍历渲染后的 DOM，跳过 script/style/
    template 与 display:none 的子树，**并单独排除服务端运行日志区（#logs / .home-log）**。
    日志正文属于「数据不是文案」（简报假设五），所以它单独计数、原样列出（data-hits），
    不参与 PASS/FAIL 判定。判定用的数字与列出的日志行都会被打印，无法被隐藏。
  - 需要浏览器支持 CDP。优先用系统自带的 Edge（Windows 10/11 默认都有），也可用
    Chrome；都找不到时脚本以退出码 2 结束并说明原因，不会假装通过。

用法（在仓库根，或用 --repo 指定）：
  python tools\\win_verify_9500.py                     # 默认 http://127.0.0.1:9500
  python tools\\win_verify_9500.py --url http://127.0.0.1:9500 --json out.json
  set RF4_BROWSER=C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe

退出码：0 = 全项 PASS；1 = 有 FAIL；2 = 环境问题（找不到浏览器 / 服务没起 / CDP 不通）。
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from check_page import WS, cdp_http  # noqa: E402  复用最小 WebSocket 客户端（纯标准库）
try:
    from check_acceptlang import check_shell_lang  # noqa: E402  第 8 项：Accept-Language
    _ACCEPTLANG_ERR = ""
except Exception as _e:  # tools/ 没整包拷时不要抛栈，按一项 FAIL 报出来
    check_shell_lang = None
    _ACCEPTLANG_ERR = str(_e)

CJK = re.compile("[\u3000-\u303f\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uff00-\uffef]")
DEF_URL = "http://127.0.0.1:9500"

# 量测脚本：等价 innerText 的可见文本，但把运行日志区单独分出来。
MEASURE_JS = r"""
(function () {
  var ui = [], data = [];
  function visible(el) {
    var cs = window.getComputedStyle(el);
    if (cs.display === "none" || cs.visibility === "hidden") return false;
    return true;
  }
  function isData(el) {
    if (!el || !el.getAttribute) return false;
    if (el.id === "logs") return true;
    var cls = el.getAttribute("class") || "";
    return cls.indexOf("home-log") >= 0;
  }
  function walk(node, inData) {
    if (node.nodeType === 3) {
      var t = node.nodeValue;
      if (t && t.trim()) { (inData ? data : ui).push(t.trim()); }
      return;
    }
    if (node.nodeType !== 1) return;
    var tag = node.tagName;
    if (tag === "SCRIPT" || tag === "STYLE" || tag === "NOSCRIPT" || tag === "TEMPLATE") return;
    if (!visible(node)) return;
    var d = inData || isData(node);
    for (var c = node.firstChild; c; c = c.nextSibling) walk(c, d);
  }
  walk(document.body, false);
  return JSON.stringify({
    ui: ui.join("\n"),
    data: data.join("\n"),
    title: document.title,
    lang: window.RF4_LANG || "",
    htmlLang: document.documentElement.getAttribute("lang") || ""
  });
})()
"""

PROBE_JS = r"""
(function () {
  var f = window.__rf4Tr;
  if (typeof f !== "function") return JSON.stringify({ok: false, why: "__rf4Tr missing"});
  return JSON.stringify({
    ok: true,
    missing: f("这条文案故意不在字典里"),
    hit: f("开始游戏"),
    hitZh: f("保存")
  });
})()
"""


def log(msg):
    print(msg)
    sys.stdout.flush()


def find_browser(explicit):
    if explicit:
        return explicit if os.path.exists(explicit) else None
    env = os.environ.get("RF4_BROWSER")
    if env and os.path.exists(env):
        return env
    cands = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for c in cands:
        if os.path.exists(c):
            return c
    for name in ("msedge", "chrome", "chromium"):
        p = shutil.which(name)
        if p:
            return p
    return None


def free_port():
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """不跟随任何 3xx：路由差集要观测服务端真实状态码。

    原有实现用 urlopen 默认 opener，会**自动跟随** 301/302/307/308；
    /admin 的期望是 307（http.Redirect → /admin/），跟随之后拿到的是
    /admin/ 的 200/503，路由差集必然报 want=307 got=200。
    redirect_request 返回 None 让 urllib 抛 HTTPError，于是状态码与
    Location 头都能原样读到。
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        return None


OPENER = urllib.request.build_opener(_NoRedirect())


def http_get(url, cookie=None, timeout=15):
    req = urllib.request.Request(url, method="GET")
    if cookie:
        req.add_header("Cookie", cookie)
    try:
        with OPENER.open(req, timeout=timeout) as r:
            return r.status, dict(r.headers), r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read().decode("utf-8", "replace")


def http_any_full(method, url, timeout=15):
    """返回 (status, headers)。3xx 原样返回，Location 可读。"""
    req = urllib.request.Request(url, method=method)
    try:
        with OPENER.open(req, timeout=timeout) as r:
            return r.status, dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers)
    except Exception:
        return None, {}


def http_any(method, url, timeout=15):
    status, _headers = http_any_full(method, url, timeout=timeout)
    return status


def render(url, cookie, port, timeout=40):
    """用 CDP 打开页面，返回 {ui, data, title, lang, htmlLang} 与探针结果。"""
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
        call("Network.enable", {})
        if cookie:
            call("Network.setCookie", {"name": cookie[0], "value": cookie[1], "url": url_root(url)})
        call("Page.navigate", {"url": url})
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                ws.sock.settimeout(3)
                msg = json.loads(ws.recv())
            except Exception:
                break
            if msg.get("method") == "Page.loadEventFired":
                break
        time.sleep(2.0)  # 面板每 2 秒轮询一次状态，等首屏渲染稳定
        out = call("Runtime.evaluate", {"expression": MEASURE_JS, "returnByValue": True})
        page = json.loads(out["result"]["result"].get("value") or "{}")
        probe = call("Runtime.evaluate", {"expression": PROBE_JS, "returnByValue": True})
        page["probe"] = json.loads(probe["result"]["result"].get("value") or "{}")
        return page
    finally:
        try:
            ws.sock.close()
        except Exception:
            pass
        try:
            cdp_http(port, "/json/close/" + target["id"])
        except Exception:
            pass


def url_root(url):
    from urllib.parse import urlparse
    u = urlparse(url)
    return "%s://%s/" % (u.scheme, u.netloc)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=DEF_URL)
    ap.add_argument("--repo", default=os.path.abspath(os.path.join(HERE, "..", "..", "..", "..")))
    ap.add_argument("--baseline", default=os.path.join(HERE, "baseline_ids.json"))
    ap.add_argument("--browser", default=None)
    ap.add_argument("--json", default=None, help="把结果另存成 JSON（可选）")
    ap.add_argument("--skip-routes", action="store_true", help="只做页面检查，不做路由差集")
    # 第 8 项（acceptlang）的断言口径。默认取 9500 自己的标题与语言变量名；
    # 只有拿别的端口做脚本自测时才需要改。
    ap.add_argument("--title-zh", default="RF4 本地服务器", help="zh 壳的 <title>（默认 9500 自己的）")
    ap.add_argument("--title-en", default="RF4 Local Server", help="en 壳的 <title>（默认 9500 自己的）")
    ap.add_argument("--lang-var", default="RF4_LANG", help="页面壳里的语言变量名（默认 9500 的 RF4_LANG）")
    a = ap.parse_args()

    results = []  # [(name, ok, detail, extra)]

    def add(name, ok, detail, extra=None):
        results.append({"name": name, "ok": bool(ok), "detail": detail, "extra": extra})
        log("[%s] %-14s %s" % ("PASS" if ok else "FAIL", name, detail))

    # ---- 0. 服务活着吗 ----
    try:
        st, _, body = http_get(a.url + "/api/status")
    except Exception as e:
        log("服务没起来：%s（%s）" % (a.url, e))
        log("RESULT: ERROR (service unreachable)")
        return 2
    if st != 200:
        log("/api/status 返回 %s，服务状态不对，先确认 launcher 已就绪。")
    add("service", st == 200, "GET /api/status -> %s" % st)

    # ---- 1. 路由差集 ----
    if not a.skip_routes:
        try:
            base = json.load(open(a.baseline, encoding="utf-8"))
            routes = base["routes"]["9500"]
        except Exception as e:
            log("读 baseline 失败：%s" % e)
            return 2
        checked, skipped, diff, detail_rows = 0, 0, [], []
        for r in routes:
            path = r["path"]
            method = r.get("method", "GET")
            if r.get("sample_policy") == "skip":
                skipped += 1
                detail_rows.append("SKIP %-5s %-22s %s" % (method, path, r.get("reason", "")[:60]))
                continue
            got = http_any(method, a.url + path)
            checked += 1
            want = r.get("expected_status")
            ok = got == want
            detail_rows.append("%s %-5s %-22s want=%s got=%s" % ("OK  " if ok else "DIFF", method, path, want, got))
            if not ok:
                diff.append((method, path, want, got))
        add("routes-9500", not diff,
            "checked %d/%d, mismatch %d, skipped %d (side-effect routes)"
            % (checked, len(routes), len(diff), skipped), detail_rows)
        for m, p, w, g in diff:
            log("    diff: %s %s want=%s got=%s" % (m, p, w, g))

    # ---- 2. lang-switch 锚点（原始 HTML）----
    _, hdrs, html = http_get(a.url + "/?lang=en")
    anchors = sorted(set(re.findall(r"lang-switch|\?lang=(?:zh|en)", html)))
    add("lang-switch", len(anchors) >= 2, "unique anchors=%d %s" % (len(anchors), anchors))

    # ---- 3. cookie 回写 ----
    sc = hdrs.get("Set-Cookie", "")
    ok_cookie = ("lang=en" in sc) and ("Path=/" in sc) and ("Max-Age=31536000" in sc)
    add("cookie-set", ok_cookie, "Set-Cookie: %s" % (sc or "(none)"))

    # ---- 4. 只靠 cookie 拿到英文页壳 ----
    st2, _, body2 = http_get(a.url + "/", cookie="lang=en")
    ok_shell = ('window.RF4_LANG="en"' in body2) and ('<html lang="en">' in body2)
    add("cookie-en", ok_shell,
        "GET / + Cookie: lang=en -> status %s, RF4_LANG=%s, html lang=%s"
        % (st2, 'en' if 'window.RF4_LANG="en"' in body2 else 'zh/absent',
           'en' if '<html lang="en">' in body2 else 'zh/absent'))

    # ---- 5~7. 浏览器渲染 ----
    browser = find_browser(a.browser)
    if not browser:
        log("找不到 Edge/Chrome，无法做渲染检查。用 --browser 指定 msedge.exe/chrome.exe 的完整路径。")
        log("RESULT: ERROR (no browser)")
        return 2
    port = free_port()
    prof = tempfile.mkdtemp(prefix="rf4-9500-check-")
    flags = [browser, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
             "--remote-debugging-port=%d" % port, "--user-data-dir=" + prof, "about:blank"]
    if os.name == "nt":
        flags.insert(1, "--disable-features=Translate,MediaRouter")
    proc = subprocess.Popen(flags, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.time() + 30
        ready = False
        while time.time() < deadline:
            try:
                cdp_http(port, "/json/version")
                ready = True
                break
            except Exception:
                time.sleep(0.5)
        if not ready:
            log("浏览器启动失败或 CDP 端口不通。")
            log("RESULT: ERROR (cdp unreachable)")
            return 2

        log("")
        log("---- en 页（?lang=en）----")
        en = render(a.url + "/?lang=en", None, port)
        en_lines = [ln for ln in en["ui"].splitlines() if ln.strip()]
        en_hits = [ln for ln in en_lines if CJK.search(ln)]
        data_lines = [ln for ln in en["data"].splitlines() if ln.strip() and CJK.search(ln)]
        add("en-cjk", len(en_hits) == 0,
            "UI CJK hits: %d (title=%r, RF4_LANG=%r, <html lang>=%r)"
            % (len(en_hits), en.get("title"), en.get("lang"), en.get("htmlLang")))
        log("    data-hits（运行日志区，属数据，不计入判定）: %d 行" % len(data_lines))
        for ln in en_hits[:20]:
            log("    hit: " + ln[:160])
        for ln in data_lines[:8]:
            log("    data: " + ln[:160])

        log("")
        log("---- zh 页（?lang=zh）----")
        zh = render(a.url + "/?lang=zh", None, port)
        zh_hits = [ln for ln in zh["ui"].splitlines() if ln.strip() and CJK.search(ln)]
        add("zh-cjk", len(zh_hits) >= 20, "CJK hits: %d (need >= 20)" % len(zh_hits))

        log("")
        log("---- 只靠 cookie 的英文页（无 URL 参数）----")
        ck = render(a.url + "/", ("lang", "en"), port)
        ck_hits = [ln for ln in ck["ui"].splitlines() if ln.strip() and CJK.search(ln)]
        add("cookie-en-render", ck_hits == 0 and ck.get("lang") == "en",
            "UI CJK hits: %d, RF4_LANG=%r" % (len(ck_hits), ck.get("lang")))

        p = en.get("probe") or {}
        ok_fb = bool(p.get("ok")) and p.get("missing") == "这条文案故意不在字典里" \
            and p.get("hit") == "Start game" and p.get("hitZh") == "Save"
        add("fallback", ok_fb,
            "missing->%r, 开始游戏->%r, 保存->%r"
            % (p.get("missing"), p.get("hit"), p.get("hitZh")))
    finally:
        try:
            proc.terminate()
        except Exception:
            pass
        time.sleep(0.5)
        shutil.rmtree(prof, ignore_errors=True)

    # ---- 8. Accept-Language 协商（标准 6 的 9500 半边）----
    # 追加在原有 9 项之后；纯 HTTP，不依赖浏览器/CDP，所以放在渲染段之后单独跑。
    if check_shell_lang is None:
        add("acceptlang", False,
            "check_acceptlang.py 导入失败（tools/ 需整包拷）：%s" % _ACCEPTLANG_ERR)
    else:
        for _nm, _ok, _dt in check_shell_lang(a.url.rstrip("/") + "/", a.title_zh,
                                              a.title_en, a.lang_var):
            add(_nm, _ok, _dt)

    # ---- 摘要块 ----
    log("")
    log("===== SUMMARY (9500 · rf4-i18n-01 · Windows 运行期校验) =====")
    for r in results:
        log("[%s] %-16s %s" % ("PASS" if r["ok"] else "FAIL", r["name"], r["detail"]))
    passed = sum(1 for r in results if r["ok"])
    verdict = "PASS" if passed == len(results) else "FAIL"
    log("RESULT: %s (%d/%d)" % (verdict, passed, len(results)))
    log("把这段从「===== SUMMARY」到最后一行原样贴回即可；完整日志也一起贴。")

    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump({"results": results, "verdict": verdict}, f, ensure_ascii=False, indent=1)
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())