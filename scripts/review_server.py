#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""review_server.py — web view chinh cut + phu de tren CLIP GOC.

Khong render gi ca: trang web dung chinh file nguon, tu nhay qua cac khoang
da cat nen xem duoc dung nhip cua ban dung sau khi cat.

    python tools/review_server.py --rough output/1020.rough.json \
        --edl output/1020_cut.edl.json --out output/1020.review.json

Mo http://127.0.0.1:8799/ — bam "Luu" xong thi bao toi, toi xuat theo file
review do.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

# Windows console may default to cp1252; Vietnamese text and arrows crash print().
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

STATE: dict = {}
OUT_PATH: Path = Path("output/review.json")
VIDEO_PATH: Path = Path("raw/clip.mp4")


# ---------------------------------------------------------------- du lieu
def make_peaks(path: str, buckets: int = 1500) -> list[float]:
    """Do cao song am (0..1) cho canvas, tinh tu audio that."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-v", "error", "-i", path,
                        "-vn", "-ac", "1", "-ar", "4000", "-f", "s16le", "-"],
                       capture_output=True)
    raw = r.stdout
    if not raw:
        return []
    n = len(raw) // 2
    step = max(1, n // buckets)
    out = []
    for i in range(0, n, step):
        chunk = raw[i * 2:(i + step) * 2]
        peak = 0
        for j in range(0, len(chunk) - 1, 2):
            v = chunk[j] | (chunk[j + 1] << 8)
            if v > 32767:
                v -= 65536
            if v < 0:
                v = -v
            if v > peak:
                peak = v
        out.append(round(min(1.0, peak / 32768.0 * 4.0), 3))
    return out


def overlap(a: tuple[float, float], b: tuple[float, float]) -> float:
    return max(0.0, min(a[1], b[1]) - max(a[0], b[0]))


def build_state(rough_path: Path, edl_path: Path | None) -> dict:
    rough = json.loads(rough_path.read_text(encoding="utf-8"))
    sents = rough["sentences"]
    dur = rough["duration"]
    video = rough["video"]

    sys.path.insert(0, str(Path(__file__).parent))
    import roughcut as R  # noqa: PLC0415

    sils = R.classify_silences(sents, R.merge_silences(rough["silences"]), dur)
    params = rough.get("params", {})
    pairs = R.find_retakes(sents, params.get("window", 20.0),
                           params.get("cover", 0.80),
                           params.get("min_tokens", 4))
    frags = {f["i"]: f for f in R.find_fragments(sents, sils)}

    kept_ranges: list[tuple[float, float]] = []
    if edl_path and edl_path.exists():
        edl = json.loads(edl_path.read_text(encoding="utf-8"))
        kept_ranges = [(s["start"], s["end"])
                       for s in edl["sources"][0]["segments"]]

    tags: dict[int, tuple[str, bool]] = {}
    for p in pairs:
        idx = p.get("bo") or [p["a"]]
        strong = bool(p.get("strong"))
        for i in idx:
            label = "nói lại" if strong else f"nói lại {p['cover'] * 100:.0f}%"
            tags.setdefault(i, (f"{label} → giữ S{p['b'] + 1}", False))
    for i, f in frags.items():
        if f.get("kind") == "orphan":
            tags[i] = ("câu lạc lõng", False)
        elif f.get("kind") == "lead_in":
            tags[i] = ("câu mở dở", False)
        else:
            tags[i] = (f"nói vấp ({f['score']} điểm)", False)

    out = []
    for i, s in enumerate(sents):
        tag, auto_keep = tags.get(i, ("", True))
        if kept_ranges:
            kept = any(overlap((s["start"], s["end"]), k) > 0.15
                       for k in kept_ranges)
        else:
            kept = auto_keep
        gap = next((x["duration"] for x in sils
                    if abs(x["end"] - s["start"]) <= 0.35), 0.0)
        out.append({
            "id": f"S{i + 1}",
            "start": s["start"], "end": s["end"],
            "text": s["text"], "tag": tag,
            "keep": kept, "pause": 0.10,
            "avail": round(max(0.0, gap - 0.05), 2),
        })

    # nhip thoi: 3 cau lien mach, sau do moi nghi dai 0.45s
    n = 0
    for row in out:
        if not row["keep"]:
            row["pause"] = 0.0
            continue
        n += 1
        if n == 1:
            row["pause"] = 0.08      # dem cau dau, khong cat vao tieng
        else:
            row["pause"] = 0.65 if n % 3 == 1 else 0.0

    return {
        "video": video,
        "duration": dur,
        "sentences": out,
        "peaks": make_peaks(video),
        "built": round(sum(max(0.0, r["end"] - r["start"] + 0.10
                               + min(r["pause"], r["avail"]))
                           for r in out if r["keep"]), 2),
    }


# ---------------------------------------------------------------- trang
PAGE = r"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8">
<title>Rough cut review</title>
<style>
:root{--bg:#0f1115;--panel:#171a21;--line:#262b36;--txt:#e6e8ee;--dim:#8b93a5;
--ok:#3ddc97;--bad:#ff5c7a;--accent:#5b9dff}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--txt);font:14px/1.45 -apple-system,"Segoe UI",Roboto,sans-serif}
header{display:flex;gap:16px;align-items:center;padding:10px 16px;border-bottom:1px solid var(--line);background:var(--panel)}
header b{font-size:15px}
.pill{padding:3px 9px;border-radius:99px;background:#20242e;color:var(--dim);font-size:12px}
.pill.ok{background:rgba(61,220,151,.14);color:var(--ok)}
main{display:grid;grid-template-columns:540px 1fr;gap:16px;padding:16px 16px 68px;height:calc(100vh - 52px)}
.left{display:flex;flex-direction:column;gap:10px;min-height:0}
.stage{position:relative;background:#000;border-radius:10px;overflow:hidden;flex:1;min-height:0}
video{width:100%;height:100%;object-fit:contain;display:block}
#sub{position:absolute;left:8%;right:8%;bottom:9%;text-align:center;font-weight:800;
font-size:24px;line-height:1.25;text-transform:uppercase;letter-spacing:.5px;
color:#fff;text-shadow:0 2px 6px #000,0 0 3px #000;pointer-events:none}
#sub.off{display:none}
.bar{display:flex;gap:8px;align-items:center}
button{background:#232937;color:var(--txt);border:1px solid var(--line);border-radius:8px;
padding:7px 12px;cursor:pointer;font:inherit}
button:hover{background:#2b3243}
button.on{background:var(--accent);border-color:var(--accent);color:#08101f;font-weight:700}
#wave{width:100%;height:64px;display:block;border-radius:8px;background:#12151b;cursor:crosshair}
.right{overflow:auto;border:1px solid var(--line);border-radius:10px;background:var(--panel)}
.row{display:grid;grid-template-columns:26px 92px 1fr 96px 40px;gap:8px;align-items:center;
padding:8px 10px;border-bottom:1px solid var(--line)}
.row:last-child{border-bottom:0}
.row.cut{opacity:.45}
.row.cur{background:rgba(91,157,255,.10)}
.row.cur .id{color:var(--accent)}
.id{font-weight:700;color:var(--dim);font-size:12px}
.meta{font-variant-numeric:tabular-nums;font-size:12px;color:var(--dim)}
.meta b{color:var(--txt);font-weight:600}
.tag{display:inline-block;font-size:11px;padding:1px 6px;border-radius:5px;
background:rgba(255,92,122,.16);color:var(--bad);margin-top:2px}
.txt{width:100%;background:#0f1218;color:var(--txt);border:1px solid var(--line);
border-radius:6px;padding:6px 8px;font:inherit;font-size:13px}
.txt:focus{outline:0;border-color:var(--accent)}
select{background:#0f1218;color:var(--txt);border:1px solid var(--line);border-radius:6px;
padding:5px;font:inherit;font-size:12px;width:100%}
input[type=checkbox]{width:17px;height:17px;accent-color:var(--ok);cursor:pointer}
footer{position:fixed;left:0;right:0;bottom:0;padding:10px 16px;background:var(--panel);
border-top:1px solid var(--line);display:flex;gap:14px;align-items:center;font-size:13px}
footer .big{font-size:17px;font-weight:700;font-variant-numeric:tabular-nums}
.hint{color:var(--dim);font-size:12px}
#saved{color:var(--ok);opacity:0;transition:opacity .3s}
#saved.show{opacity:1}
</style></head><body>
<header>
  <b>Rough cut</b>
  <span class="pill" id="src"></span>
  <span class="pill" id="cnt"></span>
  <span class="hint">Space: phát/dừng · X: bỏ/giữ câu đang nghe · ←/→: ±1s</span>
</header>
<main>
  <div class="left">
    <div class="stage">
      <video id="v" src="/video" preload="auto" playsinline></video>
      <div id="sub"></div>
    </div>
    <canvas id="wave" width="1200" height="64"></canvas>
    <div class="bar">
      <button id="play">▶ Phát</button>
      <button id="restart">⏮ Từ đầu</button>
      <button id="cc" class="on">Phụ đề</button>
      <span class="hint" id="pos"></span>
    </div>
  </div>
  <div class="right" id="list"></div>
</main>
<footer>
  <span>Dài dự kiến</span><span class="big" id="total"></span>
  <span class="hint" id="vs"></span>
  <span style="flex:1"></span>
  <span id="saved">đã lưu</span>
  <button id="save">Lưu</button>
</footer>
<script>
const S = __STATE__;
const v = document.getElementById('v');
const subEl = document.getElementById('sub');
const cv = document.getElementById('wave');
const ctx = cv.getContext('2d');
const listEl = document.getElementById('list');
let segs = [];
let cur = 0;
let dirty = false;

const OPTS = [0, 0.05, 0.08, 0.12, 0.18, 0.25, 0.45, 0.70];

function build() {
  segs = [];
  S.sentences.forEach(r => {
    if (!r.keep) return;
    const pre = Math.min(r.pause, r.avail);
    segs.push({
      id: r.id,
      ss: Math.max(0, r.start - pre),
      se: Math.min(S.duration, r.end + 0.10),
      text: r.text,
      row: r
    });
  });
  segs.forEach((s, i) => {
    if (i > 0 && s.ss < segs[i - 1].se) s.ss = segs[i - 1].se;
  });
  if (cur > segs.length - 1) cur = Math.max(0, segs.length - 1);
}

function total() {
  return segs.reduce((a, s) => a + (s.se - s.ss), 0);
}

function renderList() {
  listEl.innerHTML = '';
  S.sentences.forEach(r => {
    const d = document.createElement('div');
    d.className = 'row' + (r.keep ? '' : ' cut');
    d.dataset.id = r.id;
    d.innerHTML =
      '<input type="checkbox" ' + (r.keep ? 'checked' : '') + '>' +
      '<div><div class="id">' + r.id + '</div>' +
        '<div class="meta"><b>' + r.start.toFixed(2) + '</b>–' + r.end.toFixed(2) +
        '<br>' + (r.end - r.start).toFixed(2) + 's</div></div>' +
      '<div><input class="txt" value="' + r.text.replace(/"/g, '&quot;') + '">' +
        (r.tag ? '<span class="tag">' + r.tag + '</span>' : '') + '</div>' +
      '<select class="pause">' + (OPTS.includes(r.pause) ? OPTS : OPTS.concat([r.pause]).sort((x, y) => x - y)).map(o =>
        '<option value="' + o + '"' + (Math.abs(o - r.pause) < 0.001 ? ' selected' : '') +
        '>' + (o === 0 ? 'liền' : '+' + o.toFixed(2) + 's') + '</option>').join('') +
      '</select>' +
      '<button class="go" title="phát từ câu này">▶</button>';

    const cb = d.querySelector('input[type=checkbox]');
    cb.onchange = () => {
      r.keep = cb.checked;
      d.classList.toggle('cut', !r.keep);
      refresh();
    };
    const tx = d.querySelector('.txt');
    tx.oninput = () => { r.text = tx.value; refresh(); };
    const ps = d.querySelector('.pause');
    ps.onchange = () => { r.pause = parseFloat(ps.value); refresh(); };
    d.querySelector('.go').onclick = () => {
      build();
      const i = segs.findIndex(s => s.id === r.id);
      if (i >= 0) { cur = i; v.currentTime = segs[i].ss; v.play(); }
    };
    listEl.appendChild(d);
  });
}

function refresh(noSave) {
  build();
  const t = total();
  document.getElementById('total').textContent = t.toFixed(2) + 's';
  const n = segs.length;
  document.getElementById('cnt').textContent = n + '/' + S.sentences.length + ' câu giữ';
  document.getElementById('vs').textContent =
    '· gốc ' + S.duration.toFixed(2) + 's · −' + (100 * (1 - t / S.duration)).toFixed(1) + '%';
  draw();
  if (!noSave) { markSaved(false); saveSoon(); }
}

function markSaved(ok) {
  dirty = !ok;
  const el = document.getElementById('saved');
  el.textContent = ok ? 'đã lưu' : 'chưa lưu';
  el.style.color = ok ? 'var(--ok)' : 'var(--dim)';
  el.classList.add('show');
}

let timer = null;
function saveSoon() {
  clearTimeout(timer);
  timer = setTimeout(save, 500);
}

async function save() {
  const body = JSON.stringify({
    version: 1,
    video: S.video,
    duration: S.duration,
    sentences: S.sentences.map(r => ({
      id: r.id, keep: r.keep, pause: r.pause, text: r.text,
      start: r.start, end: r.end, avail: r.avail, tag: r.tag
    })),
    total: total()
  });
  try {
    const r = await fetch('/save', {method: 'POST', body});
    markSaved(r.ok);
  } catch (e) { markSaved(false); }
}

function draw() {
  const W = cv.width, H = cv.height;
  ctx.clearRect(0, 0, W, H);
  const N = S.peaks.length || 1;
  const per = S.duration / N;
  // nen: doan bi cat
  ctx.fillStyle = 'rgba(255,92,122,.13)';
  ctx.fillRect(0, 0, W, H);
  // vung giu lai
  ctx.fillStyle = 'rgba(61,220,151,.10)';
  segs.forEach(s => ctx.fillRect(s.ss / S.duration * W, 0,
    (s.se - s.ss) / S.duration * W, H));
  // song am
  ctx.fillStyle = '#7f8aa3';
  S.peaks.forEach((p, i) => {
    const h = Math.max(1, p * (H - 8));
    ctx.fillRect(i / N * W, (H - h) / 2, Math.max(1, W / N - 0.5), h);
  });
  // vien cac mien giu lai
  ctx.strokeStyle = 'rgba(61,220,151,.55)';
  ctx.lineWidth = 1;
  segs.forEach(s => {
    const x1 = s.ss / S.duration * W, x2 = s.se / S.duration * W;
    ctx.strokeRect(x1 + .5, .5, Math.max(1, x2 - x1 - 1), H - 1);
  });
  // playhead
  if (v.currentTime) {
    const x = v.currentTime / S.duration * W;
    ctx.fillStyle = '#fff';
    ctx.fillRect(x - 1, 0, 2, H);
  }
}

function paintSub() {
  const s = segs[cur];
  subEl.textContent = s ? s.text : '';
}

function step() {
  const s = segs[cur];
  if (!s) return;
  if (v.currentTime >= s.se - 0.03) {
    if (cur + 1 < segs.length) {
      cur += 1;
      v.currentTime = segs[cur].ss;
      paintSub();
      highlight();
    } else {
      v.pause();
      return;
    }
  }
  if (!v.paused) requestAnimationFrame(step);
  draw();
  document.getElementById('pos').textContent =
    outTime().toFixed(2) + ' / ' + total().toFixed(2) + 's';
}

function outTime() {
  let t = 0;
  for (let i = 0; i < cur && i < segs.length; i++) t += segs[i].se - segs[i].ss;
  const s = segs[cur];
  if (s) t += Math.max(0, Math.min(v.currentTime - s.ss, s.se - s.ss));
  return t;
}

function highlight() {
  document.querySelectorAll('.row').forEach(r => {
    r.classList.toggle('cur', segs[cur] && r.dataset.id === segs[cur].id);
  });
}

document.getElementById('play').onclick = () => {
  if (v.paused) { v.play(); requestAnimationFrame(step); }
  else v.pause();
};
document.getElementById('restart').onclick = () => {
  build(); cur = 0;
  if (segs.length) { v.currentTime = segs[0].ss; paintSub(); highlight(); }
  v.play(); requestAnimationFrame(step);
};
document.getElementById('cc').onclick = e => {
  subEl.classList.toggle('off');
  e.target.classList.toggle('on');
};
document.getElementById('save').onclick = save;
v.onpause = () => document.getElementById('play').textContent = '▶ Phát';
v.onplay = () => { document.getElementById('play').textContent = '⏸ Dừng'; requestAnimationFrame(step); };

v.addEventListener('timeupdate', () => {
  const s = segs[cur];
  if (s && v.currentTime >= s.se - 0.03 && !v.paused) step();
  draw();
  paintSub();
});

cv.onclick = e => {
  const r = cv.getBoundingClientRect();
  const t = (e.clientX - r.left) / r.width * S.duration;
  const i = segs.findIndex(s => t >= s.ss && t <= s.se);
  if (i >= 0) { cur = i; v.currentTime = t; }
  else {
    const j = segs.findIndex(s => s.ss > t);
    if (j >= 0) { cur = j; v.currentTime = segs[j].ss; }
  }
  highlight(); paintSub();
};

document.addEventListener('keydown', e => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
  if (e.code === 'Space') { e.preventDefault(); document.getElementById('play').click(); }
  if (e.key === 'ArrowRight') v.currentTime = Math.min(S.duration, v.currentTime + 1);
  if (e.key === 'ArrowLeft') v.currentTime = Math.max(0, v.currentTime - 1);
  if (e.key === 'x' || e.key === 'X') {
    const s = segs[cur];
    if (!s) return;
    s.row.keep = !s.row.keep;
    const row = document.querySelector('.row[data-id="' + s.id + '"]');
    if (row) { row.classList.toggle('cut', !s.row.keep); row.querySelector('input').checked = s.row.keep; }
    refresh();
  }
});

build();
document.getElementById('src').textContent = S.video.split(/[\\/]/).pop();
renderList();
refresh(true);
markSaved(true);
</script></body></html>"""


# ---------------------------------------------------------------- server
class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):  # im lang
        pass

    def _send(self, code: int, ctype: str, body: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            html = PAGE.replace("__STATE__", json.dumps(STATE, ensure_ascii=False))
            self._send(200, "text/html; charset=utf-8", html.encode("utf-8"))
            return
        if path == "/video":
            self._stream(VIDEO_PATH)
            return
        if path == "/state":
            self._send(200, "application/json; charset=utf-8",
                       json.dumps(STATE, ensure_ascii=False).encode("utf-8"))
            return
        self._send(404, "text/plain", b"not found")

    def _stream(self, p: Path) -> None:
        size = p.stat().st_size
        ctype = mimetypes.guess_type(str(p))[0] or "video/mp4"
        rng = self.headers.get("Range")
        start, end = 0, size - 1
        if rng:
            m = re.match(r"bytes=(\d+)-(\d*)", rng)
            if m:
                start = int(m.group(1))
                end = int(m.group(2)) if m.group(2) else size - 1
                end = min(end, size - 1)
        length = end - start + 1
        self.send_response(206 if rng else 200)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(length))
        if rng:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        with p.open("rb") as f:
            f.seek(start)
            left = length
            while left > 0:
                chunk = f.read(min(1 << 16, left))
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    return
                left -= len(chunk)

    def do_POST(self) -> None:  # noqa: N802
        if urlparse(self.path).path != "/save":
            self._send(404, "text/plain", b"not found")
            return
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n)
        try:
            data = json.loads(body.decode("utf-8"))
            OUT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=1),
                                encoding="utf-8")
            # dong bo lai state trong bo nho de reload khong mat chinh sua
            by_id = {r["id"]: r for r in STATE["sentences"]}
            for r in data.get("sentences", []):
                if r["id"] in by_id:
                    by_id[r["id"]].update({k: r[k] for k in
                                           ("keep", "pause", "text")})
            self._send(200, "application/json", b'{"ok":true}')
        except Exception as exc:  # noqa: BLE001
            self._send(400, "application/json",
                       json.dumps({"ok": False, "error": str(exc)}).encode())


def main() -> None:
    global STATE, OUT_PATH, VIDEO_PATH
    ap = argparse.ArgumentParser()
    ap.add_argument("--rough", required=True)
    ap.add_argument("--edl", default="")
    ap.add_argument("--out", default="output/review.json")
    ap.add_argument("--port", type=int, default=8799)
    ap.add_argument("--state-only", action="store_true")
    a = ap.parse_args()

    OUT_PATH = Path(a.out)
    edl = Path(a.edl) if a.edl else None
    STATE = build_state(Path(a.rough), edl)
    VIDEO_PATH = Path(STATE["video"])
    if OUT_PATH.exists():
        old = json.loads(OUT_PATH.read_text(encoding="utf-8"))
        by_id = {r["id"]: r for r in STATE["sentences"]}
        for r in old.get("sentences", []):
            if r["id"] in by_id:
                by_id[r["id"]].update({k: r[k] for k in
                                       ("keep", "pause", "text") if k in r})

    if a.state_only:
        print(json.dumps({k: v for k, v in STATE.items() if k != "peaks"},
                         ensure_ascii=False, indent=1))
        return

    srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    srv.daemon_threads = True
    print(f"ready http://127.0.0.1:{a.port}/  ({VIDEO_PATH.name}, "
          f"{len(STATE['sentences'])} cau)", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
