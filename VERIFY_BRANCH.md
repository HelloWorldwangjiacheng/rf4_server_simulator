# 验证分支 verify/rf4-i18n-01 · 从这里开始（Windows 实跑）

这个分支 = **`ec58447d06452072647d7ec26d7a7b59f581c649` + `rf4-i18n-01.patch` 已应用**。

> **跳过 `git apply`。** 补丁已经打进本分支的提交里，你 clone 下来就是打完补丁的状态。
> `README_WINDOWS.md` 第 1 节（clone → `git checkout ec58447` → `git apply --check` → `git apply`）
> **对本分支不适用，整节跳过**；从第 2 节「构建 launcher」开始照做即可。
> 想核对的话：`git status --porcelain` 应该干净，`git log --oneline -2` 第一条是本分支提交、
> 第二条是 `ec58447`。

补丁指纹（交付目录原件，未重新生成）：`rf4-i18n-01.patch` 404,472 B，sha256
`875888f7bc0039995faf82d7c522a1c3f3c33b9da99be30f8da255e74f13e74e`。

---

## 1. 取代码（一行）

```bat
git clone -b verify/rf4-i18n-01 https://github.com/HelloWorldwangjiacheng/rf4_server_simulator rf4-win
cd rf4-win
```

已经有这个仓库的副本也行：`git fetch origin verify/rf4-i18n-01` → `git checkout verify/rf4-i18n-01`。
**不要**把自己手工打过 M2/M3 补丁的旧副本和本分支混用——那是两条不同的来源。

---

## 2. 构建 launcher

```bat
set CGO_ENABLED=0
go build -trimpath -o launcher.exe .\cmd\launcher
dir launcher.exe
```

（与 `README_WINDOWS.md` 第 2 节完全一致。不需要 `GOOS=windows`，不需要 wine。）

---

## 3. 起服务并确认就绪

```bat
launcher.exe -config config.yaml
```

首次启动会初始化数据库，可能要一分钟。另开一个 PowerShell 窗口：

```powershell
curl.exe -s -o NUL -w "%{http_code}`n" http://127.0.0.1:9500/api/status
curl.exe -s http://127.0.0.1:9500/api/status
```

看到 `200` 和一段 JSON 就是起来了。9500 被占用的话先 `netstat -ano | findstr :9500`。
（与 `README_WINDOWS.md` 第 3 节完全一致。）

---

## 4. 三条验证命令（launcher 一直开着，按这个顺序跑）

```bat
REM 4.1 12 项判定 + 摘要块（约 1 分钟）——标准 4/6/7/8 的 9500 半边
python tools\win_verify_9500.py

REM 4.2 单独跑一遍 Accept-Language 三项（标准 6 的 9500 半边；可省，4.1 里已经跑过）
python tools\check_acceptlang.py

REM 4.3 【必须在停服务之前】导出 9500 的 id 集合——标准 11 的 9500 半边
python tools\check_ids.py --port 9500 --dump-ids ids_9500.json
```

> **4.3 一定要在停服务之前做**，服务停了导出就是 `RESULT: ERROR`。
> 4.1 和 4.3 互不依赖，先跑哪个都行。

脚本找不到浏览器时（`RESULT: ERROR` 且提到 CDP / browser），加参数指路径：

```bat
python tools\win_verify_9500.py --browser "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
```

`tools` 整个文件夹都要在（`win_verify_9500.py` 会 import 同目录的
`check_page.py`、`check_acceptlang.py`）。本分支已经把整个 `tools/` 带上了，直接跑即可。

---

## 5. 贴回三样（缺一样这轮没法判）

1. **摘要块**：`win_verify_9500.py` 输出里从 `===== SUMMARY` 到 `RESULT: ...` 那几行，12 项，原样复制。
2. **完整日志**：整段 `win_verify_9500.py` 输出（含 `en-cjk` / `zh-cjk` 的 `hit:` 明细、
   `routes-9500` 每条的 want/got）。有 FAIL 就把 FAIL 前后的日志一起贴，别只贴结论。
3. **`ids_9500.json`**：4.3 导出的那个文件（几十 KB 纯文本），贴回或附回。

---

## 6. `RESULT: ERROR` 不算通过

退出码：`0` = 全项 PASS，`1` = 有 FAIL，`2` = 环境问题（服务没起 / 找不到浏览器 / CDP 不通）。
**`2` 一律重跑**：先确认 9500 真的 200，再用 `--browser` 指 msedge.exe 路径；别当通过贴。

---

## 7. 本分支禁止改代码

发现问题**回报**，不要在分支上改。这个分支只用于「拿真机输出」，
任何代码/脚本/文档修改都要回到主流程重走冻结与验收。