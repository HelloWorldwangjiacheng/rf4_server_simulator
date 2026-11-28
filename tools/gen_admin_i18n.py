#!/usr/bin/env python3
r"""生成 internal/admin/web/app/locales.data.js（管理后台 i18n 字典，生成物）。

源与产物（都在仓库内，脚本只用标准库，不需要 node）：
  输入  internal/admin/web/app/locales/zh.json  zh 原文（key → 中文）
  输入  internal/admin/web/app/locales/en.json  en 译文（key → 英文，键集与 zh 相同）
  输入  本文件里的 TEMPLATES（带占位的中文句式 → 英文模板，按顺序匹配）
  产物  internal/admin/web/app/locales.data.js  ZH / EN / TEMPLATES 三个导出

口径：
  - 字典按 key 排序输出，键集必须两边相同（脚本会校验，不等就退出码 1）。
  - 正则里的非 ASCII 字符输出成 \uXXXX，源码保持纯 ASCII，避免编辑器/换行差异。
  - 模板按「整句匹配」用：正则必须以 $ 结尾，杜绝把「后面还有内容」的服务器原文截断替换。

用法：
  python3 tools/gen_admin_i18n.py            # 生成并写入
  python3 tools/gen_admin_i18n.py --check    # 只比较，不写文件；不一致退出码 1
退出码：0 = 一致/写入成功；1 = 键集不等或 --check 不一致。
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_REPO = os.path.dirname(HERE)

# 带插值的句式：中文（zh 原文，匹配用）→ 英文模板（{0}/{name} 占位）。
# 只放「整句」规则；捕获组里的玩家名、ID、服务器原文不进字典，原样保留。
TEMPLATES = [
    ('^(?<n>\\d+)\\s*分钟前$', '{n} min ago'),
    ('^(?<n>\\d+)\\s*小时前$', '{n} h ago'),
    ('^(?<n>\\d+)\\s*天前$', '{n} d ago'),
    ('^(?<n>\\d+)\\s*项$', '{n} items'),
    ('^(?<n>\\d+)\\s*条$', '{n} rows'),
    ('^(?<n>\\d+)\\s*项修改尚未保存$', '{n} unsaved change(s)'),
    ('^未达标 (?<a>[\\d.]+)% · 合格 (?<b>[\\d.]+)% · 奖杯 (?<c>[\\d.]+)% · 蓝冠 (?<d>[\\d.]+)%$', 'Below {a}% · Qualified {b}% · Trophy {c}% · Blue crown {d}%'),
    ('^普通上限 (?<a>[\\d.]+) 秒$', 'Normal max {a}s'),
    ('^普通上限 (?<a>[\\d.]+) 秒 / 饵上限 (?<b>[\\d.]+) 秒$', 'Normal max {a}s / lure max {b}s'),
    ('^(?<n>\\d+) 件商品有覆盖价$', '{n} items have override prices'),
    ('^共 (?<n>\\d+) 条$', '{n} rows total'),
    ('^本地 · (?<p>\\d+) · v(?<v>.+)$', 'Local · {p} · v{v}'),
    ('^在线、档案、物品、参数条数来自 (?<u>.+?)。$', 'Online, profiles, items and tunable counts come from {u}.'),
    ('^关键口径来自 (?<a>.+?) 与 (?<b>.+?)。$', 'Key settings come from {a} and {b}.'),
    ('^日志来自审计表 (?<a>.+?)，不是进程日志。$', 'Log rows come from the audit table {a}, not the process log.'),
    ('^RF4 (管理工作台|管理后台)?\\s*·\\s*本地\\s*(?<p>\\d+)$', 'RF4 Workbench · local {p}'),
    ('^(?<d>.+) · 本地 (?<p>\\d+)$', '{d} · local {p}'),
    ('^范围 (?<a>\\S+) – (?<b>.+)$', 'range {a} – {b}'),
    ('^默认 (?<v>.+)$', 'default {v}'),
    ('^(?<v>[\\d.]+) 倍$', '{v}×'),
    ('^最长 (?<v>.+)$', 'max {v}'),
    ('^固定 (?<v>.+)$', 'fixed {v}'),
    ('^先显示 (?<n>.+)$', 'showing first {n}'),
    ('^本地 (?<v>.+)$', 'local {v}'),
    ('^(?<n>[\\d.]+) (?<u>秒|分钟|小时|米|克|件|条|项|封|个)$', '{n} {u}'),
    ('^(?<v>[\\d.]+) %/秒$', '{v} %/s'),
    ('^本次查询显示 (?<a>[\\d.]+) / (?<b>[\\d.]+) 件$', 'Showing {a} of {b} items'),
    ('^(?<a>[\\d.]+) 银 / (?<b>[\\d.]+) 金 / (?<c>[\\d.]+) 件$', '{a} silver / {b} gold / {c} pcs'),
    ('^(?<a>[\\d.]+) 银 / (?<b>[\\d.]+) 金$', '{a} silver / {b} gold'),
    ('^(?<n>[\\d.]+) (?<u>秒|轮|件|个|种|条|项|封|米|克|小时|分钟)$', '{n} {u}'),
    ('^(?<n>[\\d.]+) 种鱼$', '{n} species'),
    ('^(?<n>[\\d.]+) 个格子$', '{n} cells'),
    ('^(?<n>[\\d.]+) 个型号$', '{n} models'),
    ('^(?<n>[\\d.]+) 种鱼 · 仅影响此水域$', '{n} species · this water only'),
    ('^启用全部 (?<n>[\\d.]+) 种$', 'Enable all {n}'),
    ('^停用全部 (?<n>[\\d.]+) 种$', 'Disable all {n}'),
    ('^共 (?<n>[\\d.]+) 条$', '{n} rows'),
    ('^第 (?<n>[\\d.]+) 组$', 'Group {n}'),
    ('^已填入 (?<n>[\\d.]+) 个空白阶段。$', 'Filled in {n} blank stages.'),
    ('^店铺列表（(?<n>[\\d.]+) 家）$', 'Shop list ({n})'),
    ('^找到 (?<n>[\\d.]+) 个$', 'Found {n}'),
    ('^间隔 (?<n>[\\d.]+) 秒$', 'Every {n} s'),
    ('^阶段 (?<n>[\\d.]+)$', 'Stage {n}'),
    ('^（(?<n>[\\d.]+) 项，一般不用改）$', '({n} items, usually left alone)'),
    ('^(?<h>.+) （(?<n>[\\d.]+) 项，一般不用改）$', '{h} ({n} items, usually left alone)'),
    ('^(?<h>.+)（(?<n>[\\d.]+) 项，一般不用改）$', '{h} ({n} items, usually left alone)'),
    ('^吃 (?<a>.+?) 等 (?<n>[\\d.]+) 种$', 'Eats {a} and others ({n} in total)'),
    ('^吃 (?<a>.+)$', 'Eats {a}'),
    ('^不吃 (?<a>.+)$', 'Does not eat {a}'),
    ('^（现在：(?<v>.+)）$', '(now {v})'),
    ('^收件人：\\s*(?<v>.+)$', 'Recipient: {v}'),
    ('^当前预设：(?<v>.+?)。预设覆盖前六项；欢乐时光独立。$', 'Current preset: {v}. A preset covers the first six rules; happy hour is separate.'),
    ('^圆形，半径 (?<r>[\\d.]+) 米$', 'Circle, radius {r} m'),
    ('^圆形，半径 (?<r>[\\d.]+) 米，圆心在 (?<c>.+)$', 'Circle, radius {r} m, centre at {c}'),
    ('^(?<a>[\\d.]+)×(?<b>[\\d.]+) 米$', '{a}×{b} m'),
    ('^(?<a>[\\d.]+)×(?<b>[\\d.]+) 米，游戏坐标 (?<c>.+) · 松开完成$', '{a}×{b} m, game coords {c} · release to finish'),
    ('^已划鱼群区域：(?<n>[\\d.]+) 个。$', 'Shoal zones drawn: {n}.'),
    ('^(?<span>.+?) g 以下$', 'under {span} g'),
    ('^已切换到「(?<t>.+)」，最多 30 秒生效$', 'Switched to "{t}"; takes effect within 30 seconds'),
    ('^已切换到「(?<t>.+)」，约 30 秒内生效$', 'Switched to "{t}"; takes effect within about 30 seconds'),
    ('^已保存「(?<s>.+)」，在线玩家立即收到刷新$', 'Saved "{s}"; online players refresh immediately'),
    ('^已加入「(?<s>.+)」，记得保存$', 'Added "{s}" — remember to save'),
    ('^封禁「(?<p>.+)」？$', 'Ban "{p}"?'),
    ('^恢复「(?<i>.+)」的整件覆盖？$', 'Restore the whole-item override for "{i}"?'),
    ('^找不到店铺：(?<id>.+)$', 'Shop not found: {id}'),
    ('^(?<id>.+)（当前编辑，不在所选水.+$', '{id} (currently editing, not in the selected water list)'),
    ('^已确认保存：(?<a>.+?)；待重试：(?<b>.+?)。(?<e>.*)$', 'Saved: {a}; retrying: {b}. {e}'),
    ('^预设读取失败，草稿未变：(?<e>.+)$', 'Could not read the preset; the draft is unchanged: {e}'),
    ('^(?<n>[\\d.]+) 封$', '{n} mails'),
    ('^请求失败（HTTP (?<code>[\\d.]+)）$', 'Request failed (HTTP {code})'),
]

HEADER = (
    "// 生成物：不要手改。源文件 locales/zh.json + locales/en.json + tools/gen_admin_i18n.py\n"
    "// 源文件即 locales/zh.json（zh 原文）与 locales/en.json（en 译文）；运行期缺 en 时回退 zh 原文。\n"
)


def js_str(s):
    out = []
    for ch in s:
        o = ord(ch)
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        else:
            out.append(ch)
    return "".join(out)


def js_pat(s):
    """正则源码：非 ASCII 一律 \\uXXXX，保证 .js 是纯 ASCII。"""
    return "".join("\\u%04x" % ord(ch) if ord(ch) > 126 else js_str(ch) for ch in s)


def render(zh, en, templates):
    buf = [HEADER, "export const ZH = {\n"]
    for k in sorted(zh):
        buf.append('  "%s": "%s",\n' % (js_pat(k), js_str(zh[k])))
    buf.append("};\nexport const EN = {\n")
    for k in sorted(en):
        buf.append('  "%s": "%s",\n' % (js_pat(k), js_str(en[k])))
    buf.append("};\nexport const TEMPLATES = [\n")
    for pat, tpl in templates:
        buf.append('  ["%s", "%s"],\n' % (js_pat(pat), js_str(tpl)))
    buf.append("];\n")
    return "".join(buf)


def load(repo):
    base = os.path.join(repo, "internal", "admin", "web", "app")
    with open(os.path.join(base, "locales", "zh.json"), encoding="utf-8") as f:
        zh = json.load(f)
    with open(os.path.join(base, "locales", "en.json"), encoding="utf-8") as f:
        en = json.load(f)
    return base, zh, en


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=DEFAULT_REPO)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    base, zh, en = load(args.repo)
    if set(zh) != set(en):
        missing = sorted(set(zh) ^ set(en))
        sys.stderr.write("键集不一致：%s\n" % ", ".join(missing[:10]))
        return 1
    for pat, _ in TEMPLATES:
        if not pat.endswith("$"):
            sys.stderr.write("模板必须以 $ 结尾（整句匹配）：%s\n" % pat)
            return 1
    text = render(zh, en, TEMPLATES)
    out = os.path.join(base, "locales.data.js")
    if args.check:
        with open(out, encoding="utf-8") as f:
            cur = f.read()
        if cur != text:
            sys.stderr.write("locales.data.js 与源不一致\n")
            return 1
        print("locales.data.js 与源一致（%d 条字典，%d 条模板）" % (len(zh), len(TEMPLATES)))
        return 0
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print("wrote %s（%d 条字典，%d 条模板）" % (out, len(zh), len(TEMPLATES)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
