#!/usr/bin/env python3
"""生成 i18n 资源：locales/zh.json、locales/en.json、locales.data.js。

输入：
  1. shared/deliverables/rf4-i18n-01/copy_inventory.json（M1 文案清单：持有 key 命名 page.section.element）
  2. tools/en_translations.py（zh 原文 → 英文；带插值的整句用正则模板）

口径：
  - zh.json 的 key 优先用 M1 清单的 key；清单里没有的原文（页面源码里后加的文案）用 admin.m2.tNNN / admin.m3.tNNN 补。
  - en.json 缺某 key 时运行期回退 zh 原文（标准 9），所以不写空串。

用法：python3 tools/gen_locales.py [--check]
幂等：同一输入重复跑，输出字节一致。
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DELIV = os.path.dirname(HERE)
REPO = os.path.abspath(os.path.join(DELIV, "..", "..", "work", "rf4_server_simulator"))
INVENTORY = os.path.join(DELIV, "copy_inventory.json")
APP = os.path.join(REPO, "internal", "admin", "web", "app")
LOCALES = os.path.join(APP, "locales")

sys.path.insert(0, HERE)
from en_translations import EN_BY_ZH, TEMPLATES  # noqa: E402
from en_translations_m3 import EN_BY_ZH_M3  # noqa: E402
from en_templates_m3 import TEMPLATES_M3  # noqa: E402

ALL_TEMPLATES = list(TEMPLATES) + list(TEMPLATES_M3)

# M2 表 + M3 表：同一份 zh 原文只写一次英文。M3 覆盖 M1 清单 ui 的全部条目与页面源码里的字面量。
ALL_EN = dict(EN_BY_ZH)
for _k, _v in EN_BY_ZH_M3.items():
    ALL_EN.setdefault(_k, _v)

# 量词/单位单独成词条：页面上「20 秒」「9999 件」这类整句的模板会把数字与单位拆开，
# 单位要能被词典单独命中才翻得动（模板里的捕获组会再走一层 trPart）。
UNITS = {
    "秒": "s", "分钟": "min", "小时": "h", "天": "d", "米": "m", "千米": "km",
    "克": "g", "千克": "kg", "件": "pcs", "条": "rows", "项": "items", "封": "mails",
    "轮": "rounds", "种": "species", "倍": "×", "%/秒": "%/s",
}
ALL_EN.update(UNITS)

# M3：所有页面段都进语言层（M2 只做了 shell/dashboard/labels/audit/docs/widgets 六段）。
SECTIONS = None


def main():
    inv = json.load(open(INVENTORY, encoding="utf-8"))
    entries = inv["entries"]
    zh, keys = {}, []
    for e in entries:
        section = e.get("section", "").split(".")[-1]
        if SECTIONS is not None and section not in SECTIONS:
            continue
        if e.get("scope_hint") != "ui":
            continue
        k = e["key"]
        if k in zh:
            continue
        zh[k] = e["zh"]
        keys.append(k)

    # 清单里没有的原文（页面源码里后加的文案）：从译文表里补，key 用稳定编号。
    have = set(zh.values())
    extra2, extra3 = 0, 0
    for text in EN_BY_ZH:
        if text in have:
            continue
        extra2 += 1
        zh["admin.m2.t%03d" % extra2] = text
        have.add(text)
    for text in EN_BY_ZH_M3:
        if text in have:
            continue
        extra3 += 1
        zh["admin.m3.t%03d" % extra3] = text
        have.add(text)

    # 单位词条（key 固定，便于审计）：只在 en 缺值时补，不覆盖清单里的同文条目
    for _zh in UNITS:
        zh.setdefault("admin.m3.unit.%s" % _zh, _zh)

    en, missing = {}, []
    for k, v in zh.items():
        if v in ALL_EN:
            en[k] = ALL_EN[v]
        else:
            missing.append((k, v))

    os.makedirs(LOCALES, exist_ok=True)
    write_json(os.path.join(LOCALES, "zh.json"), zh)
    write_json(os.path.join(LOCALES, "en.json"), en)
    write_bundle(os.path.join(APP, "locales.data.js"), zh, en)

    print("zh keys: %d" % len(zh))
    print("en keys: %d" % len(en))
    print("missing en: %d" % len(missing))
    print("zh chars: %d / en chars: %d" % (sum(len(v) for v in zh.values()), sum(len(v) for v in en.values())))
    if os.environ.get("SHOW_MISSING") == "1":
        for k, v in missing:
            print("MISS %s | %s" % (k, v))
    return 0


def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")


def write_bundle(path, zh, en):
    lines = [
        "// 生成物：不要手改。源文件 locales/zh.json + locales/en.json + tools/en_translations.py",
        "// 生成命令：python3 shared/deliverables/rf4-i18n-01/tools/gen_locales.py",
        "export const ZH = {",
    ]
    for k in sorted(zh):
        lines.append("  %s: %s," % (json.dumps(k), json.dumps(zh[k], ensure_ascii=False)))
    lines.append("};")
    lines.append("export const EN = {")
    for k in sorted(en):
        lines.append("  %s: %s," % (json.dumps(k), json.dumps(en[k], ensure_ascii=False)))
    lines.append("};")
    lines.append("export const TEMPLATES = [")
    for pat, repl in ALL_TEMPLATES:
        # Python 的命名分组 (?P<n>) 在 JS 里是 (?<n>)；正则本体其他地方两边一致。
        js_pat = pat.replace("(?P<", "(?<")
        lines.append("  [%s, %s]," % (json.dumps(js_pat), json.dumps(repl, ensure_ascii=False)))
    lines.append("];")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())