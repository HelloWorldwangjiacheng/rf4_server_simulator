#!/usr/bin/env bash
# rf4-i18n-01 服务起停脚本（简报标准 13 明文要求的交付物）。
#
# 用法：
#   ./start_services.sh [--port-8080 8080] [--port-9500 9500] start
#   ./start_services.sh stop
#   ./start_services.sh status
#
# 行为：
#   8080（admin）：后台起，pid/日志落 shared/work/rf4-run/，就绪探测到 HTTP 200 才返回 0。
#                  端口被占用时明确报错并退出非 0，不静默、不换端口。
#   9500（launcher）：cmd/launcher 是 Windows-only 目标（hosts.go 直接 import
#                  golang.org/x/sys/windows，无 build tag），Linux 上构建/运行都不成立。
#                  这里不做假起，明确报错 + 指向 README_WINDOWS.md，退出码 2。
#
# --port-8080 时改的是本次运行的临时配置副本（放在 rf4-run/），不改仓库的
# config.yaml，也不改任何路由。
# --port-9500 一旦出现在命令行上，start/stop 就直接给 9500 的平台错误并以退出码 2 结束，
# 不静默降级。
#
# 退出码：0 成功；1 失败（端口占用 / 起不来 / 未运行）；2 平台不支持（9500）。

set -u

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="${RF4_REPO:-$HERE/../../work/rf4_server_simulator}"
BIN="${RF4_BIN:-$HERE/../../work/rf4-bin}"
RUN="${RF4_RUN:-$HERE/../../work/rf4-run}"

PORT_8080=8080
PORT_9500=9500
WANT_9500=0
ACTION=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --port-8080) PORT_8080="$2"; shift 2 ;;
    --port-9500) PORT_9500="$2"; WANT_9500=1; shift 2 ;;
    --repo) REPO="$2"; shift 2 ;;
    --bin) BIN="$2"; shift 2 ;;
    start|stop|status) ACTION="$1"; shift ;;
    -h|--help) sed -n '1,20p' "$0"; exit 0 ;;
    *) echo "未知参数: $1" >&2; exit 1 ;;
  esac
done

if [ -z "$ACTION" ]; then
  echo "用法: $0 [--port-8080 N] [--port-9500 N] {start|stop|status}" >&2
  exit 1
fi

# 路径尽量规范化，日志里别出现 xxx/../../work 这种
[ -d "$REPO" ] && REPO="$(cd "$REPO" && pwd)"
[ -d "$BIN" ] && BIN="$(cd "$BIN" && pwd)"
[ -d "$RUN" ] && RUN="$(cd "$RUN" && pwd)"

# pid/日志按实际端口分开，避免「起 18080 覆盖掉 8080 的 pid 文件」把自己的实例变成孤儿
PID_8080="$RUN/admin-$PORT_8080.pid"
LOG_8080="$RUN/admin-$PORT_8080.log"
PID_9500="$RUN/launcher-$PORT_9500.pid"

# 端口是否已被占用：能 bind 就算空闲。返回 0=被占用，1=空闲
port_busy() {
  python3 -c 'import socket,sys
s = socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    s.bind(("0.0.0.0", int(sys.argv[1])))
except OSError:
    sys.exit(0)
sys.exit(1)' "$1"
}

# 谁占着端口：ss/fuser 都可能没装，最后用 /proc 兜底（Linux）
port_owner() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    local line
    line="$(ss -lptnH "sport = :$port" 2>/dev/null | head -n1)"
    if [ -n "$line" ]; then echo "$line"; return 0; fi
  fi
  if command -v fuser >/dev/null 2>&1; then
    local pids
    pids="$(fuser -n tcp "$port" 2>/dev/null | tr -s ' ')"
    if [ -n "$pids" ]; then echo "pid$pids"; return 0; fi
  fi
  python3 -c 'import os,sys,glob
port = int(sys.argv[1])
inodes = set()
for f in ("/proc/net/tcp", "/proc/net/tcp6"):
    try:
        rows = open(f).read().splitlines()[1:]
    except OSError:
        continue
    for r in rows:
        p = r.split()
        if len(p) < 10:
            continue
        if int(p[1].split(":")[1], 16) == port and p[3] == "0A":
            inodes.add(p[9])
if not inodes:
    print("未找到（端口在 TCP 表里也不可见）")
    raise SystemExit(0)
for pid in os.listdir("/proc"):
    if not pid.isdigit():
        continue
    try:
        for fd in os.listdir("/proc/" + pid + "/fd"):
            try:
                t = os.readlink("/proc/" + pid + "/fd/" + fd)
            except OSError:
                continue
            if t.startswith("socket:[") and t[8:-1] in inodes:
                cmd = open("/proc/" + pid + "/cmdline").read().replace(chr(0), " ").strip()
                print("pid %s  %s" % (pid, cmd[:160]))
                raise SystemExit(0)
    except OSError:
        continue
print("socket inode %s 找不到对应进程（可能属于其他用户）" % ",".join(sorted(inodes)))' "$port"
}

pid_alive() {
  [ -f "$1" ] || return 1
  local p
  p="$(cat "$1" 2>/dev/null)"
  [ -n "$p" ] || return 1
  kill -0 "$p" 2>/dev/null
}

http_code() {
  local c
  c="$(curl -s -o /dev/null -w '%{http_code}' --max-time 2 "http://127.0.0.1:$1/" 2>/dev/null)"
  [ -n "$c" ] || c="000"
  echo "$c"
}

start_8080() {
  mkdir -p "$RUN"
  RUN="$(cd "$RUN" && pwd)"
  if port_busy "$PORT_8080"; then
    echo "错误: 端口 $PORT_8080 已被占用，拒绝启动（不静默、不自动换端口）。" >&2
    echo "占用者: $(port_owner "$PORT_8080")" >&2
    if pid_alive "$PID_8080"; then
      echo "提示: 本脚本自己的实例还在跑（pid $(cat "$PID_8080")），先 ./start_services.sh stop。" >&2
    fi
    return 1
  fi
  if [ ! -x "$BIN/admin" ]; then
    echo "错误: 找不到可执行的 admin 二进制: $BIN/admin（先跑 tools/build_linux.sh）" >&2
    return 1
  fi
  local cfg="$RUN/config-8080-$PORT_8080.yaml"
  # 换端口时观测端口也要一起错开，否则会和已在跑的 8080 实例抢 :9503（实测过，
  # 表现为 "观测端口异常退出 ... bind: address already in use" 后进程直接退出）。
  local obs_port="$((9503 + PORT_8080 - 8080))"
  python3 - "$REPO/config.yaml" "$cfg" "$PORT_8080" "$obs_port" <<'PY'
import sys
src, dst, port, obs = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
lines = open(src, encoding="utf-8").read().splitlines()
out, in_admin = [], False
for ln in lines:
    if ln.strip() == "admin:":
        in_admin = True
        out.append(ln)
        continue
    if in_admin:
        if ln.strip() and not ln.startswith((" ", "\t")):
            in_admin = False
        elif ln.strip().startswith("http_addr:"):
            indent = ln[: len(ln) - len(ln.lstrip())]
            out.append('%shttp_addr: ":%s"' % (indent, port))
            continue
        elif ln.strip().startswith("obs_addr:"):
            indent = ln[: len(ln) - len(ln.lstrip())]
            out.append('%sobs_addr: ":%s"' % (indent, obs))
            continue
    out.append(ln)
open(dst, "w", encoding="utf-8").write("\n".join(out) + "\n")
PY
  echo "启动 admin: $BIN/admin -config $cfg （repo=$REPO, http=$PORT_8080, obs=$obs_port）"
  (
    cd "$REPO" || exit 1
    nohup "$BIN/admin" -config "$cfg" > "$LOG_8080" 2>&1 &
    echo $! > "$PID_8080"
  )
  local i
  for i in $(seq 1 40); do
    if [ "$(http_code "$PORT_8080")" = "200" ]; then
      echo "就绪: http://127.0.0.1:$PORT_8080/ -> 200 （pid $(cat "$PID_8080")）"
      echo "日志: $LOG_8080"
      echo "停止: $0 --port-8080 $PORT_8080 stop"
      return 0
    fi
    if ! pid_alive "$PID_8080"; then
      echo "错误: admin 进程已退出，起不来。日志尾部:" >&2
      tail -n 20 "$LOG_8080" >&2
      rm -f "$PID_8080"
      return 1
    fi
    sleep 0.5
  done
  echo "错误: 20s 内 $PORT_8080 未返回 200。日志尾部:" >&2
  tail -n 20 "$LOG_8080" >&2
  return 1
}

stop_8080() {
  if ! pid_alive "$PID_8080"; then
    echo "8080(port $PORT_8080): 未在运行（无有效 pid 文件 $PID_8080）"
    rm -f "$PID_8080"
    return 0
  fi
  local p
  p="$(cat "$PID_8080")"
  echo "停止 admin pid $p ..."
  kill "$p" 2>/dev/null
  local i
  for i in $(seq 1 20); do
    kill -0 "$p" 2>/dev/null || break
    sleep 0.25
  done
  if kill -0 "$p" 2>/dev/null; then
    echo "错误: pid $p 未退出，改用 kill -9 前请先确认它是不是我们的进程。" >&2
    return 1
  fi
  rm -f "$PID_8080"
  echo "已停止（pid $p）。"
  return 0
}

status_8080() {
  local code
  code="$(http_code "$PORT_8080")"
  if pid_alive "$PID_8080"; then
    echo "8080(port $PORT_8080): 运行中 pid $(cat "$PID_8080")，HTTP $code，日志 $LOG_8080"
    [ "$code" = "200" ] && return 0 || return 1
  fi
  if [ "$code" = "200" ]; then
    echo "8080(port $PORT_8080): 端口有服务在应答（HTTP 200），但不是本脚本起的（无 pid 文件）"
    return 1
  fi
  echo "8080(port $PORT_8080): 未运行（HTTP $code）"
  return 1
}

no_9500() {
  cat >&2 <<'TXT'
错误: 9500（launcher 控制面板）在本机（Linux）起不来 —— 这不是环境没装好，是平台目标问题：
  cmd/launcher/hosts.go:23 直接 import golang.org/x/sys/windows，且没有 build tag，
  所以 `go build ./cmd/launcher` 在 linux/amd64 上必然失败（build constraints exclude all Go files）。
  本容器也没有 wine，无法运行 GOOS=windows 的产物。

9500 侧的运行期验证改在 Windows 机器上做，步骤见：
  shared/deliverables/rf4-i18n-01/README_WINDOWS.md
（打 patch → go build → 起 launcher → 确认 9500 就绪 → python tools\win_verify_9500.py）

本脚本不提供 9500 的替代启动（不做 harness 冒充、不加 build tag），以免把验收污染成假通过。
TXT
  return 2
}

case "$ACTION" in
  start)
    if [ "$WANT_9500" -eq 1 ]; then
      no_9500
      exit 2
    fi
    start_8080 || exit 1
    echo
    echo "9500: 本次未启动（Windows-only）。要 9500 的明确报错就加 --port-9500，或按 README_WINDOWS.md 在 Windows 上起。"
    exit 0
    ;;
  stop)
    if [ "$WANT_9500" -eq 1 ]; then
      no_9500
      exit 2
    fi
    rc=0
    stop_8080 || rc=1
    if pid_alive "$PID_9500"; then
      echo "9500: pid $(cat "$PID_9500") 存活，但 Linux 上不会有这个进程，请人工确认。"
      rc=1
    fi
    exit "$rc"
    ;;
  status)
    rc=0
    status_8080 || rc=1
    if port_busy "$PORT_9500"; then
      echo "9500: 端口被占用"
    else
      echo "9500: 未监听（Windows-only，Linux 不提供）"
    fi
    exit "$rc"
    ;;
esac