# rf4-i18n-01 · 管理后台（8080）与 launcher 面板（9500）中英双语

任务 id：`rf4-i18n-01`　阶段：**M3**（9500 页面双语 + 8080 其余页面实翻 + Windows 校验包）
副本：`shared/work/rf4_server_simulator`，HEAD = `ec58447d06452072647d7ec26d7a7b59f581c649`
本轮日期：2026-11-28（时间一律取自 `date -Is` 原始输出，见 `notes/M3-selfcheck.log`）

## 做了什么

### 1. 共享 i18n 基础设施（M2 建好，M3 扩到全部页面）
- `internal/admin/lang_page.go`：8080 页面壳按语言改写——`<html lang>`、`<title>`、`window.__LANG__`、
  切换控件 `#lang-switch`。优先级 `?lang=` > cookie `lang` > `Accept-Language` > 默认 `zh`；
  用 `?lang=` 访问时回写 cookie（`Path=/`、`Max-Age=31536000`、`SameSite=Lax`）。
  路由表零增零改（`/` 与 `/index.html` 走这个 handler，其余静态资源仍是 `http.FileServer`）。
- `internal/admin/web/app/i18n.js`：`t(key)` 取文案、`tr(zh原文)` 按原文取 key、
  `translateDom(root)` 替换「用户看得见的文本节点」（幂等）、`startLangObserver()` 用
  MutationObserver 兜住异步插入的日志/提示/弹窗。缺 en 值回退 zh 原文，不出空串/裸 key。
  M3 增加了两层能力：
  - **整句优先、分段兜底**：先按整句查字典/模板，整句不认识再按 `" · "` 分段各翻一次
    （页面里大量提示是「说明 · 范围 a – b · 默认 c」这样拼出来的）。
  - **模板捕获组递归**：模板匹配到的片段（如「默认 1 倍」里的「1 倍」）再走一层翻译。
- `internal/admin/web/app/locales/zh.json` + `en.json`：**1608 个 key，双包完全对齐**
  （`check_parity.py`：`diff: none`）。key 命名沿用 M1 清单的 `page.section.element`；
  清单里没有的原文用 `admin.m2.tNNN` / `admin.m3.tNNN` / `admin.m3.unit.<量词>` 补。
- `internal/admin/web/app/locales.data.js`（生成物）：浏览器加载的字典 + 71 条插值模板，
  由 `tools/gen_locales.py` 从上面两个 JSON 生成，不要手改。

### 2. 8080 文案：全部页面实翻（不是只接线）
- `tools/en_translations_m3.py`：**1063 条** zh→en 实译（M3 新增），覆盖 M1 清单
  `scope_hint=ui` 的全部条目（1240 条里的其余部分与 M2 已有 241 条重合）以及页面源码
  （`app/*.js`、`app/pages/*.js`）里的中文文案字面量。加上 M2 的 241 条，共 **1304 条有效译词**。
- `tools/en_templates_m3.py`：**44 条**带插值的整句模板（`范围 a – b`、`默认 c`、`N 种鱼`、
  `吃 A 等 N 种`、`已切换到「X」`、`第 N 组` 等）。
- 结果：13 个页面里 **11 个在 en 下 CJK hits = 0**（dashboard / players / tuning / rules /
  mail / zones / hooks / event-gifts / audit / docs / + 根页）。剩余两个页面的命中全部是
  **游戏数据**（鱼种名、饵名、地图名，例如「葛氏鲈塘鳢」「拉多加湖图」），按简报假设五
  属于数据不是文案，保留中文。逐页原始输出见 `notes/M3-selfcheck.log` 最后一节。

### 3. 9500 launcher 面板双语（M3 新增）
- `cmd/launcher/panel_lang.go`（新增）：9500 的语言口径与 8080 完全相同（同一 cookie 名与参数，
  两个端口共享偏好）。`renderPanel()` 只改页面壳：`<html lang>`、`<title>`、
  `window.RF4_LANG`、顶栏切换控件。`http.SetCookie` 只在 `?lang=` 出现时回写。
- `cmd/launcher/main.go`（改 11 行）：`/` handler 改成按语言渲染页面壳，仍是原来那条 catch-all 路由，
  没有新增/改动任何路由路径。
- `cmd/launcher/panel.html`（新增语言层）：内嵌字典（240 条 zh→en）+ 14 条动态句正则 +
  `tr()`/`walk()`/MutationObserver，等价于 8080 的 `i18n.js`；另有顶栏切换控件与 CSS。
  字典是生成物（源 `tools/panel_en.py`，生成 `tools/gen_panel_i18n.py`，幂等）。
- `cmd/launcher` 未改任何平台适配：没有加 build tag、没有动 `hosts.go` 的 import 结构、
  没有写 harness。`GOOS=windows go build ./cmd/launcher` 通过（本机交叉编译验证）。

### 4. Windows 校验包（9500 运行期验收的全部载体）
- `tools/win_verify_9500.py`：纯标准库，Windows 上 `python tools\win_verify_9500.py` 直接跑。
  自带 PASS/FAIL 判定 + 退出码 + 末尾摘要块。覆盖：9500 15 条路由状态码差集、
  `lang-switch` 锚点数、cookie 回写、仅靠 cookie 取英文页壳、en 页 CJK hits、zh 页 CJK hits、
  缺 key 回退（运行期 `window.__rf4Tr` 实测）。运行日志区单独计数，不计入判定。
  **第 8 项（M3c 追加）`acceptlang-*`**：Accept-Language 协商（标准 6 的 9500 半边），
  判定逻辑在同目录 `tools/check_acceptlang.py`（纯标准库、可独立跑），摘要块因此是 12 项。
- `README_WINDOWS.md`：起停、构建、脚本用法、贴回什么、常见问题。**用户只看这一份。**

### 5. 自检脚本（`tools/`，纯标准库）+ 起停脚本
`check_ids.py`（标准 11 的 id 集合双向差集）、`start_services.sh`（交付物根，标准 13 的起停）、
`check_acceptlang.py`（标准 6 的 9500 半边：Accept-Language 协商，可独立跑）、
`check_parity.py`、`check_page.py`、`check_default.py`、`test_fallback.py`、`sample_route_status.py`、
`gen_locales.py`、`gen_en_m3.py`、`gen_panel_i18n.py`、`selfcheck_m3.sh`、`en_translations.py`、
`en_translations_m3.py`、`en_templates_m3.py`、`panel_en.py`、`whitelist.txt`（1 条）。

## 怎么验证（可直接复制；cwd = `/home/rakazo`）

```bash
# 0) 起 8080（用交付的起停脚本；仓库外二进制，仓库零改动；端口占用会明确报错并退出非 0）
D=shared/deliverables/rf4-i18n-01
$D/start_services.sh start                       # 期望 就绪: http://127.0.0.1:8080/ -> 200，rc=0
$D/start_services.sh status                      # 期望 8080(port 8080): 运行中 … HTTP 200，rc=0
# 别的端口也行（改的是 rf4-run/ 下的临时配置副本，不动仓库 config.yaml）：
#   $D/start_services.sh --port-8080 18080 start
# 9500 这条在任何 Linux 上都会给平台错误并以 2 退出（Windows-only，见 README_WINDOWS.md）：
#   $D/start_services.sh --port-9500 9500 start ; echo rc=$?   # 期望 rc=2


D=shared/deliverables/rf4-i18n-01

# 标准 2：语言包对齐（期望 zh keys: 1608 / en keys: 1608 / diff: none，rc=0）
python3 $D/tools/check_parity.py

# 标准 3：8080 英文页零中文（期望 CJK hits: 0，rc=0）
python3 $D/tools/check_page.py --url 'http://127.0.0.1:8080/?lang=en' --whitelist $D/tools/whitelist.txt

# 标准 5（8080 半边）：中文没被改坏（期望 CJK hits: 649 >= 20）
python3 $D/tools/check_page.py --url 'http://127.0.0.1:8080/?lang=zh' --min 20

# 标准 6：默认语言协商链（期望 verdict: PASS，7 条 ok）
python3 $D/tools/check_default.py

# 标准 7（8080 半边）：仅 cookie 也生效
curl -s -H 'Cookie: lang=en' 'http://127.0.0.1:8080/' | grep -c 'lang-switch'          # 期望 1
curl -s -D - -o /dev/null 'http://127.0.0.1:8080/?lang=en' | grep -i '^set-cookie'     # 期望 Max-Age=31536000
python3 $D/tools/check_page.py --url 'http://127.0.0.1:8080/' --cookie lang=en --whitelist $D/tools/whitelist.txt

# 标准 8：切换控件可达（期望 3 个唯一锚点：?lang=en / ?lang=zh / lang-switch）
curl -s 'http://127.0.0.1:8080/?lang=en' | grep -Eo 'lang-switch|\?lang=(zh|en)' | sort -u | wc -l

# 标准 9：缺 en 值回退 zh 原文（真删 en 值 + 真构建 + 真渲染，期望 verdict: PASS）
python3 $D/tools/test_fallback.py

# 标准 10：零新增依赖（期望两条命令都没有输出）
git diff --stat -- go.mod go.sum requirements.txt package.json pyproject.toml setup.py
git diff | grep -E '^\+.*(import (flask_babel|i18next|babel)|from (flask_babel|babel))'

# 标准 11（8080 半边 a）：路由状态码差集（期望 27/27 match；9500 的 9 条在本机 Connection refused）
python3 $D/tools/sample_route_status.py --base-8080 http://127.0.0.1:8080 --baseline $D/tools/baseline_ids.json

# 标准 11（8080 半边 b）：交互元素 id 集合双向差集（期望 removed: 0 / undeclared added: 0 / RESULT: PASS，rc=0）
python3 $D/tools/check_ids.py --port 8080
#   [assets] 段比对服务端实际发出的 GET / 与 app/*.js（同 baseline 提取口径）；
#   [dom] 段断言渲染后的 DOM 里没有 baseline 之外的新 id；lang-switch 是简报 7/8 要求的新增锚点，按 declared 列出。
# 9500 半边（本机起不来，两级走法任选其一）：
#   Windows:  python tools\check_ids.py --port 9500 --dump-ids ids_9500.json
#   本机:     python3 $D/tools/check_ids.py --port 9500 --from-json ids_9500.json
#   （本机直接 `--port 9500` 会因 launcher 未监听而退出码 2，不会假通过）

# 标准 12：白名单条数（期望 1 <= 10，且不含 UI 标签类词）
grep -vc '^#' $D/tools/whitelist.txt

# 一次跑完上面 2/3/5/6/7/8/9/10/11/12，原始输出落 notes/M3-selfcheck.log
bash $D/tools/selfcheck_m3.sh

# 9500 侧（本机做不到，必须在 Windows 上，见 README_WINDOWS.md）
#   python tools\win_verify_9500.py
```

`check_page.py` 的渲染后端：优先用平台 CDP 浏览器（`RAKAZO_CDP_PORT`，默认 9222）取
`document.body.innerText` + `document.title`；拿不到 CDP 才退回 `chromium --dump-dom`。
本机直接 `chromium --headless --dump-dom` 会挂起（45s 超时，见 `notes/M2-env-report.md`），故主用 CDP；
CDP 不可用时脚本退出码 2 并说明，不会假通过。

## 如何新增一种语言（标准 13 要求的第一节）

以加德语（`de`）为例，两条链路都要动，但都不改架构：

1. **服务端语言协商**：`internal/admin/lang_page.go` 的 `isLang()` 加上 `"de"`，
   `panel_lang.go` 的 `panelIsLang()` 同样加；两处 `Accept-Language` 分支各加一条
   `strings.HasPrefix(tag, "de")`。cookie 仍叫 `lang`，取值 `zh|en|de`。
2. **8080 资源包**：把 `internal/admin/web/app/locales/en.json` 复制成 `de.json`，
   逐条把英文值换成德语值（key 不改）。`tools/gen_locales.py` 里把 `LOCALES` 的输出列表
   加上 `de`，并把 `locales.data.js` 改成导出 `{ ZH, EN, DE, TEMPLATES }`；
   `i18n.js` 里 `LANG` 的判断从二选一改成查表，`tr()` 的取值顺序是
   `当前语言 → zh 回退`（缺译时回退 zh 原文，永不空白）。
3. **9500 资源包**：`tools/panel_en.py` 复制成 `panel_de.py`（同样 240 条 key），
   `tools/gen_panel_i18n.py` 里把字典名参数化，生成时把两套字典一起塞进 `panel.html`
   （`window.RF4_I18N = { en: {...}, de: {...} }`），语言层按 `window.RF4_LANG` 选表。
4. **切换控件**：`lang_page.go` 与 `panel_lang.go` 里的 `...LangSwitchHTML()` 各加一个锚点。
5. **验收**：`check_parity.py` 改成按包逐个比 key 数；`check_page.py --url '.../?lang=de'`
   应 CJK hits 0（如果德语页还该保留中文数据，就按 `whitelist.txt` 逐条登记）。

原则：**语言 = 一份 key 对齐的 JSON**，key 永远来自 M1 清单（`copy_inventory.json`），
新增文案先补清单再加 key，不要在新语言包里另起命名。

## 白名单含义（标准 13 要求的第二节）

`tools/whitelist.txt` 登记「英文页上允许出现的中文」，上限 10 条，形态：
`路径或URL :: 中文样例 :: 原因`。当前 **1 条**：

```
http://127.0.0.1:8080/ :: 本项目免费开源，作者未收取任何费用，谨防被骗 :: 服务端公告正文，由运营方发布，属数据不是界面文案
```

规则：

- **只有「数据」能进白名单**：运营方发布的公告正文、服务端运行日志正文（9500 的运行日志区）、
  玩家输入的内容。**UI 标签、按钮、表头、提示语、枚举展示名一律双语化，不许进白名单**——
  这是标准 12 的硬口径，白名单里出现 UI 类词即判失败。
- 白名单按**行**匹配：`check_page.py` 把渲染文本按行拆开，含样例子串的整行豁免，其余行照数。
  所以样例要选「整行里最独特的那一段」，不要用会命中普通文案的短词。
- 9500 的运行日志区用的是 DOM 层面的排除（`win_verify_9500.py` 按 `#logs` / `.home-log` 子树分流），
  不靠白名单堆行：日志是动态的，白名单按行登记会无限膨胀。
- 加白名单前先问一句：这行能不能翻？能翻就翻，不能翻才登记，并写清原因。

## 本轮补件（M3 预检退回的两条）

预检指出标准 11 的 id 差集与标准 13 的 `start_services.sh` 在交付物里没有载体，本轮只补这两件：

- `tools/check_ids.py`：纯标准库，退出码 0/1/2。8080 走「服务端实际发出的文件」做双向差集
  （GET / + 递归 import 的 `app/*.js`，用与 `gen_baseline_ids.py` 相同的正则），DOM 侧只断言
  没有 baseline 之外的新 id；9500 侧走渲染后 DOM 全量双向差集，`--dump-ids/--from-json` 支持
  Windows 导出、本机比对。`lang-switch` 是简报 7/8 要求新增的锚点，按 declared 列出而非判失败。
- `start_services.sh`：`--port-8080/--port-9500`、`start|stop|status`、后台起停、pid/日志落
  `shared/work/rf4-run/`、就绪探测到 HTTP 200 才返回 0；端口被占用时打印占用者并退出 1；
  9500 给平台错误并退出 2。
- **产品代码零改动**：`rf4-i18n-01.patch` **没有重新生成**——mtime 仍是
  `2026-11-28 11:28:08.619737681`、404,472 B、sha256
  `875888f7bc0039995faf82d7c522a1c3f3c33b9da99be30f8da255e74f13e74e`；
  在 ec58447 的干净副本（`git archive HEAD` 解出）上 `git apply --check` 仍 rc=0
  （11 files changed, 7214 insertions(+), 6 deletions(-)）。
- `tools/win_verify_9500.py` **M3b 当时一个字节没改**（mtime `2026-11-28 11:10:19.487627685`、
  sha256 `cfd2eef169875d52c127e4158c5b42ea1f9b90268279f8eef246d9caaba82be5`）。
  ⚠️ M3c 追加第 8 项后这个 sha256 已变（见下一节），原 9 项判定与字段名仍未改。
- 证据：`notes/M3b-selfcheck.log`（本轮补件全部原样输出，含 rc）。
- README_WINDOWS 只加了一段「可选：导出 9500 id」说明，不影响已有 9 项判定。

## 本轮补件（M3c：标准 6 的 9500 半边 + 标准 11 的 9500 差集改成必做）

预检退回两条：① 标准 6 在 9500 上没有可执行载体（`check_default.py` 的 `BASE` 硬编码 8080、
断言 8080 的标题；`win_verify_9500.py` 7 类判定里没有 Accept-Language）；② `README_WINDOWS.md`
把标准 11 的 9500 id 导出写成「可选」。本轮只补这两处，**产品代码零改动、patch 未重新生成**。

- `tools/check_acceptlang.py`（新增，纯标准库）：三项断言、逐项 PASS/FAIL + 实测值、末尾摘要块、
  退出码 0/1/2（2 = 服务连不上，不算通过）。断言的是 **9500 自己的** `<html lang>` /
  `<title>`（`RF4 本地服务器` / `RF4 Local Server`）/ `window.RF4_LANG`，不拿 8080 的标题凑。
- `tools/win_verify_9500.py`（**纯增量**）：原 9 项（service / routes-9500 / lang-switch / cookie-set /
  cookie-en / en-cjk / zh-cjk / cookie-en-render / fallback）判定逻辑与字段名一字未改，只在
  `fallback` 之后追加 3 个 `acceptlang-*` 项；新增 `--title-zh/--title-en/--lang-var` 三个参数
  （默认即 9500 口径，不传参 = 原行为，用户照旧 `python tools\win_verify_9500.py`）。摘要块 9 → 12 项。
- `README_WINDOWS.md`：5b 由「可选」改「必做」；贴回清单写死三样（摘要块 / 完整日志 / `ids_9500.json`）；
  摘要块示例与判定表补 `acceptlang-*`；改正「`win_verify` 一个字节没改」这句（M3c 已改过）；
  开头加「`tools` 整包一起拷」的提醒（新增 import）。
- 本机实测（原始输出 `notes/M3c-selfcheck.log`）：
  - `check_acceptlang.py` 对 8080 用 8080 标题 → `RESULT: PASS (3/3)`，rc=0；
  - 同一脚本用 9500 标题跑 8080 → `RESULT: FAIL (0/3)`，rc=1（**反证：断言不是恒 PASS**）；
  - `win_verify_9500.py` 对未监听的 9500 → `RESULT: ERROR (service unreachable)`，rc=2（预检预期）；
  - 追加项进摘要块的结构验证：在 `/tmp` 副本里裁掉渲染段后跑 8080，摘要块 7 项（4 原项 + 3 追加项）
    按顺序输出、字段名不变（交付文件未做此裁剪，原因：容器里从 shell 派生的浏览器进程起不来）。
- **本机产不出的东西**：12 项完整摘要必须来自用户 Windows 机器（本机 launcher 起不来、
  且容器里子进程浏览器被桌面保护挡掉，`win_verify` 只能到 rc=2）。

## 交付物清单

- `rf4-i18n-01.patch`（累计补丁，含 M2+M3；在 HEAD 干净副本上 `git apply --check` 通过）
- `README_WINDOWS.md`（**给用户**：Windows 起停 + 校验包用法）
- `start_services.sh`（交付物根：`--port-8080/--port-9500`、`start|stop|status`、端口占用明确报错退出非 0）
- `tools/check_ids.py`（标准 11 的 id 差集；`--dump-ids/--from-json` 支持跨机比对）
- `tools/check_acceptlang.py`（标准 6 的 9500 半边：Accept-Language 协商，M3c 新增）
- `notes/M3c-selfcheck.log`、`notes/M3c-report.md`（本轮补件的原始输出与结论）
- `tools/`（见上）、`notes/M3-selfcheck.log`（本轮标准 2/3/5/6/7/8/9/10/11/12 原始输出）、
  `notes/M3-report.md`（结论摘要 + 9500 侧做法）、`notes/M2-8080-report.md`、`notes/M2-env-report.md`
- `copy_inventory.json`（M1 文案清单，在交付物根）、`tools/baseline_ids.json`（M1 路由基线）

## 已知限制与没做的事

1. **9500 的运行期实测不在本机产出**：`cmd/launcher` 是 Windows-only，本机只能做
   `GOOS=windows go build` 的编译验证（通过）。标准 4/6/13 与 5/7/8/11 的 9500 半边
   由 `tools/win_verify_9500.py` 在用户 Windows 机器上产出，验收主管按「据用户机器输出」记。
2. **8080 的 waters / bait 两个页面在 en 下仍有中文**，全部是游戏数据（鱼种名、饵名、地图名，
   例如「葛氏鲈塘鳢」「拉多加湖图」），按假设五属于数据。要翻这些得先决定「物种名是否也双语」，
   那是产品决策，不是本任务的文案范围。
3. **不是所有页面都做了 CJK=0 的强制校验**：简报标准 3/5 只覆盖根页；上面 11/13 页的
   零命中是附加体检（`selfcheck_m3.sh` 最后一节），作为质量证据，不替代标准判定。
4. **未做**：localStorage 语言偏好（简报允许可选）、`legacy.html`（未被 index.html 引用）未翻。
   9500 的**运行期**启动仍只能在 Windows 上（`start_services.sh --port-9500` 在本机是明确报错 + 退出码 2，
   不是静默跳过）。
5. **9500 的 `panel.html` 变大约 20 KB**（内嵌字典 + 语言层），页面首屏无额外请求，仍是单文件。

## 需要下游注意的坑

1. **改译文只改 `tools/en_translations_m3.py` 的上游（`gen_en_m3.py` 的输入）或 `en_translations.py`，
   再跑 `gen_locales.py`**；9500 改 `tools/panel_en.py` 再跑 `gen_panel_i18n.py`。
   不要手改 `locales.data.js`、`locales/*.json`、`panel.html` 的字典块——都是生成物，
   `check_parity.py` 与运行期字典会立刻对不上。
2. `tr()` **不做子串替换**（9500 的 `polysh` 只在「并列短语」那一种情形补翻捕获组内的片段）。
   所以翻译单位是「整段文本节点」或「模板形状」：加词时若原文被 DOM 拆成多段，
   要按段加（`"在线、档案、物品、参数条数来自 "` 这种带尾空格的，字典按 trim 索引，两种写法都命中）。
3. **模板要防贪婪**：`^默认 (?P<v>.+)$` 会把 `" · "` 后面的段一起吞掉。i18n.js 已有兜底
   （整句结果里仍有中文且含 `" · "` 就退回分段），但新增模板时仍建议用 `[^·]+` 收窄。
4. 标准 1 的 mtime 口径：`baseline_ids.json` mtime = `2026-11-28 10:36:01.598996359`，
   本轮所有被改文件 mtime 均晚于它（逐文件 `ls -l --time-style=full-iso` 见 `notes/M3-selfcheck.log` 末尾）。
5. 新增文件用 `git add -N` 标成 intent-to-add，`git diff` 才会把内容写进 patch；
   验收用 `git apply --check` 时要连同新增文件一起验。
6. `start_services.sh --port-8080 <非8080>` 时，脚本会在 `rf4-run/` 下生成临时配置副本，
   **同时把 `admin.obs_addr` 错开**（`9503 + 端口差`）。不这么做的话第二个实例会在
   `观测端口监听失败: listen tcp :9503: bind: address already in use` 后直接退出——
   这是实测踩到的，不是理论风险。pid/日志也按端口分开（`admin-<port>.pid/.log`），
   否则起 18080 会覆盖掉 8080 的 pid 文件，把 8080 变成没人管的孤儿进程。
7. 9500 的 `#lang-switch` 在静态 `panel.html` 里是空占位 `<nav ...></nav>`，**必须由 handler 填**；
   直接打开 `panel.html` 文件不会有切换控件（这是故意的，避免两处各写一份 HTML）。