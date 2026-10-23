#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Chụp màn hình một bài báo làm bằng chứng.

    python capture_evidence.py URL --out video1/evidence --name ten-ngan

Mặc định chụp viewport 1280x1800 (đủ để thấy tiêu đề + đoạn đầu).
Ảnh lưu: <out>/<name>.png, metadata: <out>/<name>.json
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

EDGE = [
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
]


def find_browser() -> Path:
    for p in EDGE:
        if p.exists():
            return p
    raise SystemExit("Không thấy Edge/Chrome để chụp màn hình.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--out", default="evidence")
    ap.add_argument("--name", default="")
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=1800)
    ap.add_argument("--wait", type=int, default=6000)
    ap.add_argument("--mobile", action="store_true",
                    help="gia lap dien thoai (UA iPhone, viewport 430x764)")
    ap.add_argument("--user-agent", default="")
    a = ap.parse_args()

    if a.mobile:
        a.width, a.height = 430, 764
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    name = a.name.strip() or f"evidence_{int(time.time())}"
    name = "".join(c if c.isalnum() or c in "-_" else "-" for c in name)
    img = out / f"{name}.png"
    profile = Path(tempfile.mkdtemp(prefix="evidence-browser-"))

    cmd = [
        str(find_browser()),
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        "--no-first-run",
        f"--user-data-dir={profile}",
        f"--window-size={a.width},{a.height}",
        f"--virtual-time-budget={a.wait}",
        f"--screenshot={img}",
    ]
    ua = a.user_agent or (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
        "Mobile/15E148 Safari/604.1" if a.mobile else "")
    if ua:
        cmd.append(f"--user-agent={ua}")
    cmd.append(a.url)
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if not img.exists():
        raise SystemExit((r.stderr or r.stdout or "chụp thất bại")[-1200:])

    meta = {"url": a.url, "screenshot": str(img), "width": a.width,
            "height": a.height, "captured_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    (out / f"{name}.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(img)


if __name__ == "__main__":
    main()
