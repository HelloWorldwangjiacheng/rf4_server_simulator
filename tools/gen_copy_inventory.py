#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 rf4-i18n-01 的 M1 文案清单 copy_inventory.json。

目的：把改前代码里所有硬编码中文**位置**固定下来，并给出 page.section.element
形式的候选 key，供 M2/M3 逐条替换时对照。

覆盖范围（= 用户确认的 UI 骨架：页面标题、区块标题、按钮、表单标签、表头、
空状态、确认/提示语、帮助文本、枚举值展示名）：
- 8080：internal/admin/web/index.html + app/**.js（SPA 全部页面模块）
- 9500：cmd/launcher/panel.html

不覆盖：
- legacy.html（未被 index.html 引用，只被 ui 测试当文本夹具）
- internal/portal/web（玩家端 /portal/ 页面，不属于本任务两个页面）
- 服务端 Go 源码里的字符串（运行日志正文 = 数据，按白名单口径保留中文）

纯标准库、幂等；--repo 指向被审计的仓库。
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

CJK = re.compile(r"[\u4e00-\u9fff]")

# 常见 UI 词 → key 片段（长的优先匹配，故按长度降序匹配）
VOCAB = {
    "保存": "save", "取消": "cancel", "放弃": "discard", "确认": "confirm", "确定": "ok",
    "开始": "start", "停止": "stop", "重启": "restart", "启动": "launch", "关闭": "close",
    "刷新": "refresh", "重新加载": "reload", "返回": "back", "上一页": "prev", "下一页": "next",
    "删除": "delete", "新增": "add", "编辑": "edit", "修改": "update", "重置": "reset",
    "登录": "login", "退出": "logout", "搜索": "search", "筛选": "filter", "导入": "import",
    "导出": "export", "复制": "copy", "下载": "download", "上传": "upload", "应用": "apply",
    "玩家": "player", "用户": "user", "鱼饵": "bait", "钩子": "hook", "鱼护": "keepnet",
    "邮件": "mail", "商店": "shop", "水域": "waters", "鱼种": "fish", "鱼口": "bite",
    "技能": "skill", "活动": "event", "礼包": "gift", "审计": "audit", "日志": "log",
    "参数": "tuning", "规则": "rule", "配置": "config", "主题": "theme", "版本": "version",
    "更新": "update", "总览": "overview", "关于": "about", "发布说明": "changelog",
    "价格": "price", "库存": "stock", "数量": "count", "名称": "name", "类型": "type",
    "等级": "level", "经验": "exp", "银币": "silver", "金币": "gold", "权重": "weight",
    "天气": "weather", "水温": "temperature", "状态": "status", "时间": "time",
    "错误": "error", "失败": "fail", "成功": "success", "提示": "hint", "帮助": "help",
    "空": "empty", "标题": "title", "说明": "desc", "加载": "loading", "暂无": "empty",
    "没有": "none", "全部": "all", "详情": "detail", "查看": "view", "选择": "select",
    "切换": "switch", "开启": "on", "停用": "off", "在线": "online", "离线": "offline",
    "控制中心": "control", "管理": "admin", "服务器": "server", "运行": "runtime",
    "本地": "local", "官方": "official", "基础": "base", "进阶": "advanced",
    "区域": "region", "主机": "host", "进程": "proc", "网络": "network", "数据库": "db",
    "校验": "validate", "测试": "test", "示例": "example", "单位": "unit", "秒": "sec",
    "分钟": "min", "小时": "hour", "天": "day", "次": "times", "上限": "max", "下限": "min",
}

SECTION_BY_FILE = {
    "core.js": "shell",
    "main.js": "shell",
    "widgets.js": "shell",
    "labels.js": "labels",
    "dashboard": "dashboard",
    "players": "players",
    "shop": "shop",
    "rules": "rules",
    "waters": "waters",
    "hooks": "hooks",
    "bait": "bait",
    "mail": "mail",
    "tuning": "tuning",
    "event-gifts": "event_gifts",
    "zones": "zones",
    "docs": "docs",
    "audit": "audit",
}


def vocab_slug(text):
    """取最长命中词做 slug；命中多个同长取先出现的。"""
    hits = [(w, s) for w, s in VOCAB.items() if w in text]
    if not hits:
        return None
    hits.sort(key=lambda x: (-len(x[0]), text.index(x[0])))
    return hits[0][1]


def strip_js_comments(txt):
    """去掉注释但保留行号（块注释按原换行数补回）。"""
    def block(m):
        return "\n" * m.group(0).count("\n")

    txt = re.sub(r"/\*.*?\*/", block, txt, flags=re.S)
    return re.sub(r"(?m)^(\s*)//.*$", lambda m: m.group(1), txt)


JS_LITERAL = re.compile(r"'([^'\\\n]*)'|\"([^\"\\\n]*)\"|`([^`]*)`")
H_CALL = re.compile(r"""h\(\s*['"]([a-zA-Z][a-zA-Z0-9]*)['"]""")
ATTR_LABEL = re.compile(r"""\b(text|title|label|help|placeholder|desc|name)\s*:\s*$""")


class PanelScanner(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.items = []
        self.stack = []  # (tag, id-or-None, line)
        self.skip_depth = 0
        self.section = "page"
        self.line = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        line = self.getpos()[0]
        if tag in ("style", "script"):
            self.skip_depth += 1
            if tag == "style":
                self.stack.append((tag, None, line))
            return
        eid = a.get("id")
        cls = a.get("class", "")
        if eid and (eid.startswith("view-") or eid in ("hero", "main")):
            self.section = eid.replace("view-", "").replace("hero", "hero")
        for key in ("placeholder", "title", "aria-label", "alt"):
            v = a.get(key)
            if v and CJK.search(v):
                self.items.append({
                    "zh": v.strip(), "line": line, "kind": "attr", "attr": key,
                    "tag": tag, "id": eid, "class": cls, "section": self.section,
                })
        if tag in ("input", "br", "img", "meta", "link", "hr"):
            return
        self.stack.append((tag, eid, line))

    def handle_endtag(self, tag):
        if tag in ("style", "script"):
            self.skip_depth = max(0, self.skip_depth - 1)
            if tag == "style" and self.stack:
                self.stack.pop()
            return
        if tag in ("input", "br", "img", "meta", "link", "hr"):
            return
        if self.stack:
            self.stack.pop()

    def handle_data(self, data):
        if self.skip_depth:
            return
        t = data.strip()
        if not t or not CJK.search(t):
            return
        tag, eid, line = self.stack[-1] if self.stack else ("html", None, 0)
        self.items.append({
            "zh": t, "line": self.getpos()[0], "kind": "text", "attr": "",
            "tag": tag, "id": eid, "class": "", "section": self.section,
            "owner_line": line,
        })


def git_head(repo):
    try:
        out = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                             capture_output=True, text=True, check=True)
        return out.stdout.strip()
    except Exception:
        return "unknown"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="shared/work/rf4_server_simulator")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    here = Path(__file__).resolve().parent.parent
    repo = Path(args.repo)
    out_path = Path(args.out) if args.out else here / "copy_inventory.json"

    entries = []
    seq = {}

    def add(page, section, zh, file, line, kind, tag, eid="", extra=None):
        base = vocab_slug(zh) or "t%d" % (len(entries) + 1)
        k = (page, section, base)
        seq[k] = seq.get(k, 0) + 1
        element = base if seq[k] == 1 else "%s_%d" % (base, seq[k])
        key = "%s.%s.%s" % (page, section, element)
        row = {
            "key": key,
            "zh": zh,
            "page": page,
            "section": section,
            "file": file,
            "line": line,
            "kind": kind,
            "tag": tag,
            "id": eid,
            "scope_hint": "review" if (("${" in zh) or len(zh) > 40) else "ui",
            "key_confidence": "vocab" if elem_vocab(base) else "fallback",
        }
        if extra:
            row.update(extra)
        entries.append(row)

    # ---- 8080: admin SPA ----
    idx = repo / "internal/admin/web/index.html"
    if idx.is_file():
        txt = idx.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"<title>([^<]*)</title>", txt):
            if CJK.search(m.group(1)):
                add("admin", "shell", m.group(1).strip(), "internal/admin/web/index.html",
                    txt[:m.start()].count("\n") + 1, "text", "title")

    for f in sorted((repo / "internal/admin/web/app").rglob("*.js")):
        raw = f.read_text(encoding="utf-8", errors="replace")
        txt = strip_js_comments(raw)
        rel = str(f.relative_to(repo))
        section = SECTION_BY_FILE.get(f.name, f.stem.replace("-", "_"))
        for m in JS_LITERAL.finditer(txt):
            s = m.group(1) or m.group(2) or m.group(3) or ""
            if not s or not CJK.search(s):
                continue
            line = txt[:m.start()].count("\n") + 1
            tag = ""
            for hm in H_CALL.finditer(txt, max(0, m.start() - 300), m.start()):
                tag = hm.group(1)
            before = txt[max(0, m.start() - 40):m.start()]
            am = ATTR_LABEL.search(before)
            kind = "attr:" + am.group(1) if am else "text"
            add("admin", section, s, rel, line, kind, tag)

    # ---- 9500: launcher panel ----
    panel_rel = "cmd/launcher/panel.html"
    p = PanelScanner()
    panel_txt = (repo / panel_rel).read_text(encoding="utf-8", errors="replace")
    p.feed(panel_txt)

    # panel.html 的分区锚点：tab 视图与 h2 小标题（按首次出现行号排序）
    anchor_slugs = [
        ("开始前确认", "steps"), ("服务器工作台", "workbench"), ("后台信息", "info"),
        ("更多", "more"), ("管理后台登录", "login"), ("使用说明", "guide"),
        ("运行日志", "logs"), ("版本与更新", "version"), ("管理后台准备中", "admin_gate"),
        ("管理后台", "admin"),
    ]
    anchors = []
    for m in re.finditer(r'id="view-(\w+)"', panel_txt):
        anchors.append((panel_txt[:m.start()].count("\n") + 1, "view_" + m.group(1)))
    for m in re.finditer(r"<h[23][^>]*>([^<]*)</h[23]>", panel_txt):
        line = panel_txt[:m.start()].count("\n") + 1
        text = m.group(1)
        for kw, slug in anchor_slugs:
            if kw in text:
                anchors.append((line, slug))
                break
    anchors.sort()
    for it in p.items:
        sec = "page"
        for line, slug in anchors:
            if line <= it["line"]:
                sec = slug
            else:
                break
        it["section"] = sec

    for it in p.items:
        add("panel", it["section"], it["zh"], panel_rel, it["line"], it["kind"], it["tag"],
            it.get("id") or "", {"attr": it.get("attr", ""), "class": it.get("class", "")})

    by_page = {}
    by_section = {}
    for e in entries:
        by_page[e["page"]] = by_page.get(e["page"], 0) + 1
        sk = e["page"] + "." + e["section"]
        by_section[sk] = by_section.get(sk, 0) + 1

    data = {
        "meta": {
            "task": "rf4-i18n-01",
            "phase": "M1 文案清单（改前快照，未改任何代码）",
            "generated_by": "shared/deliverables/rf4-i18n-01/tools/gen_copy_inventory.py",
            "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
            "repo_head": git_head(repo),
            "repo_path": str(repo),
            "baseline_commit_policy": "清单取自 GitHub main=ec58447，非用户本机 /home/wangjc 工作副本",
            "key_scheme": "page.section.element — page∈{admin,panel}；section=页面模块（players/tuning/panel 区域…）；element=从常见 UI 词表推出的英文片段，推不出时用 t<N>",
            "key_note": "key 是候选值，M2 开始前可人工改名；改名只改本清单与资源文件，不影响 baseline_ids.json",
            "counts": {
                "total": len(entries),
                "by_page": by_page,
                "by_section": dict(sorted(by_section.items(), key=lambda kv: -kv[1])),
            },
            "scope_policy": (
                "scope_hint=ui：短标签、无插值的直接展示文本，默认必须双语；"
                "scope_hint=review：含 ${} 插值或 >40 字的长句，需在 M2 人工判断是 UI 文案还是数据/日志拼接。"
                "服务端 Go 源码与 /api/logs 返回的运行日志正文不在本清单，按白名单口径保留中文。"
            ),
            "covered_files": [
                "internal/admin/web/index.html",
                "internal/admin/web/app/**.js",
                "cmd/launcher/panel.html",
            ],
            "excluded_files": [
                {"file": "internal/admin/web/legacy.html", "reason": "未被 index.html 引用，仅被 ui 测试当文本夹具"},
                {"file": "internal/portal/web/**", "reason": "玩家端 /portal/ 页面，非本任务两个页面"},
            ],
        },
        "entries": entries,
    }
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("written:", out_path)
    print("total:", len(entries), "by page:", by_page)
    for k, v in list(sorted(by_section.items(), key=lambda kv: -kv[1]))[:12]:
        print("   ", k, v)
    return 0


def elem_vocab(base):
    return base in set(VOCAB.values())


if __name__ == "__main__":
    sys.exit(main())