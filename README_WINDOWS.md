# 9500 控制面板 · Windows 运行期校验说明（给用户，一步一步照做）

这份说明对应 **简报标准 4 / 6 / 13，以及 5 / 7 / 8 / 11 的 9500 半边**。
9500（launcher 控制面板）是 Windows-only 目标：`cmd/launcher/hosts.go` 直接 import
`golang.org/x/sys/windows` 且没有 build tag，Linux 容器里构建不出这个二进制，所以
**这些标准的实测只能在你的 Windows 机器上做**。你跑完把输出贴回，验收主管核脚本与输出。

脚本是纯 Python 标准库，不需要 pip；浏览器用系统自带的 Edge（Win10/11 默认有），
或 Chrome，脚本会自动找。

> **`tools` 整个文件夹要一起拷**：`win_verify_9500.py` 会 import 同目录的
> `check_page.py`（浏览器 CDP 客户端）与 `check_acceptlang.py`（第 8 项判定）。
> 只拷一个 `win_verify_9500.py` 跑不起来。`python` 就是能出版本号的那个命令，
> 有些机器上是 `py -3`，等价替换即可。

---

## 0. 前置

| 需要 | 说明 |
| --- | --- |
| Windows 10 / 11 | 任意近期版本 |
| Python 3.8+ | `python --version` 能出版本号即可，不需要装任何包 |
| Go 1.21+ | 只在「构建 launcher」这一步用到；`go version` 能出版本号 |
| Git | 用来检出 `ec58447` 并打补丁 |
| Microsoft Edge | 默认浏览器自带即可；没有的话装 Chrome |

端口 **9500** 要空着（脚本默认连 `http://127.0.0.1:9500`）。8080 不用单独起——
launcher 会把管理后台挂在同一个 9500 入口下。

---

## 1. 准备代码并打补丁

```bat
:: 1.1 一个干净副本（或直接用你现有的副本，但必须停在 ec58447）
git clone <这个仓库的地址> rf4-win
cd rf4-win
git checkout ec58447d06452072647d7ec26d7a7b59f581c649

:: 1.2 把交付物里的 rf4-i18n-01.patch 拷到仓库根，先试应用
git apply --check rf4-i18n-01.patch
::    ↑ 没有任何输出 + 退出码 0 = 补丁能干净应用

git apply rf4-i18n-01.patch
git status --porcelain
```

`git status` 应该看到 11 个文件（10 个改动 + `cmd/launcher/panel_lang.go` 新增），
不应该出现 `go.mod` / `go.sum`。补丁只改 `internal/admin/**` 与 `cmd/launcher/**`。

> 如果你手上的副本已经应用过 M2 的旧补丁，请重新从 `ec58447` 起一个干净副本再打这一份
> （这份是累计补丁，直接覆盖 M2 的内容）。

---

## 2. 构建 launcher

```bat
set CGO_ENABLED=0
go build -trimpath -o launcher.exe .\cmd\launcher
dir launcher.exe
```

`launcher.exe` 出现在仓库根即可。第一次构建要下依赖，慢一点正常。

> 不需要 `GOOS=windows`（你本来就在 Windows 上）；也不需要 wine / 交叉编译。

---

## 3. 起服务并确认就绪

```bat
:: 3.1 起 launcher（用你自己的 config.yaml；首次启动会初始化数据库，可能要一分钟）
launcher.exe -config config.yaml
```

另开一个 PowerShell 窗口：

```powershell
:: 3.2 确认就绪：应该看到 HTTP 200 和一段 JSON
curl.exe -s -o NUL -w "%{http_code}`n" http://127.0.0.1:9500/api/status
curl.exe -s http://127.0.0.1:9500/api/status
```

或者直接用浏览器打开 <http://127.0.0.1:9500/>，看到「服务器工作台」页面就是起来了。

如果 `api/status` 一直不通：看 launcher 窗口里的报错；常见原因是 9500 被占用
（`netstat -ano | findstr :9500`）或 `config.yaml` 里的 sqlite 路径不对。

---

## 4. 跑校验脚本

```bat
python tools\win_verify_9500.py
```

可选参数：

```bat
:: 换端口 / 换地址
python tools\win_verify_9500.py --url http://127.0.0.1:9500

:: 脚本找不到浏览器时，直接指定 Edge 的完整路径
python tools\win_verify_9500.py --browser "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

:: 只做页面检查，不跑路由差集（只想快点看页面时）
python tools\win_verify_9500.py --skip-routes
```

也可以**单独**跑 Accept-Language 那三项（标准 6 的 9500 半边；`win_verify` 里也会跑一遍，
这条只是让你在怀疑协商有问题时能单独看）：

```bat
python tools\check_acceptlang.py
:: 期望 RESULT: PASS (3/3)，退出码 0
```

脚本会自己统计、自己判 PASS/FAIL，最后打印一段 **摘要块**：

```
===== SUMMARY (9500 · rf4-i18n-01 · Windows 运行期校验) =====
[PASS] service          GET /api/status -> 200
[PASS] routes-9500      checked 7/15, mismatch 0, skipped 8 (side-effect routes)
[PASS] lang-switch      unique anchors=3 ['?lang=en', '?lang=zh', 'lang-switch']
[PASS] cookie-set       Set-Cookie: lang=en; Path=/; Max-Age=31536000; SameSite=Lax
[PASS] cookie-en        GET / + Cookie: lang=en -> status 200, RF4_LANG=en, html lang=en
[PASS] en-cjk           UI CJK hits: 0 (title='RF4 Local Server', RF4_LANG='en', <html lang>='en')
[PASS] zh-cjk           CJK hits: 6xx (need >= 20)
[PASS] cookie-en-render UI CJK hits: 0, RF4_LANG='en'
[PASS] fallback         missing->'这条文案故意不在字典里', 开始游戏->'Start game', 保存->'Save'
[PASS] acceptlang-default 无 Accept-Language / 无 cookie / 无 ?lang= -> HTTP 200, 期望 'zh' 壳 | <html lang>='zh-CN' <title>='RF4 本地服务器' RF4_LANG='zh'
[PASS] acceptlang-en    Accept-Language: en-US,en;q=0.9 -> HTTP 200, 期望 'en' 壳 | <html lang>='en' <title>='RF4 Local Server' RF4_LANG='en'
[PASS] acceptlang-zh    Accept-Language: zh-CN,zh;q=0.9 -> HTTP 200, 期望 'zh' 壳 | <html lang>='zh-CN' <title>='RF4 本地服务器' RF4_LANG='zh'
RESULT: PASS (12/12)
```

最后三项（`acceptlang-*`）是**本轮追加**的：判的是标准 6「默认语言按浏览器语言走」在 9500 上的
那一半——不带任何头和 cookie 时是中文壳，浏览器首选 en 时是英文壳，首选 zh 时还是中文壳。
断言用的是 9500 自己的 `<html lang>` / `<title>`（RF4 本地服务器 / RF4 Local Server）/
`window.RF4_LANG`，不拿 8080 的标题凑。所以摘要块现在是 12 项。

退出码：`0` = 全项 PASS；`1` = 有 FAIL（摘要块里能看到哪一项）；`2` = 环境问题
（服务没起、找不到浏览器、CDP 不通）——**2 不是通过，别当通过贴**。

---

## 5. 停止服务

任选一种：

- 托盘图标右键 → 退出；
- 在 launcher 窗口按 `Ctrl+C`；
- PowerShell：`Stop-Process -Name launcher`；
- 任务管理器结束 `launcher.exe`。

停之后再确认一次端口已释放：`netstat -ano | findstr :9500` 没有输出即可。

---

## 5b. 必做：导出 9500 的 id 集合

标准 11 明文要求「两个端口的交互元素 id 集合差集为空」，这一条**必须有 9500 的 id 集合**才算数，
所以这步是**必做**，不是可选。9500 那一半在本机没法渲染，所以用导出：
**停服务之前**，在仓库根再跑一条（launcher 还在跑就行）：

```powershell
python tools\check_ids.py --port 9500 --dump-ids ids_9500.json
```

它会把 9500 面板渲染后 DOM 里所有 `id` 导出成 `ids_9500.json`（纯文本，几十 KB）。
**把这个文件一起发回**，本机用 `python3 tools/check_ids.py --port 9500 --from-json ids_9500.json`
做双向差集（这一步由验收侧执行，你不用跑）。

导出与 `win_verify_9500.py` 互不依赖：先跑哪个都行，但**导出必须在停服务之前**做。
如果导出时报 `RESULT: ERROR`（找不到浏览器/CDP 不通），处理办法跟上面 `win_verify` 一样
（`--browser` 指路径），别跳过这一步。

---

## 6. 贴回什么（就这三样，缺一样这轮没法判）

1. **摘要块**：`python tools\win_verify_9500.py` 输出里从 `===== SUMMARY` 到 `RESULT: ...` 的那几行，原样复制。
   （摘要块里包含 `acceptlang-*` 三项，标准 6 的 9500 半边就靠它判；你要是单独跑过
   `check_acceptlang.py`，把那段 `===== SUMMARY (Accept-Language …)` 也一起贴。）
2. **完整日志**：整段 `python tools\win_verify_9500.py` 的输出（含 en-cjk / zh-cjk 明细、
   `data-hits` 行、`routes-9500` 的逐条 want/got）。如果某项 FAIL，把 FAIL 那行前后的日志一起贴，别只贴结论。
3. **`ids_9500.json`**：第 5b 步导出的文件（标准 11 的 9500 半边靠它，缺了这项没法判）。

验收主管会按「据用户机器输出」记这一轮的 4/5/7/8/11-9500，所以**别手改输出、别只贴 PASS 的那几行**。

---

## 7. 脚本判的是什么（口径，贴回时一起看）

| 项 | 含义 | 期望 |
| --- | --- | --- |
| `service` | `GET /api/status` | 200 |
| `routes-9500` | baseline 里 9500 端口 15 条路由的状态码；有副作用的路由按 baseline 的 `sample_policy=skip` 跳过 | mismatch 0 |
| `lang-switch` | 原始 HTML 里语言切换锚点（`lang-switch` / `?lang=zh` / `?lang=en` 去重） | ≥ 2 |
| `cookie-set` | `?lang=en` 是否回写 cookie | `lang=en; Path=/; Max-Age=31536000` |
| `cookie-en` | 不带 URL 参数、只带 `Cookie: lang=en` 的页面壳 | `RF4_LANG="en"`、`<html lang="en">` |
| `en-cjk` | en 页渲染后的 **UI 文本** CJK 命中 | 0 |
| `zh-cjk` | zh 页渲染后的 CJK 命中（确认中文没被改坏） | ≥ 20 |
| `cookie-en-render` | 只靠 cookie 拿到的 en 页，渲染后 CJK | 0 |
| `fallback` | 字典里没有的整句是否原样回退；已知 key 是否给出英文 | 两条都成立 |
| `acceptlang-default` | 不带 Accept-Language、不带 cookie、不带 `?lang=` 时的页面壳（标准 6） | `zh` 壳：`<html lang="zh-CN">`、`<title>RF4 本地服务器</title>`、`RF4_LANG="zh"` |
| `acceptlang-en` | `Accept-Language: en-US,en;q=0.9` 时的页面壳（标准 6） | `en` 壳：`<html lang="en">`、`<title>RF4 Local Server</title>`、`RF4_LANG="en"` |
| `acceptlang-zh` | `Accept-Language: zh-CN,zh;q=0.9` 时的页面壳（标准 6） | `zh` 壳（同上） |

**关于运行日志区**：面板右侧「运行日志」显示的是服务端进程的 stdout，属于**数据不是界面文案**
（简报假设五）。脚本把它单独计数（`data-hits`）并原样列出，不计入 `en-cjk` 的 PASS/FAIL；
判定用的数字和列出来的日志行都会打印，藏不住。

**关于物种名/饵名/玩家名**：这些是游戏数据，跟 8080 侧一样保留原文，不在翻译范围。

---

## 8. 常见问题

| 现象 | 处理 |
| --- | --- |
| `RESULT: ERROR (no browser)` | 用 `--browser` 指定 msedge.exe / chrome.exe 完整路径 |
| `RESULT: ERROR (service unreachable)` | launcher 没起或还没就绪；等 10~30 秒再跑，或看 `/api/status` |
| `RESULT: ERROR (cdp unreachable)` | 浏览器启动失败或被杀软拦；换 Chrome 试，或关掉占用调试端口的程序 |
| `routes-9500` 有 mismatch | 把 mismatch 行贴回；如果是 404/405 差别，说明路由注册跟 baseline 不一致 |
| `en-cjk` 命中几行 | 把 `hit:` 开头的行贴回，那些就是漏翻的界面文案，我按行补 |
| 首次启动很慢 | 首次要导入静态配置建库，等一两分钟正常 |