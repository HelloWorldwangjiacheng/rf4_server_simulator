#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""面板静态漏翻扫描：把 panel.html 的可见文本节点过一遍 tr()，输出 hits 计数与逐条命中。

口径（与运行期 ENGINE / tools/win_verify_9500.py 的 en-cjk 判定同源）：
  * 只看「用户看得到的字」：HTML 文本节点 + title/placeholder/aria-label/alt 四个属性；
  * 跳过 <script> / <style> / <template> / <noscript> 与 HTML 注释；
  * 运行日志区（#logs / .home-log）里的内容是「数据不是文案」，单独计数、不计入判定；
  * tr() 的实现与数据见 tools/panel_tr_eval.py + tools/panel_en.py（同一份规则，不复制）。

这是静态近似（没有浏览器，拿不到 JS 运行时插值后的字符串）；
真正渲染后的数字由 tools/win_verify_9500.py 在 Windows 上实测。

用法：
  python3 tools/check_panel_tr.py                     # 默认扫 <repo>/cmd/launcher/panel.html
  python3 tools/check_panel_tr.py --html /path/panel.html
  python3 tools/check_panel_tr.py --text "某些拼接后的句子"      # 单条字符串
  python3 tools/check_panel_tr.py --lang zh           # 统计 zh 侧 CJK 文本节点数（基线对比）
退出码：0 = en 侧无残留（hits=0）；1 = 有残留；2 = 结构问题。
"""
import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from panel_tr_eval import CJK, cjk_count, tr  # noqa: E402

DEFAULT_REPO = os.path.dirname(HERE)
ATTRS = ("title", "placeholder", "aria-label", "alt")


def mask(src):
    """抹掉 script/style/template/noscript/注释，保留换行以便报行号。"""
    def blank(m):
        return re.sub(r"[^\n]", " ", m.group(0))
    for pat in (r"<script\b.*?</script>", r"<style\b.*?</style>",
                r"<template\b.*?</template>", r"<noscript\b.*?</noscript>",
                r"<!--.*?-->"):
        src = re.sub(pat, blank, src, flags=re.S | re.I)
    return src


def data_spans(src_masked):
    """#logs / .home-log 区（运行日志正文）的字符区间。"""
    spans = []
    for m in re.finditer(r"<(div|section|textarea|pre)\b[^>]*(?:id=\"logs\"|class=\"[^\"]*home-log[^\"]*)[^>]*>",
                         src_masked, flags=re.I):
        tag = m.group(1)
        close = re.search(r"</%s>" % tag, src_masked[m.end():], flags=re.I)
        end = m.end() + close.end() if close else len(src_masked)
        spans.append((m.start(), end))
    return spans


def in_spans(pos, spans):
    return any(a <= pos < b for a, b in spans)


def nodes(html):
    """产出 (line_no, 类型, 文本)。"""
    src = mask(html)
    spans = data_spans(src)
    for m in re.finditer(r">([^<>]+)<", src):
        txt = m.group(1)
        if not txt.strip():
            continue
        yield (src.count("\n", 0, m.start(1)) + 1,
               "data" if in_spans(m.start(1), spans) else "text", txt)
    for m in re.finditer(r"\b(%s)=\"([^\"]*)\"" % "|".join(ATTRS), src):
        yield (src.count("\n", 0, m.start(2)) + 1, "attr", m.group(2))


def main():
    ap = argparse.ArgumentParser(description="面板 en 侧漏翻静态扫描（hits 计数 + 逐条命中）")
    ap.add_argument("--repo", default=DEFAULT_REPO, help="仓库根（默认：本脚本所在 tools/ 的上级）")
    ap.add_argument("--html", default=None, help="panel.html 路径（默认 <repo>/cmd/launcher/panel.html）")
    ap.add_argument("--text", default=None, action="append", help="只检查给定字符串（可重复）")
    ap.add_argument("--lang", default="en", choices=["en", "zh"],
                    help="en = 过 tr() 数残留（判定）；zh = 数 CJK 文本节点（基线对比）")
    a = ap.parse_args()

    if a.text:
        hits = 0
        for s in a.text:
            out = tr(s)
            n = cjk_count(out)
            if n:
                hits += 1
            print("[%s] CJK %d -> %d  %r" % ("HIT " if n else "OK  ", cjk_count(s), n, out))
        print("texts=%d  hits=%d" % (len(a.text), hits))
        return 0 if hits == 0 else 1

    html_path = a.html or os.path.join(a.repo, "cmd", "launcher", "panel.html")
    if not os.path.isfile(html_path):
        print("STRUCT: 找不到 %s（用 --repo/--html 指定）" % html_path, file=sys.stderr)
        return 2
    with open(html_path, encoding="utf-8") as f:
        html = f.read()

    ui_total = ui_cjk = data_hits = 0
    hits = []
    for line, kind, txt in nodes(html):
        s = txt.strip()
        if not s:
            continue
        if kind == "data":
            if CJK.search(s):
                data_hits += 1
            continue
        ui_total += 1
        if a.lang == "zh":
            if CJK.search(s):
                ui_cjk += 1
                hits.append((line, kind, s))
            continue
        out = tr(s)
        if CJK.search(out):
            hits.append((line, kind, "%s  ⇒  %s" % (s, out)))

    if a.lang == "zh":
        print("html: %s" % html_path)
        print("zh 文本节点（含属性）: %d，其中含 CJK: %d" % (ui_total, ui_cjk))
        for line, kind, s in hits[:20]:
            print("  zh L%-5d %-4s %s" % (line, kind, s[:120]))
        return 0

    print("html: %s" % html_path)
    print("en 侧文本节点（含属性）: %d" % ui_total)
    print("hits: %d" % len(hits))
    for line, kind, s in hits:
        print("  L%-5d %-4s %s" % (line, kind, s[:200]))
    print("data-hits（运行日志区，属数据、不计入判定）: %d" % data_hits)
    return 0 if not hits else 1


if __name__ == "__main__":
    raise SystemExit(main())