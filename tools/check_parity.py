#!/usr/bin/env python3
"""标准 2：zh/en 语言包 key 对齐。纯标准库。

校验对象：internal/admin/web/app/locales/zh.json 与 en.json（生成物，源是
tools/en_translations.py + M1 文案清单）。

判定：两边 key 集合完全一致（en 是 zh 的子集也可以，缺的 key 运行期回退 zh；
但不许出现 en 有、zh 没有的孤儿 key），keys >= 50，且 zh/en 无空值。

输出固定含 `zh keys: N` / `en keys: N` / `diff: none`。
退出码 0 通过，1 不通过。
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DELIV = os.path.dirname(HERE)
REPO = os.path.abspath(os.path.join(DELIV, "..", "..", "work", "rf4_server_simulator"))
LOCALES = os.path.join(REPO, "internal", "admin", "web", "app", "locales")


def main():
    zh = json.load(open(os.path.join(LOCALES, "zh.json"), encoding="utf-8"))
    en = json.load(open(os.path.join(LOCALES, "en.json"), encoding="utf-8"))
    print("zh keys: %d" % len(zh))
    print("en keys: %d" % len(en))

    problems = []
    for k in sorted(set(zh) - set(en)):
        problems.append("missing en: " + k)
    for k in sorted(set(en) - set(zh)):
        problems.append("orphan en (no zh): " + k)
    for src, d in (("zh", zh), ("en", en)):
        for k, v in d.items():
            if not isinstance(v, str) or not v.strip():
                problems.append("empty %s value: %s" % (src, k))

    if len(zh) < 50:
        problems.append("zh keys < 50")
    if problems:
        print("diff: %d problem(s)" % len(problems))
        for p in problems:
            print("  " + p)
        return 1
    print("diff: none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())