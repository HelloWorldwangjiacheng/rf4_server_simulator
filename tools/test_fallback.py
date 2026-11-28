#!/usr/bin/env python3
"""标准 9：缺 key 回退不空白。纯标准库 + 本机 Go（构建临时副本，不改主仓库）。

做法（真删、真渲染，不是模拟）：
1. 把仓库拷到临时目录（跳过 .git/logs/data），只改拷贝里的 locales.data.js；
2. 从拷贝的 en 字典里**删掉**若干条 en 值（默认 admin.dashboard.overview + admin.shell.save）；
3. 用同一个 Go 工具链构建临时 admin 二进制，配置改到临时端口 18080，起服务；
4. 渲染 ?lang=en，断言：这些位置显示 zh 原文（总览 / 保存修改），且页面不出现
   裸 key（admin.dashboard.overview）、不出现 undefined / 空占位。
5. 关掉临时服务、删临时目录。

退出码 0 且输出 PASS 才算过。
"""
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DELIV = os.path.dirname(HERE)
REPO = os.path.abspath(os.path.join(DELIV, "..", "..", "work", "rf4_server_simulator"))
GO = os.path.abspath(os.path.join(DELIV, "..", "..", "tools", "go", "bin", "go"))
# 选「中文原文只对应一个 key、且必渲染」的两条，避免同句多 key 互相兜底造成假阳性
DROP_KEYS = ["admin.dashboard.server", "admin.dashboard.t345"]
EXPECT_ZH = ["服务器现在什么状态、当前生效的是哪套参数、最近动过什么。", "当前生效的关键口径"]
PORT = 18080


def free_port(port):
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def main():
    if not os.path.isdir(REPO):
        print("FAIL: repo copy not found at " + REPO)
        return 1
    if not os.path.exists(GO):
        print("FAIL: go toolchain not found at " + GO)
        return 1
    if not free_port(PORT):
        print("FAIL: port %d busy; stop other test servers first" % PORT)
        return 1

    tmp = tempfile.mkdtemp(prefix="rf4-fallback-")
    copy = os.path.join(tmp, "repo")
    # data/ 里是 sqlite（admin 启动要开库），logs/ 是日志目录：都要随副本走
    shutil.copytree(REPO, copy, ignore=shutil.ignore_patterns(".git", "node_modules"))
    try:
        # 1) 删 en 值
        bundle = os.path.join(copy, "internal/admin/web/app/locales.data.js")
        src = open(bundle, encoding="utf-8").read()
        removed = 0
        for k in DROP_KEYS:
            pat = re.compile(r'^\s*"' + re.escape(k) + r'":.*\n', re.M)
            src2 = pat.sub("", src)
            if src2 != src:
                removed += 1
            src = src2
        if removed != len(DROP_KEYS):
            print("FAIL: could not drop %d/%d keys from en bundle" % (removed, len(DROP_KEYS)))
            return 1
        open(bundle, "w", encoding="utf-8").write(src)

        # 2) 临时配置（只改 admin 端口，其余照抄）
        cfg = open(os.path.join(REPO, "config.yaml"), encoding="utf-8").read()
        if "admin:" not in cfg:
            print("FAIL: config.yaml has no admin section")
            return 1
        cfg = re.sub(r"(?m)^(\s*http_addr\s*:\s*).*$", r'\g<1>"127.0.0.1:%d"' % PORT, cfg, count=1)
        # admin 还会起一个观测端口，默认 :9503 会和主实例撞车（撞车时 admin 直接退出）
        cfg = re.sub(r'(?m)^(\s*obs_addr\s*:\s*)":9503"$', r'\g<1>":19503"', cfg, count=1)
        if str(PORT) not in cfg or "19503" not in cfg:
            print("FAIL: could not set temp admin ports in config")
            return 1
        open(os.path.join(copy, "config.yaml"), "w", encoding="utf-8").write(cfg)

        # 3) 构建临时 admin
        out = os.path.join(tmp, "admin")
        env = dict(os.environ, GOFLAGS="-mod=mod", GOCACHE=os.environ.get("GOCACHE", "/tmp/go-build"))
        b = subprocess.run([GO, "build", "-o", out, "./cmd/admin"], cwd=copy, env=env,
                           capture_output=True, text=True)
        if b.returncode != 0:
            print("FAIL: build failed\n" + b.stderr[-1200:])
            return 1

        # 4) 起服务、渲染
        log = open(os.path.join(tmp, "admin.log"), "w")
        proc = subprocess.Popen([out, "-config", "config.yaml"], cwd=copy,
                                stdout=log, stderr=subprocess.STDOUT)
        try:
            for _ in range(40):
                if _http_ok("http://127.0.0.1:%d/" % PORT):
                    break
                time.sleep(0.25)
            else:
                print("FAIL: temp admin did not answer on %d" % PORT)
                log.flush()
                print("---- temp admin log ----")
                print(open(os.path.join(tmp, "admin.log"), encoding="utf-8").read()[-1500:])
                return 1
            text = render("http://127.0.0.1:%d/?lang=en" % PORT)
            tl = subprocess.run([sys.executable, os.path.join(HERE, "check_page.py"),
                                 "--url", "http://127.0.0.1:%d/?lang=en" % PORT, "--dump"],
                                capture_output=True, text=True, timeout=120)
            body = tl.stdout
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
            log.close()

        ok = True
        for zh in EXPECT_ZH:
            if zh not in body:
                print("FAIL: dropped key did not fall back to zh text: %s" % zh)
                ok = False
        for bad in DROP_KEYS + ["undefined", "NaN"]:
            if bad in body:
                print("FAIL: page shows broken placeholder: %s" % bad)
                ok = False
        print("dropped en keys: " + ", ".join(DROP_KEYS))
        print("fallback rendered zh: " + ", ".join(EXPECT_ZH))
        print("verdict: " + ("PASS" if ok else "FAIL"))
        return 0 if ok else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _http_ok(url):
    import urllib.request
    try:
        with urllib.request.urlopen(url, timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def render(url):
    import urllib.request
    with urllib.request.urlopen(url, timeout=5) as r:
        return r.read().decode("utf-8", "replace")


if __name__ == "__main__":
    raise SystemExit(main())