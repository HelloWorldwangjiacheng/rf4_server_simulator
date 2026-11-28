#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A11 自证：win_verify 的 http_any()/http_get() 不再跟随重定向，且能读到 Location。

纯标准库：http.server 起一个临时端点，对 /admin 回 307 + Location: /admin/，
对 /admin/ 回 200。然后用 tools/win_verify_9500.py 里的**同一对函数**去探。

同时把「旧行为」也跑一遍做对照：默认 urlopen 会跟随 307 落到 /admin/（200），
这就是修复前路由差集 want=307 got=200 的来源。

用法：
  python3 tools/check_no_redirect.py
退出码：0 = 观测到 307 + Location=/admin/ 且旧行为确为 200；1 = 断言失败。
"""
import os
import sys
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from win_verify_9500 import http_any, http_any_full, http_get  # noqa: E402


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path == "/admin":
            self.send_response(307)
            self.send_header("Location", "/admin/")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if self.path == "/admin/":
            body = b"admin console"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *args):
        pass


def main():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    url = "http://127.0.0.1:%d/admin" % port
    bad = 0
    try:
        st = http_any("GET", url)
        print("http_any(GET %s) -> %s" % (url, st))
        if st != 307:
            bad += 1

        st2, hdrs = http_any_full("GET", url)
        loc = hdrs.get("Location") or hdrs.get("location") or ""
        print("http_any_full -> status=%s, Location=%r" % (st2, loc))
        if st2 != 307 or not loc.endswith("/admin/"):
            bad += 1

        st3, hdrs3, _body = http_get(url)
        loc3 = hdrs3.get("Location") or hdrs3.get("location") or ""
        print("http_get   -> status=%s, Location=%r" % (st3, loc3))
        if st3 != 307 or not loc3.endswith("/admin/"):
            bad += 1

        # 对照：修复前的写法（默认 urlopen）会跟随 307 落到 /admin/ 的 200
        old = None
        try:
            with urllib.request.urlopen(url, timeout=10) as r:
                old = r.status
        except urllib.error.HTTPError as e:
            old = e.code
        print("对照：默认 urlopen（旧写法）-> %s（跟随 307 落到 /admin/）" % old)
        if old != 200:
            bad += 1
    finally:
        srv.shutdown()
        srv.server_close()

    print("")
    if bad:
        print("RESULT: FAIL（%d 项断言不成立）" % bad)
        return 1
    print("RESULT: OK（不跟随重定向：307 + Location=/admin/；旧写法确为 200）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())