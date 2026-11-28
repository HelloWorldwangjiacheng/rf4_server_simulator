#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""标准 6「默认语言按浏览器语言走」的 9500 半边：Accept-Language 协商。

为什么单独有这个脚本：check_default.py 的 BASE 硬编码 8080、断言的是 8080 的标题，
9500（launcher 控制面板）在 Linux 起不来，那条命令在 9500 上跑不了。这个脚本就是补那个载体。

口径（服务端，两个端口共用一个 cookie 名和同一套优先级）：
    ?lang=  >  cookie lang  >  Accept-Language  >  默认 zh

本脚本只发 HTTP 头、不渲染 JS，断言的是「页面壳」的三件事（都是用户在浏览器里看得见的）：
    <html lang>、<title>、window.<lang-var>
标题默认取 9500 自己的（zh=RF4 本地服务器 / en=RF4 Local Server），**不照抄 8080 的
RF4 管理后台 / RF4 Admin Console**；--title-zh / --title-en / --lang-var 可改，
只在拿别的端口（例如 8080）做脚本自测时才需要改。

三项：
  A. 无 Accept-Language、无 cookie、无 ?lang= → zh 壳
  B. Accept-Language: en-US,en;q=0.9            → en 壳
  C. Accept-Language: zh-CN,zh;q=0.9            → zh 壳

用法（在仓库根）：
  python tools\\check_acceptlang.py                          # 默认 http://127.0.0.1:9500
  python tools\\check_acceptlang.py --url http://127.0.0.1:9500
  python3 tools/check_acceptlang.py --url http://127.0.0.1:8080 --title-zh "RF4 管理后台" ^
          --title-en "RF4 Admin Console" --lang-var __LANG__   # 只为自测脚本本身

退出码：0 = 三项全 PASS；1 = 有 FAIL（逐项列出实测值）；2 = 服务连不上 / HTTP 异常
（环境问题，**不算通过**，先把服务起好再跑）。
"""

import argparse
import re
import sys
import urllib.request

DEF_URL = "http://127.0.0.1:9500"
DEF_TITLE_ZH = "RF4 本地服务器"
DEF_TITLE_EN = "RF4 Local Server"
DEF_LANG_VAR = "RF4_LANG"

# (项名, Accept-Language 头, 期望语言, 人读的口径)
CASES = [
    ("acceptlang-default", None, "zh", "无 Accept-Language / 无 cookie / 无 ?lang="),
    ("acceptlang-en", "en-US,en;q=0.9", "en", "Accept-Language: en-US,en;q=0.9"),
    ("acceptlang-zh", "zh-CN,zh;q=0.9", "zh", "Accept-Language: zh-CN,zh;q=0.9"),
]


def fetch(url, headers=None, timeout=10):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode("utf-8", "replace")


def read_shell(body, lang_var):
    """从原始 HTML 里抠出 <html lang>、<title>、window.<lang_var>。抠不到给空串。"""
    m = re.search(r'<html\s+lang="([^"]*)"', body)
    html_lang = m.group(1) if m else ""
    m = re.search(r"<title>(.*?)</title>", body, re.S)
    title = m.group(1).strip() if m else ""
    m = re.search(r'window\.' + re.escape(lang_var) + r'\s*=\s*"([^"]*)"', body)
    var = m.group(1) if m else ""
    return html_lang, title, var


def check_shell_lang(url, zh_title, en_title, lang_var=DEF_LANG_VAR, timeout=10):
    """返回 [(项名, 是否 PASS, 明细字符串)]；每项都带上实测值，不只给结论。"""
    out = []
    for name, accept_lang, want, label in CASES:
        headers = {"Cache-Control": "no-cache"}
        if accept_lang:
            headers["Accept-Language"] = accept_lang
        want_html = "zh-CN" if want == "zh" else "en"
        want_title = zh_title if want == "zh" else en_title
        try:
            status, body = fetch(url, headers, timeout)
        except Exception as e:  # 连不上/超时：本项 FAIL，明细写清原因，不抛栈
            out.append((name, False, "%s -> 请求失败: %s" % (label, e)))
            continue
        html_lang, title, var = read_shell(body, lang_var)
        ok = (html_lang == want_html) and (title == want_title) and (var == want)
        out.append((name, ok,
                    "%s -> HTTP %s, 期望 %r 壳 | <html lang>=%r%s <title>=%r%s %s=%r%s"
                    % (label, status, want,
                       html_lang, "" if html_lang == want_html else "(want %r)" % want_html,
                       title, "" if title == want_title else "(want %r)" % want_title,
                       lang_var, var, "" if var == want else "(want %r)" % want)))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="标准 6 的 9500 半边：Accept-Language 协商")
    ap.add_argument("--url", default=DEF_URL, help="默认 %s" % DEF_URL)
    ap.add_argument("--title-zh", default=DEF_TITLE_ZH, help="中文壳的 <title>，默认 %r" % DEF_TITLE_ZH)
    ap.add_argument("--title-en", default=DEF_TITLE_EN, help="英文壳的 <title>，默认 %r" % DEF_TITLE_EN)
    ap.add_argument("--lang-var", default=DEF_LANG_VAR, help="页面壳里注入的语言变量名，默认 %s" % DEF_LANG_VAR)
    ap.add_argument("--timeout", type=float, default=10.0)
    a = ap.parse_args(argv)

    url = a.url.rstrip("/") + "/"

    # 0. 服务活着吗——连不上直接 2，不把「服务没起」混成 FAIL
    try:
        st, _ = fetch(url, None, a.timeout)
    except Exception as e:
        print("服务连不上：%s（%s）" % (url, e))
        print("RESULT: ERROR (service unreachable)")
        return 2
    if st != 200:
        print("服务在，但 GET %s 返回 %s（期望 200）" % (url, st))
        print("RESULT: ERROR (unexpected status)")
        return 2

    rows = check_shell_lang(url, a.title_zh, a.title_en, a.lang_var, a.timeout)
    print("target: %s" % url)
    print("shell : <html lang> / <title> / window.%s" % a.lang_var)
    print("")
    for name, ok, detail in rows:
        print("[%s] %-18s %s" % ("PASS" if ok else "FAIL", name, detail))

    passed = sum(1 for _, ok, _ in rows if ok)
    verdict = "PASS" if passed == len(rows) else "FAIL"
    print("")
    print("===== SUMMARY (Accept-Language 协商 · 9500 半边 · 标准 6) =====")
    for name, ok, detail in rows:
        print("[%s] %-18s %s" % ("PASS" if ok else "FAIL", name, detail))
    print("RESULT: %s (%d/%d)" % (verdict, passed, len(rows)))
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())