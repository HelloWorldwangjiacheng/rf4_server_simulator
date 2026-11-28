#!/usr/bin/env python3
"""标准 6：默认语言按浏览器语言走，缺省中文。纯标准库。

口径（服务端优先级）：?lang= > cookie lang > Accept-Language > zh。
本脚本用 HTTP 头直连服务端，验证协商链（页面壳的 html lang / title / window.__LANG__），
不渲染 JS；渲染后的整页文本比对由 check_page.py 负责（标准 3/5/7）。

断言：
  A. 无 Accept-Language、无 cookie → `<html lang="zh-CN">` 且 title 含「RF4 管理后台」
  B. Accept-Language: en-US → `<html lang="en">` 且 title 为 RF4 Admin Console
  C. Accept-Language: zh-CN → `<html lang="zh-CN">` 且 title 含「RF4 管理后台」
  D. cookie lang=en + 无参数 → en 壳；cookie lang=zh + 无参数 → zh 壳
  E. ?lang=en 覆盖 cookie lang=zh（参数优先）
四项全过输出 PASS，退出码 0。
"""
import sys
import urllib.request

BASE = "http://127.0.0.1:8080/"


def fetch(headers=None):
    req = urllib.request.Request(BASE, headers=headers or {})
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.read().decode("utf-8", "replace")


def is_zh(html):
    return '<html lang="zh-CN">' in html and "RF4 管理后台</title>" in html


def is_en(html):
    return '<html lang="en">' in html and "RF4 Admin Console</title>" in html


def main():
    checks = []

    h = fetch()
    checks.append(("A 无头无 cookie → zh", is_zh(h)))

    h = fetch({"Accept-Language": "en-US,en;q=0.9"})
    checks.append(("B Accept-Language: en-US → en", is_en(h)))

    h = fetch({"Accept-Language": "zh-CN,zh;q=0.9"})
    checks.append(("C Accept-Language: zh-CN → zh", is_zh(h)))

    h = fetch({"Cookie": "lang=en"})
    checks.append(("D1 cookie lang=en → en", is_en(h)))

    h = fetch({"Cookie": "lang=zh"})
    checks.append(("D2 cookie lang=zh → zh", is_zh(h)))

    req = urllib.request.Request(BASE + "?lang=en", headers={"Cookie": "lang=zh"})
    with urllib.request.urlopen(req, timeout=10) as r:
        h = r.read().decode("utf-8", "replace")
        sc = r.headers.get("Set-Cookie", "")
    checks.append(("E ?lang=en 覆盖 cookie lang=zh", is_en(h)))
    checks.append(("E2 ?lang=en 回写 cookie（Path=/ Max-Age=31536000）",
                   "lang=en" in sc and "Path=/" in sc and "Max-Age=31536000" in sc))

    bad = [n for n, ok in checks if not ok]
    for n, ok in checks:
        print(("  ok   " if ok else "  FAIL ") + n)
    print("verdict: " + ("PASS" if not bad else "FAIL"))
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())