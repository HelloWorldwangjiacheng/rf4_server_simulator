# -*- coding: utf-8 -*-
"""生成 M3 英文译文表模块：把 work/m3/out_{A,B,C,D}.json 合并成 tools/en_translations_m3.py。

这些译文由技术主管在 M3 逐条给出（1063 条，覆盖 M1 清单 scope_hint=ui 的全部条目 +
页面源码里的中文文案字面量），键是中文原文，值是英文译文。
生成物可重现：改动 out_*.json 后重跑本脚本即可。
"""
import json
import os

OUT = os.path.dirname(os.path.abspath(__file__))
DELIV = os.path.dirname(OUT)
SRC = "/home/rakazo/shared/work/m3"

merged = {}
for tag in "ABCD":
    d = json.load(open(os.path.join(SRC, "out_%s.json" % tag), encoding="utf-8"))
    for k, v in d.items():
        merged.setdefault(k, v)

lines = [
    "# -*- coding: utf-8 -*-\n"
    '"""M3 英文译文表（生成物）：中文原文 → 英文。\n\n'
    "来源：技术主管 M3 逐条翻译的 1063 条（work/m3/out_A..D.json），覆盖 M1 清单\n"
    "scope_hint=ui 的全部条目，以及页面源码（internal/admin/web/app/*.js、pages/*.js）\n"
    "里出现的中文文案字面量。生成命令：tools/gen_en_m3.py\n"
    '"""\n\nEN_BY_ZH_M3 = {'
]
for k in sorted(merged):
    lines.append("    %s: %s," % (json.dumps(k, ensure_ascii=False), json.dumps(merged[k], ensure_ascii=False)))
lines.append("}")
open(os.path.join(OUT, "en_translations_m3.py"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
print("en_translations_m3.py: %d entries" % len(merged))