#!/bin/bash
# 在团队电脑（Linux 容器）构建 rf4_server_simulator 的三个可运行目标。
# 用法：在 /home/rakazo 下执行 bash shared/deliverables/rf4-i18n-01/tools/build_linux.sh
# 产物落在 shared/work/rf4-bin/（仓库外），不改仓库任何文件。
set -euo pipefail
ROOT=${HOME}
SHARED=$ROOT/shared
GO=${GO:-$SHARED/tools/go/bin/go}
REPO=$SHARED/work/rf4_server_simulator
BIN=$SHARED/work/rf4-bin
export GOCACHE=$SHARED/work/gocache
mkdir -p "$BIN" "$GOCACHE"
cd "$REPO"

"$GO" version
grep -m1 '^go ' go.mod
"$GO" mod download

for c in admin gameserver gateway; do
  echo "-- build $c"
  "$GO" build -trimpath -o "$BIN/$c" "./cmd/$c"
done

# launcher 是 Windows-only（cmd/launcher/hosts.go 直接 import golang.org/x/sys/windows，无 build tag）
echo "-- build launcher (GOOS=windows) -> launcher.exe"
env GOOS=windows GOARCH=amd64 "$GO" build -trimpath -o "$BIN/launcher.exe" ./cmd/launcher

echo "-- 仓库状态（应为 HEAD=ec58447d..., porcelain 为空）"
git rev-parse HEAD
git status --porcelain
ls -l --time-style=full-iso "$BIN"