#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 rf4-i18n-01 的 M1 基线快照 baseline_ids.json。

来源是改前代码（commit ec58447）：两端口页面的交互元素 id 与路由状态码表。
纯标准库、离线可跑；重复执行结果幂等（除 generated_at）。

用法（仓库根或任意 cwd）：
    python3 shared/deliverables/rf4-i18n-01/tools/gen_baseline_ids.py \
        --repo shared/work/rf4_server_simulator

口径说明（重要）：
- M1 时本机没有 Go 工具链（`go` 不存在），无法起 8080/9500，因此 id 与路由表
  均从源码静态提取，每条带 file:line 证据。
- 状态码不是猜的：来自路由注册行 + 鉴权包装 `auth(...)`（→401）与
  OVERRIDES 里逐条标注的处理逻辑（file:line），未登记的走 200。
  运行期复核由 tools/sample_route_status.py 在 M2 服务起来后执行，与
  expected_status 逐条比对；两者不一致以运行期为准并回写本文件（届时记
  `confirmed_at`）。
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

INTERACTIVE_TAGS = {"button", "input", "select", "textarea", "a", "form", "details", "summary"}
ID_LOOKS_INTERACTIVE = re.compile(
    r"(btn|Button|toggle|menu|Menu|input|Input|select|Select|login|reload|tab|switch|Switch|"
    r"save|Save|cancel|search|filter|upload|download|link|Link|nav|Nav)", re.IGNORECASE)


class PanelParser(HTMLParser):
    """抽 panel.html 里带 id 的元素，记录标签、行号与可见文本。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self.stack = []
        self.text_by_id = {}

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        eid = a.get("id")
        if eid:
            self.rows.append({
                "id": eid,
                "tag": tag,
                "line": self.getpos()[0],
                "class": a.get("class", ""),
                "type": a.get("type", ""),
                "aria_label": a.get("aria-label", ""),
                "title": a.get("title", ""),
                "placeholder": a.get("placeholder", ""),
            })
            self.stack.append(eid)
            self.text_by_id.setdefault(eid, "")
        if tag in ("input", "br", "img", "meta", "link", "hr"):
            return
        if eid:
            pass

    def handle_endtag(self, tag):
        if tag in ("input", "br", "img", "meta", "link", "hr"):
            return
        if self.stack:
            self.stack.pop()

    def handle_data(self, data):
        if self.stack:
            t = data.strip()
            if t:
                cur = self.stack[-1]
                self.text_by_id[cur] = (self.text_by_id.get(cur, "") + " " + t).strip()


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


def line_of(txt: str, idx: int) -> int:
    return txt[:idx].count("\n") + 1


ADMIN_ID_ATTR = re.compile(r"""id\s*:\s*(['"])([A-Za-z][\w.-]*)\1""")
ADMIN_ID_HTML = re.compile(r"""id="([A-Za-z][\w.-]*)\"""")
H_TAG = re.compile(r"""h\(\s*['"]([a-zA-Z][a-zA-Z0-9]*)['"]""")


def admin_ids(repo: Path):
    rows = []
    web = repo / "internal/admin/web"
    idx = web / "index.html"
    txt = read(idx)
    for m in ADMIN_ID_HTML.finditer(txt):
        rows.append({
            "id": m.group(1), "tag": "div", "file": "internal/admin/web/index.html",
            "line": line_of(txt, m.start()), "interactive": m.group(1) not in ("app",),
            "source": "html-attr",
        })
    for f in sorted((web / "app").rglob("*.js")):
        txt = read(f)
        for m in ADMIN_ID_ATTR.finditer(txt):
            # 找最近的 h('tag', ...) 以确定标签
            tag = None
            best = -1
            for hm in H_TAG.finditer(txt, max(0, m.start() - 400), m.start()):
                tag = hm.group(1)
                best = hm.start()
            rows.append({
                "id": m.group(2),
                "tag": tag or "unknown",
                "file": str(f.relative_to(repo)),
                "line": line_of(txt, m.start()),
                "interactive": (tag in INTERACTIVE_TAGS) or bool(ID_LOOKS_INTERACTIVE.search(m.group(2))),
                "source": "js-h-attr",
            })
    # 去重（同一 id 在多处出现时保留首次，另记 occurrences）
    seen = {}
    for r in rows:
        k = r["id"]
        if k in seen:
            seen[k]["occurrences"] += 1
        else:
            r["occurrences"] = 1
            seen[k] = r
    return list(seen.values())


ADMIN_DYNAMIC_FAMILIES = [
    {
        "pattern": "f_<spec.id或key>_<fieldSeq>",
        "example": "f_bite_delay_max_7",
        "file": "internal/admin/web/app/core.js",
        "line": 636,
        "meaning": "表单控件 id：按字段 spec 的 id/key 生成，序号全局自增",
    },
    {
        "pattern": "pg-<pblock id>",
        "example": "pg-fish_bait",
        "file": "internal/admin/web/app/pages/tuning.js",
        "line": 239,
        "meaning": "游戏参数页的 pblock 锚点 id",
    },
    {
        "pattern": "pg-<pblock id>-<序号>",
        "example": "pg-fish_bait-7",
        "file": "internal/admin/web/app/pages/tuning.js",
        "line": 240,
        "meaning": "游戏参数页子分组锚点",
    },
    {
        "pattern": "pg-grade-<i>",
        "example": "pg-grade-0",
        "file": "internal/admin/web/app/pages/rules.js",
        "line": 145,
        "meaning": "出鱼档位编辑卡 id",
    },
    {
        "pattern": "<调用方传入的 id>（opts.id）",
        "example": "pg-other",
        "file": "internal/admin/web/app/core.js",
        "line": 441,
        "meaning": "pblock 的 id 由调用方给，静态调用点已在上表登记",
    },
    {
        "pattern": "<数据对象自身 id>（z.id / b.id / e.pointerId）",
        "example": "zonemap 节点 id（来自 /api/fish/zones 数据）",
        "file": "internal/admin/web/app/pages/zones.js",
        "line": 565,
        "meaning": "由接口数据驱动，改前改后由同一数据源决定，不参与文案国际化",
    },
]


# 9500 端口（cmd/launcher）的期望状态码覆盖表。未列出的注册路由按 method+auth 推断。
LAUNCHER_OVERRIDES = {
    ("GET", "/"): (200, "handler 直接写 panelHTML", "cmd/launcher/main.go:135"),
    ("GET", "/admin"): (307, "http.Redirect → /admin/", "cmd/launcher/main.go:131"),
    ("GET", "/admin/"): (200, "已就绪时转发 admin handler；未就绪返回 503", "cmd/launcher/main.go:555"),
    ("GET", "/api/status"): (200, "writeJSON", "cmd/launcher/main.go:348"),
    ("GET", "/api/overview"): (200, "writeJSON", "cmd/launcher/main.go:383"),
    ("GET", "/api/logs"): (200, "writeJSON", "cmd/launcher/main.go:453"),
    ("GET", "/api/hosts"): (200, "GET 分支 writeJSON", "cmd/launcher/main.go:424"),
    ("GET", "/api/start"): (204, "actionHandler 成功写 204；会真的起服务，不采样", "cmd/launcher/main.go:464"),
    ("GET", "/api/stop"): (204, "actionHandler 成功写 204；会真的停服务，不采样", "cmd/launcher/main.go:464"),
    ("GET", "/api/restart"): (204, "actionHandler 成功写 204；会真的重启，不采样", "cmd/launcher/main.go:464"),
    ("GET", "/api/game/config"): (405, "仅 POST（requireLocalJSONPost），405 无副作用，可采样", "cmd/launcher/game_launch.go:247"),
    ("GET", "/api/game/launch"): (405, "仅 POST（requireLocalJSONPost），405 无副作用，可采样", "cmd/launcher/game_launch.go:247"),
    ("POST", "/api/game/config"): (400, "空 body 解码失败 → 400；不采样（写盘）", "cmd/launcher/game_launch.go:37"),
    ("POST", "/api/game/launch"): (400, "空 body/路径为空 → 400；不采样（会起游戏进程）", "cmd/launcher/game_launch.go:52"),
    ("POST", "/api/update/dismiss"): (204, "handleUpdateDismiss；会写更新状态文件，不采样", "cmd/launcher/main.go:148"),
    ("GET", "/api/open-admin"): (204, "会打开浏览器窗口，不采样", "cmd/launcher/main.go:149"),
    ("GET", "/api/admin/retry"): (204, "重试挂载 admin handler，不采样", "cmd/launcher/main.go:134"),
    ("GET", "/healthz"): (200, "存活探针", "cmd/launcher/main.go:见 mux"),
}


def parse_launcher_routes(repo: Path):
    txt = read(repo / "cmd/launcher/main.go")
    rows = []
    pat = re.compile(r"""mux\.HandleFunc\(\s*"([^"]+)\"""")
    for m in pat.finditer(txt):
        spec = m.group(1)
        line = line_of(txt, m.start())
        if " " in spec:
            method, path = spec.split(" ", 1)
        else:
            method, path = "ANY", spec
        key_method = method if method != "ANY" else "GET"
        code, why, src = LAUNCHER_OVERRIDES.get((key_method, path), (200, "未特别标注，按 200", "cmd/launcher/main.go"))
        sample = "sample"
        if any(w in why for w in ("不采样", "不参与")):
            sample = "skip"
        rows.append({
            "method": method if method != "ANY" else "GET",
            "path": path,
            "expected_status": code,
            "auth": "none",
            "reason": why,
            "source": src,
            "registered_at": "cmd/launcher/main.go:%d" % line,
            "sample_policy": sample,
        })
    return rows


ADMIN_OVERRIDES = {
    ("POST", "/api/login"): (400, "空 body 解码失败 → 400；正确凭据 200、错误凭据 401，不采样", "skip"),
}


def parse_admin_routes(repo: Path):
    txt = read(repo / "internal/admin/api.go")
    rows = []
    pat = re.compile(r"""mux\.HandleFunc\(\s*"([^"]+)"\s*,\s*(auth\()?""")
    for m in pat.finditer(txt):
        spec = m.group(1)
        authed = bool(m.group(2))
        line = line_of(txt, m.start())
        if " " in spec:
            method, path = spec.split(" ", 1)
        else:
            method, path = "GET", spec
        code, why, sample = ADMIN_OVERRIDES.get((method, path), (None, None, None))
        rows.append({
            "method": method,
            "path": path,
            "expected_status": code if code is not None else (401 if authed else 200),
            "auth": "bearer" if authed else "none",
            "reason": why or ("withAuth 无 Bearer → 401" if authed else "匿名只读/登录入口，DB 就绪 → 200"),
            "source": "internal/admin/api.go:%d" % line,
            "registered_at": "internal/admin/api.go:%d" % line,
            "sample_policy": sample or ("sample" if method == "GET" else "skip"),
        })
    # 静态资源与前缀处理器
    for path, why, line in [
        ("/", "SPA 静态文件（index.html → 200）", None),
        ("/maps/", "纸地图贴图（素材不入仓库，缺素材可能 404，不采样）", None),
        ("/icons/", "物品/鱼种图标（同上，不采样）", None),
    ]:
        rows.append({
            "method": "GET", "path": path, "expected_status": 200, "auth": "none",
            "reason": why, "source": "internal/admin/api.go:131-136",
            "registered_at": "internal/admin/api.go", "sample_policy": "sample" if path == "/" else "skip",
        })
    return rows


def git_head(repo: Path) -> str:
    try:
        out = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                             capture_output=True, text=True, check=True)
        return out.stdout.strip()
    except Exception:
        return "unknown"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="shared/work/rf4_server_simulator")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    here = Path(__file__).resolve().parent
    repo = Path(args.repo)
    if not (repo / "go.mod").is_file():
        print("repo 不对：%s 下没有 go.mod" % repo, file=sys.stderr)
        return 2
    out_path = Path(args.out) if args.out else here / "baseline_ids.json"

    admin = admin_ids(repo)
    panel = PanelParser()
    panel.feed(read(repo / "cmd/launcher/panel.html"))
    for r in panel.rows:
        r["file"] = "cmd/launcher/panel.html"
        r["source"] = "html-attr"
        r["interactive"] = (r["tag"] in INTERACTIVE_TAGS) or bool(ID_LOOKS_INTERACTIVE.search(r["id"])) \
            or bool(r["aria_label"]) or bool(r["placeholder"])
        r["text"] = panel.text_by_id.get(r["id"], "")

    r8080 = parse_admin_routes(repo)
    r9500 = parse_launcher_routes(repo)

    data = {
        "meta": {
            "task": "rf4-i18n-01",
            "phase": "M1 改前基线（未改任何代码）",
            "generated_by": "shared/deliverables/rf4-i18n-01/tools/gen_baseline_ids.py",
            "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
            "repo_head": git_head(repo),
            "repo_path": str(repo),
            "baseline_commit_policy": "baseline 取自 GitHub main=ec58447，非用户本机 /home/wangjc 工作副本",
            "method": (
                "静态提取：从本 commit 的源码抽 id 与路由注册。M1 时本机无 Go 工具链，"
                "两端口均无法起服务，故未做运行期采样；运行期复核见 tools/sample_route_status.py，"
                "在 M2 服务起来后执行，与 expected_status 逐条比对。"
            ),
            "status_code_source": "路由注册行 + auth(...)→401 + LAUNCHER_OVERRIDES 逐条标注（见各条 source）",
            "mtime_requirement": "本文件必须早于任何模板/静态资源改动（M1 阶段零改动）",
        },
        "ports": {
            "8080": {
                "app": "cmd/admin（独立调试监听）→ internal/admin/web SPA",
                "page": "http://127.0.0.1:8080/",
                "id_count": len(admin),
                "interactive_id_count": sum(1 for r in admin if r["interactive"]),
                "ids": sorted(admin, key=lambda r: r["id"]),
                "dynamic_id_families": ADMIN_DYNAMIC_FAMILIES,
                "files_scanned": [
                    "internal/admin/web/index.html",
                    "internal/admin/web/app/*.js（含 pages/）",
                ],
                "excluded": [
                    {"file": "internal/admin/web/legacy.html",
                     "reason": "未被 index.html 引用，仅被 internal/admin/*_ui_test.cjs 当文本夹具读，不是对外页面"},
                ],
            },
            "9500": {
                "app": "cmd/launcher（控制中心，默认 127.0.0.1:9500）",
                "page": "http://127.0.0.1:9500/",
                "id_count": len(panel.rows),
                "interactive_id_count": sum(1 for r in panel.rows if r["interactive"]),
                "ids": sorted(panel.rows, key=lambda r: (r["line"], r["id"])),
                "dynamic_id_families": [],
                "files_scanned": ["cmd/launcher/panel.html"],
            },
        },
        "routes": {
            "8080": r8080,
            "9500": r9500,
        },
        "route_count": {"8080": len(r8080), "9500": len(r9500)},
    }

    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("written:", out_path)
    print("8080 ids: %d（交互 %d）; 9500 ids: %d（交互 %d）" % (
        len(admin), data["ports"]["8080"]["interactive_id_count"],
        len(panel.rows), data["ports"]["9500"]["interactive_id_count"]))
    print("routes: 8080=%d, 9500=%d" % (len(r8080), len(r9500)))
    return 0


if __name__ == "__main__":
    sys.exit(main())