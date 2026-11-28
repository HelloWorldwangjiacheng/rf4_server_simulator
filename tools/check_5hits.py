#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A8：5 条运行期漏翻的实跑断言（不许只做静态匹配）。

对 panel.html 里由 JS 拼接出来的**完整字符串**求值 tr()，输出 before → after，
断言 after 的 CJK 字符数为 0。

数据同源：tr() 的实现见 tools/panel_tr_eval.py，键/规则直接来自 tools/panel_en.py，
本脚本不内联任何第二份字典或规则。

用法（仓库根或任意 cwd 均可）：
  python3 tools/check_5hits.py
  python3 tools/check_5hits.py -v          # 同时打印命中的规则序号
退出码：0 = 全部 CJK=0；1 = 有残留；2 = 环境问题。
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from panel_tr_eval import CJK, cjk_count, rule_index, tr  # noqa: E402

TS = "2026-11-28 12:31:44"

# panel.html 的拼接点 → 拼接完成后的字符串。字符串按拼接顺序原样构造。
CASES = [
    # H1 英雄区（panel.html:1334）：
    #   text.textContent = "一切就绪，可以开始游戏了。已稳定运行 " + humanUptime(up) + "。"
    ("H1  hero: 已稳定运行 3 分 12 秒",
     "一切就绪，可以开始游戏了。已稳定运行 " + "3 分 12 秒" + "。"),
    # H1 的其余 humanUptime 出口（panel.html:1083-1089，逐一覆盖）
    ("H1a hero: 刚刚启动", "一切就绪，可以开始游戏了。已稳定运行 " + "刚刚启动" + "。"),
    ("H1b hero: 3 分钟", "一切就绪，可以开始游戏了。已稳定运行 " + "3 分钟" + "。"),
    ("H1c hero: 3 小时 12 分", "一切就绪，可以开始游戏了。已稳定运行 " + "3 小时 12 分" + "。"),
    ("H1d hero: 2 天 3 小时", "一切就绪，可以开始游戏了。已稳定运行 " + "2 天 3 小时" + "。"),
    # H2 构建身份（panel.html:1153 表格行 = "构建：" + buildText(p)）
    ("H2a build row", "构建：" + "0.9.4" + " · 来源：" + "AIGC/rf4_server_simulator"),
    # panel.html:1404 buildText() 返回值本身（无「构建：」前缀）
    ("H2b buildText", "0.9.4" + " · 来源：" + "AIGC/rf4_server_simulator"),
    ("H2c build row, source unknown", "构建：" + "未知" + " · 来源：" + "未知"),
    # H3 物品目录行（panel.html:1113）
    ("H3  items row", "635" + " 件 · 档案 " + "1"),
    # H4 更新提示（panel.html:1464-1466）
    ("H4  note: latest", "你正在使用最新版本。" + " 检查于 " + TS),
    # H5 同函数其余会被拼上「 检查于 …」的 noteText 分支
    ("H5a note: connected", "更新服务已连接。" + " 检查于 " + TS),
    ("H5b note: new stable", "有新的" + "正式版" + "可以下载；当前版本也可以继续使用。" + " 检查于 " + TS),
    ("H5c note: new preview", "有新的" + "预览版" + "可以下载；当前版本也可以继续使用。" + " 检查于 " + TS),
]

# H5 枚举：同一函数里其余 noteText 分支——它们不会随后被拼上「 检查于 …」，
# 单独整条命中字典键；这里一并断言 CJK=0，证明没有第二条漏翻通道。
NOT_APPENDED = [
    ("H5d note: waiting", "启动后会在后台检查新版本，不影响正常使用。"),
    ("H5e note: offline", "暂时读不到版本信息。"),
    ("H5f note: checking", "正在连接更新服务器…"),
    ("H5g note: local build", "自己编译的版本没有构建时间戳，跳过更新检测，不影响使用。"),
    ("H5h note: error with last", "暂时连不上更新服务器，显示的是上次检查到的版本。稍后会自动重试。"),
    ("H5i note: error plain", "暂时连不上更新服务器，稍后会自动重试。不影响正常使用。"),
]

# A10：shortSource() 的产物在 en 页必须原样保留，不能被切片/翻译改写
PATH_CASES = [
    "AIGC/rf4_server_simulator",
    "D:/AIGC/rf4_server_simulator",
]


def main():
    ap = argparse.ArgumentParser(description="A8：5 条漏翻的实跑断言（CJK=0）")
    ap.add_argument("-v", "--verbose", action="store_true", help="打印命中的规则序号")
    a = ap.parse_args()

    bad = 0
    rows = CASES + NOT_APPENDED
    print("== 5 条漏翻：before → after（CJK 计数）==")
    for name, s in rows:
        out = tr(s)
        n = cjk_count(out)
        idx = rule_index(s)
        flag = "OK  " if n == 0 else "HIT "
        if n:
            bad += 1
        extra = ""
        if a.verbose:
            extra = "  rule=%s" % ("#R%02d" % (idx + 1) if idx is not None else "none")
        print("[%s] %-34s CJK %d → %d%s" % (flag, name, cjk_count(s), n, extra))
        print("       before: %s" % s)
        print("       after : %s" % out)

    print("")
    print("== A10 shortSource 产物保持原文 ==")
    for p in PATH_CASES:
        out = tr(p)
        ok = out == p
        if not ok:
            bad += 1
        print("[%s] %-32s -> %s" % ("OK  " if ok else "BAD ", p, out))

    print("")
    print("cases=%d  CJK>0: %d" % (len(rows) + len(PATH_CASES), bad))
    if bad:
        print("RESULT: FAIL（有残留中文，A8 未过）")
        return 1
    print("RESULT: OK（全部 CJK=0）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())