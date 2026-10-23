#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Quét video/ảnh người dùng đưa vào, tạo assets.json + thumbnail.

    python index_assets.py "video1/assets" --out "video1/assets/assets.json"

- Video: ffprobe duration/kích thước, thumbnail tại 1s.
- Ảnh: đọc kích thước, thumbnail.
- Các trường description/tags để trống cho bước hiểu nội dung.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

VIDEO_EXT = {".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def probe(path: Path) -> dict:
    r = run(["ffprobe", "-v", "error", "-show_entries",
             "format=duration:stream=width,height", "-of", "json", str(path)])
    try:
        d = json.loads(r.stdout or "{}")
    except Exception:
        return {}
    st = (d.get("streams") or [{}])[0]
    return {"duration": round(float(d.get("format", {}).get("duration", 0) or 0), 3),
            "width": int(st.get("width") or 0), "height": int(st.get("height") or 0)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    root = Path(a.folder).resolve()
    if not root.exists():
        raise SystemExit(f"không thấy folder: {root}")
    out = Path(a.out) if a.out else root / "assets.json"
    thumbs = out.parent / "_thumbs"
    thumbs.mkdir(parents=True, exist_ok=True)

    items = []
    for p in sorted(root.iterdir()):
        if not p.is_file() or p.name.startswith("."):
            continue
        ext = p.suffix.lower()
        if ext not in VIDEO_EXT | IMAGE_EXT:
            continue
        item = {"file": str(p), "name": p.name,
                "type": "video" if ext in VIDEO_EXT else "image"}
        if item["type"] == "video":
            item.update(probe(p))
            thumb = thumbs / f"{p.stem}.jpg"
            if item.get("duration", 0) > 0:
                run(["ffmpeg", "-y", "-v", "error", "-ss",
                     f"{min(1.0, item['duration'] / 3):.2f}", "-i", str(p),
                     "-frames:v", "1", "-vf", "scale=480:-2", str(thumb)])
            item["thumb"] = str(thumb) if thumb.exists() else ""
        else:
            try:
                with Image.open(p) as im:
                    item["width"], item["height"] = im.size
            except Exception:
                pass
            thumb = thumbs / f"{p.stem}.jpg"
            try:
                with Image.open(p) as im:
                    im.convert("RGB").thumbnail((480, 480))
                    im.save(thumb, quality=85)
                item["thumb"] = str(thumb)
            except Exception:
                item["thumb"] = ""
        item["description"] = ""
        item["tags"] = []
        items.append(item)

    out.write_text(json.dumps({"assets": items}, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(out)
    print(f"{len(items)} asset")


if __name__ == "__main__":
    main()
