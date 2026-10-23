#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""cut.py — entry point.

    python scripts/cut.py open raw/clip.mp4              # transcribe + web view
    python scripts/cut.py export output/clip.review.json # render

`open` renames nothing and renders nothing: the web page plays the original
file and jumps over the cuts, so you hear the real rhythm before committing.

Dependencies: ffmpeg, ffprobe, faster-whisper. Nothing else.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path

# Windows console may default to cp1252; Vietnamese text and arrows crash print().
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


# ---------------------------------------------------------------- env
def _venv_python() -> Path | None:
    cands = []
    env = os.environ.get("DSH_VIDEO_ASR_VENV")
    if env:
        cands.append(Path(env) / "Scripts" / "python.exe")
    cands += [Path.home() / ".dsh/tools/asr-venv/Scripts/python.exe"]
    return next((c for c in cands if c.exists()), None)


def _ensure_whisper() -> None:
    """Chay lai chinh script bang python co faster-whisper neu can."""
    try:
        import faster_whisper  # noqa: F401,PLC0415
        return
    except Exception:
        pass
    py = _venv_python()
    if py and Path(sys.executable).resolve() != py.resolve():
        os.execv(str(py), [str(py)] + sys.argv)
    sys.exit("thieu faster-whisper — cai bang: pip install faster-whisper "
             "(hoac dat DSH_VIDEO_ASR_VENV tro toi venv co no)")


def _run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", **kw)


def probe_fps(path: str) -> float:
    r = _run(["ffprobe", "-v", "error", "-select_streams", "v:0",
              "-show_entries", "stream=r_frame_rate",
              "-of", "default=nw=1:nk=1", path])
    s = (r.stdout or "").strip()
    if "/" in s:
        n, d = s.split("/")
        return float(n) / float(d or 1) if float(d or 1) else 30.0
    return float(s or 30.0)


def probe_duration(path: str) -> float:
    r = _run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
              "-of", "default=nw=1:nk=1", path])
    return round(float((r.stdout or "0").strip() or 0), 3)


# ---------------------------------------------------------------- open
def cmd_open(a) -> None:
    _ensure_whisper()
    video = Path(a.video).resolve()
    if not video.exists():
        sys.exit(f"khong thay file: {video}")
    out_dir = Path(a.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rough = out_dir / f"{video.stem}.rough.json"
    review = out_dir / f"{video.stem}.review.json"

    if a.rebuild or not rough.exists():
        print(f"[1/2] transcribe {video.name} (model {a.model}) ...", flush=True)
        rc = subprocess.run([sys.executable, str(HERE / "roughcut.py"), "build",
                             str(video), "--out", str(rough), "--model", a.model,
                             "--lang", a.lang, "--db", str(a.db),
                             "--min-sil", str(a.min_sil), "--split", str(a.split)])
        if rc.returncode != 0:
            sys.exit("transcribe that bai")
        print(f"      bang: {out_dir / (video.stem + '.tables.md')}")
    else:
        print(f"[1/2] dung lai transcript: {rough.name}")

    print("[2/2] mo web view ...", flush=True)
    import review_server as rs  # noqa: PLC0415

    sys.argv = ["review_server.py", "--rough", str(rough), "--out", str(review),
                "--port", str(a.port)]
    rs.main()


# ---------------------------------------------------------------- render
def render_edl(edl: dict, out_path: Path, crf: int = 18,
               preview: bool = False, seamless: bool = False) -> None:
    """trim + concat (khong bao gio dung -vf select), fade, loudnorm -14.

    `preview=True` render 360p veryfast de duyet nhanh, khong phai ban giao.
    `seamless=True` fade 20ms va khong giu dem nghi giua cac cau.
    """
    src = edl["sources"][0]
    segs = src["segments"]
    chains, pairs = [], []
    for i, s in enumerate(segs):
        a, b = s["start"], s["end"]
        d = round(b - a, 3)
        fade = round(min(0.02 if seamless else 0.03, d / 4), 3)
        chains.append(f"[0:v]trim=start={a}:end={b},setpts=PTS-STARTPTS[v{i}]")
        chains.append(f"[0:a]atrim=start={a}:end={b},asetpts=PTS-STARTPTS,"
                      f"afade=t=in:st=0:d={fade},"
                      f"afade=t=out:st={round(d - fade, 3)}:d={fade}[a{i}]")
        pairs.append(f"[v{i}][a{i}]")
    n = len(segs)
    filt = ";".join(chains)
    filt += f";{''.join(pairs)}concat=n={n}:v=1:a=1[vc][ac]"
    filt += ";[ac]loudnorm=I=-14:TP=-1.5:LRA=11[ao]"
    filt += ";[vc]scale=360:-2[vo]" if preview else ";[vc]null[vo]"
    cmd = ["ffmpeg", "-hide_banner", "-y", "-i", src["path"],
           "-filter_complex", filt, "-map", "[vo]", "-map", "[ao]",
           "-c:v", "libx264", "-crf", str(24 if preview else crf),
           "-preset", "veryfast" if preview else "medium",
           "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "128k" if preview else "192k",
           "-ar", "48000", "-ac", "2",
           "-movflags", "+faststart", str(out_path)]
    r = _run(cmd)
    if r.returncode != 0:
        sys.exit("render that bai:\n" + (r.stderr or "")[-2000:])


# ---------------------------------------------------------------- export
def cmd_export(a) -> None:
    src = Path(a.review)
    data = json.loads(src.read_text(encoding="utf-8"))
    video = data["video"]
    dur = float(data["duration"])
    stem = src.stem.replace(".review", "")
    suffix = ".preview.mp4" if a.preview else ".mp4"
    out_mp4 = Path(a.out or src.with_name(stem + suffix))
    edl_path = src.with_name(stem + ".edl.json")
    fps = a.fps or probe_fps(video)
    step = 1.0 / fps

    rows = [s for s in data["sentences"] if s.get("keep")]
    if not rows:
        sys.exit("khong con cau nao duoc giu")

    # Cắt sát: lặng trong câu >= 0.20s cũng bỏ, giữ 80ms sau tiếng và
    # 100ms trước tiếng; đệm cuối câu 100ms, pre-roll 40ms.
    rough_path = src.with_name(stem + ".rough.json")
    inner_sils = []
    if rough_path.exists():
        inner_sils = json.loads(rough_path.read_text(encoding="utf-8")).get(
            "silences", [])

    raw: list[list[float]] = []
    for i, s in enumerate(rows):
        if a.seamless:
            # câu hoàn chỉnh: cắt đúng biên tiếng, không đệm, không thở
            a0 = max(0.0, float(s["start"]))
            b0 = min(dur, float(s["end"]))
        else:
            pre = min(float(s.get("pause", 0.08)), float(s.get("avail", 0.08)))
            if s.get("pre") is not None:
                pre = min(float(s.get("avail", 0.08)), max(0.0, float(s["pre"])))
            else:
                pre = min(float(s.get("avail", 0.08)), max(0.04, pre))
            a0 = max(0.0, float(s["start"]) - pre)
            b0 = min(dur, float(s["end"]) + 0.10)
        pieces = [[a0, b0]]
        for sil in inner_sils:
            x, y = float(sil["start"]), float(sil["end"])
            if y - x < (0.10 if a.seamless else 0.20):
                continue
            nxt = []
            for p0, p1 in pieces:
                if x > p0 + 0.15 and y < p1 - 0.15:
                    if a.seamless:
                        nxt.append([p0, x])
                        nxt.append([y, p1])
                    else:
                        nxt.append([p0, round(x + 0.08, 3)])
                        nxt.append([round(y - 0.10, 3), p1])
                else:
                    nxt.append([p0, p1])
            pieces = nxt
        for p0, p1 in pieces:
            if raw and p0 < raw[-1][1]:
                p0 = raw[-1][1]
            if p1 - p0 >= 0.30:
                raw.append([p0, p1])

    segs = []
    for a0, b0 in raw:
        if a.seamless:
            # lay tron frame bien: khong cat vao phu am dau/cuoi
            s0 = round(math.floor(a0 / step + 1e-9) * step, 4)
            s1 = round(math.ceil(b0 / step - 1e-9) * step, 4)
        else:
            s0 = round(math.ceil(a0 / step - 1e-6) * step, 4)
            s1 = round(math.floor(b0 / step + 1e-6) * step, 4)
        if s1 - s0 >= 0.25:
            segs.append({"start": s0, "end": s1, "duration": round(s1 - s0, 3)})

    total = round(sum(s["duration"] for s in segs), 3)
    edl = {
        "ok": True, "mode": "edit-chinh-tri", "fps": fps,
        "source_total": round(dur, 3), "output_estimate": total,
        "compression_pct": round(100 * (1 - total / dur), 1),
        "sources": [{"path": video, "duration": round(dur, 3),
                     "segments": segs}],
        "subtitles": [{"start": s["start"], "end": s["end"],
                       "text": s.get("text", "")} for s in rows],
    }
    edl_path.write_text(json.dumps(edl, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    print(f"EDL: {edl_path}  ({len(segs)} doan, {total:.2f}s)")

    print(f"{'preview' if a.preview else 'render'} -> {out_mp4} ...", flush=True)
    render_edl(edl, out_mp4, preview=a.preview, seamless=a.seamless)

    # ---- self-check
    got = probe_duration(out_mp4)
    sil = _run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(out_mp4), "-af",
                "silencedetect=noise=-45dB:d=0.6", "-f", "null", "-"])
    longs = re.findall(r"silence_duration: ([\d.]+)", (sil.stderr or ""))
    luf = _run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(out_mp4), "-vn",
                "-af", "ebur128=peak=true", "-f", "null", "-"])
    m_i = re.findall(r"I:\s*(-?[\d.]+) LUFS", luf.stderr or "")
    m_p = re.findall(r"Peak:\s*(-?[\d.]+) dBFS", luf.stderr or "")
    lufs, peak = (m_i[-1] if m_i else "?"), (m_p[-1] if m_p else "?")

    if a.seamless:
        cut_line = "- cắt sát biên tiếng: không đệm, không kiểm tra mức to"
    else:
        worst, worst_at = -99.0, ""
        for s in segs:
            for name, t in (("in", s["start"]), ("out", s["end"])):
                # dau/cuoi clip goc khong phai moi cat: clip co the ket thuc giua
                # tieng noi, khong the doi thanh cat trong lang.
                if ((name == "in" and t <= 0.05)
                        or (name == "out" and t >= dur - 0.05)):
                    continue
                v = _run(["ffmpeg", "-hide_banner", "-nostats", "-ss",
                          f"{max(0, t - 0.08):.3f}", "-to", f"{t + 0.08:.3f}",
                          "-i", video, "-vn", "-af", "volumedetect",
                          "-f", "null", "-"])
                m = re.search(r"max_volume:\s*(-?[\d.]+)", v.stderr or "")
                if m and float(m.group(1)) > worst:
                    worst, worst_at = float(m.group(1)), f"{name} {t:.2f}"
        cut_line = (f"- moi cat to nhat: **{worst:.1f} dB** tai {worst_at} "
                    f"({'OK' if worst < -38 else 'CAN KIEM'})")

    report = [
        f"# {out_mp4.name}",
        "",
        f"- {dur:.2f}s -> **{got:.2f}s** ({len(segs)} doan, "
        f"-{100 * (1 - got / dur):.1f}%)",
        f"- loudness **{lufs} LUFS**, peak **{peak} dBFS**",
        f"- khoang lang > 0.6s: {len(longs)}",
        cut_line,
        "",
        "| # | in | out | dai |",
        "|---|----|-----|-----|",
    ]
    for i, s in enumerate(segs, 1):
        report.append(f"| {i} | {s['start']:.2f} | {s['end']:.2f} | "
                      f"{s['duration']:.2f} |")
    rep_path = out_mp4.with_suffix(".report.md")
    rep_path.write_text("\n".join(report), encoding="utf-8")
    print("\n".join(report))
    print(f"\nbao cao: {rep_path}")


def main() -> None:
    ap = argparse.ArgumentParser(prog="cut.py")
    sub = ap.add_subparsers(dest="cmd", required=True)

    o = sub.add_parser("open", help="transcribe + mo web view")
    o.add_argument("video")
    o.add_argument("--out-dir", default="output")
    o.add_argument("--port", type=int, default=8799)
    o.add_argument("--model", default="medium")
    o.add_argument("--lang", default="vi")
    o.add_argument("--db", type=float, default=-50.0)
    o.add_argument("--min-sil", type=float, default=0.35)
    o.add_argument("--split", type=float, default=0.80)
    o.add_argument("--rebuild", action="store_true")
    o.set_defaults(func=cmd_open)

    e = sub.add_parser("export", help="xuat clip tu review.json")
    e.add_argument("review")
    e.add_argument("--out", default="")
    e.add_argument("--fps", type=float, default=0.0)
    e.add_argument("--preview", action="store_true",
                   help="render 360p veryfast de duyet, khong phai ban giao")
    e.add_argument("--seamless", action="store_true",
                   help="cat dung bien tieng, khong dem nghi giua cac cau")
    e.set_defaults(func=cmd_export)

    a = ap.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
