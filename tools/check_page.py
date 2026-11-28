#!/usr/bin/env python3
"""按「用户在页面上看到的字」数 CJK 命中数（标准 3/4/5/6/7 的判定脚本）。

渲染方式：优先用平台的 CDP 浏览器（环境变量 RAKAZO_CDP_PORT，默认 9222）——那是真实
Chromium，能执行 SPA 的 ES 模块；拿 `document.body.innerText`（= 浏览器判定可见的文本，
天然排除 <script>/<style>/注释/属性值/隐藏元素）与 `document.title`。拿不到 CDP 时退回
`chromium --dump-dom`。

纯标准库（websocket 握手与帧解析自己写，不装包）。

用法：
  python3 tools/check_page.py --url 'http://127.0.0.1:8080/?lang=en' --whitelist tools/whitelist.txt
  python3 tools/check_page.py --url 'http://127.0.0.1:8080/?lang=zh' --min 20
  python3 tools/check_page.py --url 'http://127.0.0.1:8080/' --cookie lang=en --whitelist tools/whitelist.txt

退出码：0 通过（0 hits，或给了 --min 时 hits>=min）；1 不通过；2 环境问题。
输出固定含 `CJK hits: N`。
"""
import argparse
import base64
import hashlib
import json
import os
import re
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
import urllib.request
from html.parser import HTMLParser

CJK = re.compile(r"[\u3000-\u303f\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uff00-\uffef]")
SKIP_TAGS = {"script", "style", "noscript", "template", "code", "pre"}


# ---------------- 最小 WebSocket 客户端（RFC6455，只做文本帧） ----------------
class WS:
    def __init__(self, host, port, path, timeout=30):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        req = (
            "GET %s HTTP/1.1\r\nHost: %s:%d\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
            "Sec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n\r\n" % (path, host, port, key)
        )
        self.sock.sendall(req.encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            buf += self.sock.recv(4096)
        if b"101" not in buf.split(b"\r\n")[0]:
            raise RuntimeError("websocket handshake failed: %r" % buf[:80])

    def send(self, obj):
        data = json.dumps(obj).encode()
        header = bytearray([0x81])
        n = len(data)
        if n < 126:
            header.append(0x80 | n)
        elif n < 65536:
            header.append(0x80 | 126)
            header += struct.pack(">H", n)
        else:
            header.append(0x80 | 127)
            header += struct.pack(">Q", n)
        mask = os.urandom(4)
        header += mask
        self.sock.sendall(bytes(header) + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def _read(self, n):
        buf = b""
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise RuntimeError("connection closed")
            buf += chunk
        return buf

    def recv(self):
        payload = b""
        while True:
            b0, b1 = self._read(2)
            fin, opcode = b0 & 0x80, b0 & 0x0F
            ln = b1 & 0x7F
            if ln == 126:
                ln = struct.unpack(">H", self._read(2))[0]
            elif ln == 127:
                ln = struct.unpack(">Q", self._read(8))[0]
            data = self._read(ln) if ln else b""
            if opcode == 0x9:  # ping
                self.sock.sendall(b"\x8a" + bytes([len(data)]) + data)
                continue
            payload += data
            if fin:
                return payload.decode("utf-8", "replace")


def cdp_http(port, path, method="GET"):
    req = urllib.request.Request("http://127.0.0.1:%d%s" % (port, path), method=method)
    with urllib.request.urlopen(req, timeout=10) as r:
        body = r.read().decode("utf-8", "replace")
        return json.loads(body) if body.strip() else {}


def render_cdp(url, cookie):
    port = int(os.environ.get("RAKAZO_CDP_PORT", "9222"))
    try:
        cdp_http(port, "/json/version")
    except Exception as e:
        return None, "cdp unavailable: %s" % e
    # 新版 Chrome 要求 PUT（GET 会 405）；target 用 about:blank，稍后 Page.navigate 到目标 URL
    target = cdp_http(port, "/json/new?about:blank", method="PUT")
    ws = WS("127.0.0.1", port, "/devtools/page/" + target["id"])
    try:
        for i, (method, params) in enumerate([
            ("Page.enable", {}),
            ("Network.enable", {}),
        ], start=1):
            ws.send({"id": i, "method": method, "params": params})
            while True:
                msg = json.loads(ws.recv())
                if msg.get("id") == i:
                    break
        if cookie:
            k, v = cookie
            from urllib.parse import urlparse
            u = urlparse(url)
            ws.send({"id": 90, "method": "Network.setCookie", "params": {
                "name": k, "value": v, "url": "%s://%s/" % (u.scheme, u.netloc)}})
            while True:
                msg = json.loads(ws.recv())
                if msg.get("id") == 90:
                    break
        ws.send({"id": 91, "method": "Page.navigate", "params": {"url": url}})
        deadline = time.time() + 25
        loaded = False
        while time.time() < deadline:
            try:
                ws.sock.settimeout(3)
                msg = json.loads(ws.recv())
            except socket.timeout:
                break
            if msg.get("method") == "Page.loadEventFired":
                loaded = True
                break
        # SPA 是模块 + 若干 API 请求，load 事件后再等一会儿让渲染稳定
        time.sleep(1.8 if loaded else 3.0)
        ws.send({"id": 92, "method": "Runtime.evaluate", "params": {
            "expression": "JSON.stringify({t:document.title,x:document.body?document.body.innerText:''})",
            "returnByValue": True, "awaitPromise": True}})
        while True:
            msg = json.loads(ws.recv())
            if msg.get("id") == 92:
                val = msg["result"]["result"].get("value") or '{"t":"","x":""}'
                d = json.loads(val)
                return {"title": d.get("t", ""), "text": d.get("x", "")}, None
    finally:
        try:
            ws.sock.close()
        except Exception:
            pass
        try:
            cdp_http(port, "/json/close/" + target["id"])
        except Exception:
            pass


class TextNodes(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.chunks = []

    def handle_starttag(self, tag, attrs):
        if tag in SKIP_TAGS:
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip and data.strip():
            self.chunks.append(data)


def render_dumpdom(url, cookie=None):
    exe = None
    for name in ("chromium", "chromium-browser", "google-chrome"):
        p = shutil.which(name)
        if p:
            exe = p
            break
    if not exe:
        return None, "no chromium"
    prof = tempfile.mkdtemp(prefix="rf4-check-")
    try:
        cmd = [exe, "--headless=new", "--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage",
               "--user-data-dir=" + prof, "--virtual-time-budget=5000", "--dump-dom", url]
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
        if not out.stdout.strip():
            return None, "empty dom"
        p = TextNodes()
        p.feed(out.stdout)
        return {"title": "", "text": "\n".join(p.chunks)}, None
    except subprocess.TimeoutExpired:
        return None, "chromium dump-dom timed out"
    finally:
        shutil.rmtree(prof, ignore_errors=True)


def whitelist_samples(path):
    out = []
    if path and os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and " :: " in line:
                parts = [p.strip() for p in line.split(" :: ")]
                if len(parts) >= 2 and parts[1]:
                    out.append(parts[1])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--whitelist")
    ap.add_argument("--cookie", help="形如 lang=en：先给浏览器种 cookie，再不带宽参数访问目标 URL")
    ap.add_argument("--min", type=int, default=None, help="要求 hits >= N（标准 5）")
    ap.add_argument("--dump", action="store_true", help="打印渲染后的文本")
    ap.add_argument("--backend", choices=["auto", "cdp", "dumpdom"], default="auto")
    a = ap.parse_args()

    cookie = None
    if a.cookie:
        k, v = a.cookie.split("=", 1)
        cookie = (k, v)

    page, err = (None, None)
    if a.backend in ("auto", "cdp"):
        page, err = render_cdp(a.url, cookie)
    if page is None and a.backend in ("auto", "dumpdom"):
        page, err = render_dumpdom(a.url)
    if page is None:
        print("CJK hits: 0")
        print("verdict: ERROR (no renderer)")
        print("reason: " + str(err))
        return 2

    samples = whitelist_samples(a.whitelist)
    text = page["text"]
    lines = [ln for ln in text.splitlines() if ln.strip()]
    kept, exempt = [], []
    for ln in lines:
        if any(s and s in ln for s in samples):
            exempt.append(ln)
            continue
        kept.extend(CJK.findall(ln))
    title_hits = [c for c in CJK.findall(page["title"])
                  if not any(s and s in page["title"] for s in samples)]

    print("url: " + a.url)
    print("title: " + page["title"])
    print("CJK hits: %d" % (len(kept) + len(title_hits)))
    if kept or title_hits:
        seen = []
        for ch in kept + title_hits:
            if ch not in seen:
                seen.append(ch)
        print("distinct: " + "".join(seen[:60]))
        for ln in lines:
            if CJK.search(ln) and not any(s and s in ln for s in samples):
                print("  hit: " + ln.strip()[:180])
    if exempt:
        print("whitelisted lines: %d" % len(exempt))
        for ln in exempt:
            print("  exempt: " + ln.strip()[:120])
    if a.dump:
        print("---- text ----")
        print(text)

    total = len(kept) + len(title_hits)
    if a.min is not None:
        ok = total >= a.min
        print("verdict: %s (need >= %d)" % ("PASS" if ok else "FAIL", a.min))
        return 0 if ok else 1
    ok = total == 0
    print("verdict: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())