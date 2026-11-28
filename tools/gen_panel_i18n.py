#!/usr/bin/env python3
"""把 9500 控制面板接进语言层：生成并注入 panel.html 的语言层 + 字典块。

做法（幂等）：
  panel.html 里有一对标记 <!--RF4-I18N-START--> / <!--RF4-I18N-END-->，
  本脚本把「引擎 + 字典 + 模板规则」重写在这对标记之间。
  标记不存在时，插到主 <script> 之前（一次性）。

覆盖检查（不依赖脆弱的 JS 语法解析）：
  取 panel.html 里所有 CJK 词块（按标点/空白切分），排除 <style> 与注释区；
  每块都要能在「字典值 + 规则模式」里找到，否则报缺译。
  真正的「页面渲染后还剩几个中文」由 tools/win_verify_9500.py 在浏览器里实测；
  本机没浏览器时可用 tools/check_panel_tr.py 做静态近似（纯 Python，不需要 node）。

用法（仓库根默认取本脚本所在 tools/ 的上级，不依赖当前工作目录）：
  python3 tools/gen_panel_i18n.py                    # 检查 + 写入
  python3 tools/gen_panel_i18n.py --check            # 只检查，不写文件
  python3 tools/gen_panel_i18n.py --repo /path/to/repo
  python3 tools/gen_panel_i18n.py --panel /path/to/panel.html
退出码：0 = 覆盖齐全；1 = 有缺译；2 = 结构问题（含找不到 panel.html）。
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# tools/ 的上一级就是仓库根；脚本在哪个体检目录里跑都成立，不硬编码任何盘符。
DEFAULT_REPO = os.path.dirname(HERE)

sys.path.insert(0, HERE)
from panel_en import EN_BY_ZH, RULES  # noqa: E402

CJK_CLASS = "\u3000-\u303f\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uff00-\uffef"
CJK_RUN = re.compile(r"[%s]+" % "".join(
    c for c in [
        "\u4e00-\u9fff", "\u3400-\u4dbf", "\uf900-\ufaff",
        "\u3000-\u303f", "\uff00-\uffef",
    ]
))
START = "<!--RF4-I18N-START-->"
END = "<!--RF4-I18N-END-->"

ENGINE = r"""<script>window.RF4_LANG="zh";</script>
<script>
// 生成物：不要手改。源文件 tools/panel_en.py，生成命令 tools/gen_panel_i18n.py。
// 口径：只翻「用户看得到的字」（文本节点 + title/placeholder/aria-label/alt）；
// 日志正文、玩家数据不在字典里，因而保留中文。zh 页不做任何替换。
(function () {
  var L = window.RF4_LANG === "en" ? "en" : "zh";
  var MAP = __MAP__;
  var RULES = __RULES__;
  if (L !== "en") {
    window.__rf4Tr = function (s) { return s; };
    return;
  }
  var compiled = RULES.map(function (r) { return [new RegExp(r[0]), r[1]]; });
  var PUNCT = { "。": ".", "、": ", ", "，": ", ", "：": ": ", "；": "; ", "！": "!", "？": "?", "（": " (", "）": ")", "「": '"', "」": '"' };

  function fill(tpl, m) {
    return tpl.replace(/\{(\d+)\}/g, function (all, i) {
      var v = m[Number(i) + 1];
      return v === undefined ? all : v;
    });
  }
  var CJKRE = /[\u3000-\u303f\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uff00-\uffef]/;
  var KEYS_BY_LEN = Object.keys(MAP).sort(function (a, b) { return b.length - a.length; });
  // 并列短语（「游戏逻辑」「登录与连接」）等整句里夹的 UI 片段：整条命中之后再补翻一遍，
  // 免得一句里残留中文。只对「已经被判为 UI 文案」的字符串生效，不碰日志正文与玩家数据。
  function polysh(s) {
    if (!CJKRE.test(s)) { return s; }
    for (var i = 0; i < KEYS_BY_LEN.length; i++) {
      var k = KEYS_BY_LEN[i];
      if (k.length > 1 && s.indexOf(k) >= 0) { s = s.split(k).join(MAP[k]); }
    }
    return s.split("」「").join(", ").split("「").join("").split("」").join("");
  }
  function tr(s) {
    if (!s) { return s; }
    var t = String(s), trimmed = t.trim();
    if (!trimmed) { return s; }
    if (Object.prototype.hasOwnProperty.call(MAP, trimmed)) {
      var v = MAP[trimmed];
      return polysh(t.replace(trimmed, function () { return v; }));
    }
    for (var i = 0; i < compiled.length; i++) {
      var m = compiled[i][0].exec(trimmed);
      if (m) { return polysh(t.replace(trimmed, function () { return fill(compiled[i][1], m); })); }
    }
    if (Object.prototype.hasOwnProperty.call(PUNCT, trimmed)) {
      return t.replace(trimmed, function () { return PUNCT[trimmed]; });
    }
    return s;
  }
  window.__rf4Tr = tr;

  var SKIP = { SCRIPT: 1, STYLE: 1, TEXTAREA: 1, CODE: 1, PRE: 1 };
  var ATTRS = ["title", "placeholder", "aria-label", "alt"];
  function walk(root) {
    if (!root || !document.createTreeWalker) { return; }
    var w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode: function (n) {
        if (!n.nodeValue || !n.nodeValue.trim()) { return NodeFilter.FILTER_REJECT; }
        var p = n.parentElement;
        if (!p || SKIP[p.tagName]) { return NodeFilter.FILTER_REJECT; }
        return NodeFilter.FILTER_ACCEPT;
      }
    });
    var nodes = [];
    while (w.nextNode()) { nodes.push(w.currentNode); }
    for (var i = 0; i < nodes.length; i++) {
      var next = tr(nodes[i].nodeValue);
      if (next !== nodes[i].nodeValue) { nodes[i].nodeValue = next; }
    }
    if (root.querySelectorAll) {
      var els = root.querySelectorAll("*");
      for (var j = 0; j < els.length; j++) {
        for (var a = 0; a < ATTRS.length; a++) {
          if (els[j].hasAttribute(ATTRS[a])) {
            var cur = els[j].getAttribute(ATTRS[a]), nx = tr(cur);
            if (nx !== cur) { els[j].setAttribute(ATTRS[a], nx); }
          }
        }
      }
    }
  }
  function kick() {
    walk(document.body);
    if (document.title) { document.title = tr(document.title); }
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", kick);
  } else {
    kick();
  }
  if (typeof MutationObserver === "function") {
    var queued = false;
    var obs = new MutationObserver(function () {
      if (queued) { return; }
      queued = true;
      requestAnimationFrame(function () { queued = false; walk(document.body); });
    });
    obs.observe(document.body, { childList: true, subtree: true, characterData: true });
    window.__rf4PanelLangObserver = obs;
  }
})();
</script>"""


def masked(src):
    """去掉 <style> 与 HTML 注释区（里面的中文不是页面文案）。"""
    src = re.sub(r"<style>.*?</style>", " ", src, flags=re.S)
    src = re.sub(r"<!--.*?-->", " ", src, flags=re.S)
    src = re.sub(r"/\*.*?\*/", " ", src, flags=re.S)
    src = re.sub(r"(?m)//[^\n]*$", " ", src)
    return src


def corpus():
    parts = list(EN_BY_ZH.keys()) + [p for p, _ in RULES]
    blob = "\n".join(parts)
    runs = set()
    for m in CJK_RUN.finditer(blob):
        runs.add(m.group(0))
    return blob, runs


def parse_args(argv):
    ap = argparse.ArgumentParser(
        description="把 9500 控制面板接进语言层：生成并注入 panel.html 的字典块（幂等）。")
    ap.add_argument("--repo", default=DEFAULT_REPO,
                    help="仓库根目录（默认：本脚本所在 tools/ 的上级）")
    ap.add_argument("--panel", default=None,
                    help="panel.html 路径（默认 <repo>/cmd/launcher/panel.html）")
    ap.add_argument("--check", action="store_true", help="只检查覆盖，不写文件")
    return ap.parse_args(argv)


def main():
    args = parse_args(sys.argv[1:])
    panel = args.panel or os.path.join(args.repo, "cmd", "launcher", "panel.html")
    if not os.path.isfile(panel):
        print("STRUCT: 找不到 panel.html：%s（用 --repo/--panel 指定仓库根）" % panel,
              file=sys.stderr)
        return 2
    src = open(panel, encoding="utf-8").read()
    body = masked(src)
    blob, known = corpus()
    missing = []
    for m in CJK_RUN.finditer(body):
        run = m.group(0)
        if run in known or run in blob:
            continue
        # 单个汉字（如「的」）已经作为整条在字典里时不重复要求
        if len(run) == 1 and run in blob:
            continue
        if run not in missing:
            missing.append(run)

    print("dict entries: %d / rules: %d" % (len(EN_BY_ZH), len(RULES)))
    print("uncovered CJK runs: %d" % len(missing))
    for m in missing:
        print("MISSING %s" % m)

    data = ENGINE
    data = data.replace("__MAP__", json.dumps(EN_BY_ZH, ensure_ascii=False, sort_keys=True, indent=2))
    rules = ",\n    ".join("[%s, %s]" % (json.dumps(p, ensure_ascii=False), json.dumps(r, ensure_ascii=False)) for p, r in RULES)
    data = data.replace("__RULES__", "[\n    " + rules + "\n  ]")
    block = START + "\n" + data + "\n" + END

    if START in src and END in src:
        a = src.index(START)
        b = src.index(END) + len(END)
        new = src[:a] + block + src[b:]
    else:
        anchor = "<script>\nconst NAMES"
        if anchor not in src:
            print("STRUCT: 找不到注入点（主 <script>）", file=sys.stderr)
            return 2
        new = src.replace(anchor, block + "\n<script>\nconst NAMES", 1)

    for tag in ('<html lang="zh-CN">', '<nav id="lang-switch" class="lang-switch"></nav>',
                '<title>RF4 本地服务器</title>'):
        if tag not in new:
            print("STRUCT: panel.html 缺少静态接入点 %s" % tag, file=sys.stderr)
            return 2

    if missing:
        print("先补 tools/panel_en.py 再生成（%d 条未覆盖）。" % len(missing))
        return 1
    if args.check:
        print("check ok（未写文件）：%s" % panel)
        return 0
    if new != src:
        open(panel, "w", encoding="utf-8").write(new)
        print("panel.html 已更新：%d bytes（%s）" % (len(new), panel))
    else:
        print("panel.html 无变化（幂等）：%s" % panel)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())