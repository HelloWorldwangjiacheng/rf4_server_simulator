#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A6：RULES 顺序回归——新增整句锚定规则不得遮蔽既有更具体的规则。

做法：
  * 「改动前」的 RULES 从同一个文件的历史版本读取（git show <ref>:tools/panel_en.py），
    不复制第二份规则表；读不到 git 时用 --before-file 指定基线文件。
  * 「改动后」的 RULES 直接 import tools/panel_en.py。
  * 对每条**既有**规则给 1 个样例，分别求「改动前命中的规则」与「改动后命中的规则」，
    要求两者指向同一条规则文本（语义等价判定：规则源码逐字相同）。

输出格式：rule → sample → 命中规则序号（改动前 / 改动后）。

用法：
  python3 tools/check_rules_order.py
  python3 tools/check_rules_order.py --before-ref 41eaa2b
  python3 tools/check_rules_order.py --before-file /path/to/panel_en_base.py
退出码：0 = 无遮蔽；1 = 有样例被更前面的新规则抢走；2 = 环境问题。
"""
import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from panel_en import RULES as RULES_AFTER  # noqa: E402
from panel_tr_eval import rule_source  # noqa: E402

# 每条既有规则（rf4-i18n-01 交付时的 20 条）1 个样例。
# 样例按「该规则原本要吃的整节点文本」构造，包含它原本的锚定位置。
SAMPLES = [
    "当前版本过旧，建议尽快升级到 0.9.5",
    "新版本 0.9.5 可以下载了",
    "已复制 12 行",
    "已完成 2/3",
    "有新的正式版可以下载；当前版本也可以继续使用。",
    "检查于 2026-11-28 12:31:44",
    "「gateway」没有正常运行。请在组件表中查看对应进程日志。",
    "已稳定运行 3 分钟",
    "3 分钟",
    "3 小时",
    "2 天",
    "12 项",
    "635 件 · 档案",
    "800 行 · 内存里保留最近 800 行",
    "3 小时 12 分",
    "2 天 3 小时",
    "登录失败（HTTP 401）",
    "2/2 运行中",
    "最近一次出错：connection reset",
    "已运行 5 周",
]


def first_match(rules, s):
    s = s.strip()
    for i, (p, _t) in enumerate(rules):
        if re.match(p, s):
            return i
    return None


def load_before(a):
    if a.before_file:
        ns = {}
        with open(a.before_file, encoding="utf-8") as f:
            exec(compile(f.read(), a.before_file, "exec"), ns)
        return list(ns["RULES"]), a.before_file
    try:
        return rule_source("tools/panel_en.py", a.before_ref), "git %s:tools/panel_en.py" % a.before_ref
    except Exception as e:
        print("读不到改动前的 RULES：%s" % e, file=sys.stderr)
        return None, None


def main():
    ap = argparse.ArgumentParser(description="A6：RULES 顺序回归（新规则不遮蔽旧规则）")
    ap.add_argument("--before-ref", default="HEAD~1",
                    help="改动前的 git revision（默认 HEAD~1，即 01 交付树）")
    ap.add_argument("--before-file", default=None,
                    help="改动前的 panel_en.py 路径（没有 git 时用）")
    a = ap.parse_args()

    before, src = load_before(a)
    if before is None:
        return 2
    after = list(RULES_AFTER)
    print("before rules: %d（%s）" % (len(before), src))
    print("after  rules: %d（tools/panel_en.py）" % len(after))
    print("")

    if len(SAMPLES) < len(before):
        print("样例数 %d 少于既有规则数 %d，补样例后再跑。" % (len(SAMPLES), len(before)), file=sys.stderr)
        return 2

    bad = 0
    print("%-4s %-4s %-4s %-8s %s" % ("旧#", "新#", "结果", "是否同位", "样例"))
    for i in range(len(before)):
        s = SAMPLES[i]
        bi = first_match(before, s)
        ai = first_match(after, s)
        same_rule = (bi is not None and ai is not None and after[ai][0] == before[bi][0])
        ok = same_rule
        if not ok:
            bad += 1
        tag = "OK" if ok else "SHADOW"
        if ok and bi != i:
            # 样例被更靠前的既有规则吃掉：这是改动前就存在的遮蔽，不是本轮引入。
            # 判定只要求「改动前后由同一条规则命中」，所以不算 FAIL，但如实标出。
            tag = "OK*"
        print("%-4s %-4s %-5s %-8s %s" % (
            "#R%02d" % (bi + 1) if bi is not None else "-",
            "#R%02d" % (ai + 1) if ai is not None else "-",
            tag,
            "是" if same_rule else "否",
            s))
        if ok and bi != i:
            print("      注：目标规则 #R%02d 在本样例上被更靠前的 #R%02d 命中"
                  "（改动前即如此，本轮未改变）；下面仍列出目标规则源码。" % (i + 1, bi + 1))
        print("      目标规则 #R%02d: %s" % (i + 1, before[i][0]))
        print("      改动前命中: %s" % (before[bi][0] if bi is not None else "(未命中)"))
        print("      改动后命中: %s" % (after[ai][0] if ai is not None else "(未命中)"))

    # 追加规则本身也要能被自己的样例命中（防止写死不生效）
    print("")
    print("== 新增规则自检（追加段）==")
    new_rules = after[len(before):]
    if not new_rules:
        print("没有新增规则。")
    for j, (p, t) in enumerate(new_rules):
        idx = first_match(after, SAMPLE_FOR_NEW[j]) if j < len(SAMPLE_FOR_NEW) else None
        ok = idx is not None and after[idx][0] == p
        if not ok:
            bad += 1
        print("[%s] #R%02d %s  ← 样例: %s" % (
            "OK  " if ok else "FAIL", len(before) + j + 1, p,
            SAMPLE_FOR_NEW[j] if j < len(SAMPLE_FOR_NEW) else "(缺样例)"))

    print("")
    if bad:
        print("RESULT: FAIL（%d 条被遮蔽/未生效）" % bad)
        return 1
    print("RESULT: OK（既有规则全部同位；新增规则全部按序生效）")
    return 0


# 新增规则（表尾追加段）各自的样例，顺序与 panel_en.py 追加段一致
SAMPLE_FOR_NEW = [
    "一切就绪，可以开始游戏了。已稳定运行 刚刚启动。",
    "一切就绪，可以开始游戏了。已稳定运行 3 分 12 秒。",
    "一切就绪，可以开始游戏了。已稳定运行 3 分钟。",
    "一切就绪，可以开始游戏了。已稳定运行 3 小时 12 分。",
    "一切就绪，可以开始游戏了。已稳定运行 2 天 3 小时。",
    "一切就绪，可以开始游戏了。已稳定运行 5 周。",
    "构建：0.9.4 · 来源：AIGC/rf4_server_simulator",
    "0.9.4 · 来源：AIGC/rf4_server_simulator",
    "635 件 · 档案 1",
    "你正在使用最新版本。 检查于 2026-11-28 12:31:44",
    "更新服务已连接。 检查于 2026-11-28 12:31:44",
    "有新的正式版可以下载；当前版本也可以继续使用。 检查于 2026-11-28 12:31:44",
]

if __name__ == "__main__":
    raise SystemExit(main())