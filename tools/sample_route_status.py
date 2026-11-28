#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""运行期路由状态码复核（M2 起服务后执行），与 baseline_ids.json 的 expected_status 逐条比对。

用法：
    python3 shared/deliverables/rf4-i18n-01/tools/sample_route_status.py \
        --repo shared/work/rf4_server_simulator \
        --baseline shared/deliverables/rf4-i18n-01/tools/baseline_ids.json \
        --base-8080 http://127.0.0.1:8080 --base-9500 http://127.0.0.1:9500 \
        --out shared/deliverables/rf4-i18n-01/tools/route_status.sampled.json

只跑 sample_policy=sample 的条目：标 skip 的会真的起停服务、开浏览器或写盘，
不在验收里碰。纯标准库（urllib），失败不抛栈，逐条记录。
退出码：0 = 全部一致；1 = 有差异（差异明细打到 stdout）。
"""

import argparse
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def hit(method, url):
    req = urllib.request.Request(url, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, ""
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:
        return None, str(e)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", default="shared/deliverables/rf4-i18n-01/tools/baseline_ids.json")
    ap.add_argument("--base-8080", default="http://127.0.0.1:8080")
    ap.add_argument("--base-9500", default="http://127.0.0.1:9500")
    ap.add_argument("--out", default="shared/deliverables/rf4-i18n-01/tools/route_status.sampled.json")
    args = ap.parse_args()

    data = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    bases = {"8080": args.base_8080, "9500": args.base_9500}
    results, diffs = [], []
    for port, base in bases.items():
        for r in data["routes"][port]:
            if r.get("sample_policy") != "sample":
                continue
            url = base + r["path"]
            got, err = hit(r["method"], url)
            ok = got == r["expected_status"]
            results.append({
                "port": port, "method": r["method"], "path": r["path"],
                "expected": r["expected_status"], "observed": got, "match": ok, "error": err,
            })
            if not ok:
                diffs.append((port, r["method"], r["path"], r["expected_status"], got, err))

    out = {
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "baseline": str(args.baseline),
        "count": len(results),
        "mismatch": len(diffs),
        "results": results,
    }
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("sampled %d routes, mismatch %d -> %s" % (len(results), len(diffs), args.out))
    for d in diffs:
        print("MISMATCH port=%s %s %s expected=%s observed=%s %s" % d)
    return 0 if not diffs else 1


if __name__ == "__main__":
    raise SystemExit(main())