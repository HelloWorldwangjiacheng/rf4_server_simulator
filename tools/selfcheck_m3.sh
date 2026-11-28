#!/bin/bash
# M3 自检复跑：把标准 2/3/5/6/7/8/9/10/11/12 的原始输出一次性落到 notes/M3-selfcheck.log
# 用法：在 /home/rakazo 下执行 bash shared/deliverables/rf4-i18n-01/tools/selfcheck_m3.sh
set -uo pipefail
D=/home/rakazo/shared/deliverables/rf4-i18n-01
LOG=$D/notes/M3-selfcheck.log
: > "$LOG"
say() { echo "$@" | tee -a "$LOG"; }
run() { echo "\$ $*" | tee -a "$LOG"; "$@" >>"$LOG" 2>&1; echo "rc=$?" | tee -a "$LOG"; echo | tee -a "$LOG"; }

say "== date =="
date -Is | tee -a "$LOG"

say "== 标准 2：语言包对齐 =="
run python3 "$D/tools/check_parity.py"

say "== 标准 3：8080 英文页零中文 =="
run python3 "$D/tools/check_page.py" --url 'http://127.0.0.1:8080/?lang=en' --whitelist "$D/tools/whitelist.txt"

say "== 标准 5（8080 半边）：中文页 CJK >= 20 =="
run python3 "$D/tools/check_page.py" --url 'http://127.0.0.1:8080/?lang=zh' --min 20

say "== 标准 6：默认语言协商链 =="
run python3 "$D/tools/check_default.py"

say "== 标准 7（8080 半边）：cookie lang=en 直取英文页 =="
say "\$ curl -s -H 'Cookie: lang=en' http://127.0.0.1:8080/ | grep -c 'lang-switch'"
curl -s -H 'Cookie: lang=en' 'http://127.0.0.1:8080/' | grep -c 'lang-switch' | tee -a "$LOG"
say "\$ curl -s -D - -o /dev/null 'http://127.0.0.1:8080/?lang=en' | grep -i '^set-cookie'"
curl -s -D - -o /dev/null 'http://127.0.0.1:8080/?lang=en' | grep -i '^set-cookie' | tee -a "$LOG"
echo | tee -a "$LOG"
run python3 "$D/tools/check_page.py" --url 'http://127.0.0.1:8080/' --cookie lang=en --whitelist "$D/tools/whitelist.txt"

say "== 标准 8：切换控件锚点（>= 2） =="
say "\$ curl -s 'http://127.0.0.1:8080/?lang=en' | grep -Eo 'lang-switch|\\?lang=(zh|en)' | sort -u | wc -l"
curl -s 'http://127.0.0.1:8080/?lang=en' | grep -Eo 'lang-switch|\?lang=(zh|en)' | sort -u | tee -a "$LOG"
echo | tee -a "$LOG"

say "== 标准 9：缺 en 值回退 zh 原文 =="
run python3 "$D/tools/test_fallback.py"

say "== 标准 10：零新增依赖 =="
say "\$ git -C shared/work/rf4_server_simulator diff --stat -- go.mod go.sum requirements.txt package.json pyproject.toml setup.py"
git -C /home/rakazo/shared/work/rf4_server_simulator diff --stat -- go.mod go.sum requirements.txt package.json pyproject.toml setup.py | tee -a "$LOG"
say "\$ git -C shared/work/rf4_server_simulator diff | grep -E '^\\+.*(import (flask_babel|i18next|babel)|from (flask_babel|babel))'"
git -C /home/rakazo/shared/work/rf4_server_simulator diff | grep -E '^\+.*(import (flask_babel|i18next|babel)|from (flask_babel|babel))' | tee -a "$LOG"
echo | tee -a "$LOG"

say "== 标准 11：路由状态码差集（8080 全对，9500 由 Windows 校验包负责） =="
run python3 "$D/tools/sample_route_status.py" --base-8080 http://127.0.0.1:8080 --baseline "$D/tools/baseline_ids.json"

say "== 标准 12：白名单条数（<= 10） =="
say "\$ grep -vc '^#' $D/tools/whitelist.txt"
grep -vc '^#' "$D/tools/whitelist.txt" | tee -a "$LOG"
echo | tee -a "$LOG"

say "== 8080 全部页面英文页体检（附加，不在标准 1–13 里） =="
run python3 /home/rakazo/shared/work/m3/check_all_pages2.py

say "== 仓库状态 =="
git -C /home/rakazo/shared/work/rf4_server_simulator rev-parse HEAD | tee -a "$LOG"
git -C /home/rakazo/shared/work/rf4_server_simulator status --porcelain | tee -a "$LOG"
say "== 被改文件逐文件 mtime / size =="
git -C /home/rakazo/shared/work/rf4_server_simulator status --porcelain | awk '{print $2}' | while read -r f; do
  ls -l --time-style=full-iso "/home/rakazo/shared/work/rf4_server_simulator/$f" | tee -a "$LOG"
done
say "== baseline mtime =="
ls -l --time-style=full-iso "$D/tools/baseline_ids.json" | tee -a "$LOG"
say "done: $LOG"