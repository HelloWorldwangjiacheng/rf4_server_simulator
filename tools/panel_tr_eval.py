# -*- coding: utf-8 -*-
"""tr() 的 Python 复刻：与 panel.html 里的运行期实现同源（数据来自 tools/panel_en.py）。

用途：在没有浏览器/没有 node 的环境里对「拼接完成的字符串」求值 tr()，
供 tools/check_5hits.py（5 条漏翻断言）与 tools/check_panel_tr.py（面板静态扫描）
共用。数据只有一份——直接 import tools/panel_en.py，本文件不复制任何键或规则。

与 panel.html ENGINE 的对应关系（逐行对齐）：
  tr(s): 先按 trim 后的整串查字典 → 再按 RULES 顺序做整串正则 → 再查单标点表 →
         每次命中后用 polysh() 对结果补翻一遍（只对已判定为 UI 文案的字符串生效）。
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from panel_en import EN_BY_ZH, RULES  # noqa: E402

CJK = re.compile("[\u3000-\u303f\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uff00-\uffef]")

# 与 ENGINE 里的 PUNCT 表一致
PUNCT = {
    "。": ".", "、": ", ", "，": ", ", "：": ": ", "；": "; ",
    "！": "!", "？": "?", "（": " (", "）": ")",
    "「": '"', "」": '"',
}

# 与 ENGINE 一致：键按长度降序（等长时保持字典序，和 json.dumps(sort_keys=True) 后
# 的 Object.keys 顺序相同）
KEYS_BY_LEN = sorted(EN_BY_ZH.keys(), key=lambda k: (-len(k), k))

_FILL = re.compile(r"\{(\d+)\}")
_COMPILED = [(re.compile(p), r) for p, r in RULES]


def fill(tpl, m):
    def sub(mm):
        i = int(mm.group(1))
        v = m.group(i + 1)  # JS 的 m[Number(i)+1]
        return mm.group(0) if v is None else v
    return _FILL.sub(sub, tpl)


def polysh(s):
    if not CJK.search(s):
        return s
    for k in KEYS_BY_LEN:
        # 与 ENGINE 一致：只补翻多字键（单字键太容易误伤）
        if len(k) > 1 and k in s:
            s = s.replace(k, EN_BY_ZH[k])
    for a, b in (("」「", ", "), ("「", ""), ("」", "")):
        s = s.replace(a, b)
    return s


def tr(s):
    if not s:
        return s
    t = str(s)
    trimmed = t.strip()
    if not trimmed:
        return s
    if trimmed in EN_BY_ZH:
        return polysh(t.replace(trimmed, EN_BY_ZH[trimmed], 1))
    for rx, tpl in _COMPILED:
        m = rx.match(trimmed)
        if m:
            return polysh(t.replace(trimmed, fill(tpl, m), 1))
    if trimmed in PUNCT:
        return t.replace(trimmed, PUNCT[trimmed], 1)
    return s


def cjk_count(s):
    return len(CJK.findall(s or ""))


def rule_index(s):
    """返回整串按 RULES 命中的规则序号（0 基），未命中返回 None。"""
    trimmed = (s or "").strip()
    for i, (rx, _tpl) in enumerate(_COMPILED):
        if rx.match(trimmed):
            return i
    return None


def rule_source(name="tools/panel_en.py", rev=None):
    """读取指定 revision 的 panel_en.py 的 RULES——用于「改动前」对照。

    rev 为 None 时读工作区文件；否则用 git show <rev>:<name>（不复制第二份规则）。
    """
    if rev is None:
        return list(RULES)
    import subprocess
    root = os.path.dirname(HERE)
    out = subprocess.run(["git", "-C", root, "show", "%s:%s" % (rev, name)],
                         capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError("git show %s:%s 失败：%s" % (rev, name, out.stderr.strip()))
    ns = {}
    exec(compile(out.stdout, "<panel_en@%s>" % rev, "exec"), ns)
    return list(ns["RULES"])