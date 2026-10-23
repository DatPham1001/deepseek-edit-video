#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Rough-cut helper: island-wise ASR -> bang cau -> bang lang -> bang noi lai.

Khong render, khong dung raw/. Chi doc file va xuat JSON + bang markdown.

    python tools/roughcut.py build raw\\clip.mp4 --out output\\clip
    python tools/roughcut.py table output\\clip.rough.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

# Windows console may default to cp1252; Vietnamese text and arrows crash print().
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

FILLERS = {
    "u", "a", "o", "uh", "um", "uhm", "huh", "ah", "oh", "e", "hmm",
    "ừ", "à", "ờ", "ơ", "ạ", "ừm", "hừ", "ừa", "à ơi",
}
# tu ket thuc cau = cau chua tron y
TAIL_BAD = {
    "và", "nhưng", "mà", "là", "thì", "rồi", "nên", "để", "của", "với",
    "cho", "nếu", "bởi", "vì", "hoặc", "cũng", "đang", "sẽ", "có", "không",
    "trong", "ở", "tại", "khi", "thế", "vậy", "ạ",
}
PUNCT_END = ".?!…"
PUNCT_SOFT = ",;:"


# ---------------------------------------------------------------- co ban
def sh(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def probe_duration(path: str) -> float:
    r = sh(["ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=nw=1:nk=1", path])
    return round(float((r.stdout or "0").strip() or 0), 3)


def detect_silences(path: str, db: float, min_len: float) -> list[dict]:
    r = sh(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af",
            f"silencedetect=noise={db}dB:d={min_len}", "-f", "null", "-"])
    log = (r.stderr or "") + (r.stdout or "")
    starts = [float(m) for m in re.findall(r"silence_start: ([\d.]+)", log)]
    ends = [float(m) for m in re.findall(r"silence_end: ([\d.]+)", log)]
    out = []
    for i, s in enumerate(starts):
        e = ends[i] if i < len(ends) else None
        if e is None:
            continue
        out.append({"start": round(s, 3), "end": round(e, 3),
                    "duration": round(e - s, 3)})
    return merge_silences(out)


def merge_silences(sils: list[dict], gap: float = 0.15) -> list[dict]:
    """silencedetect hay tach mot khoang lang thanh hai vi mot tieng tick."""
    merged: list[dict] = []
    for s in sils:
        if merged and s["start"] - merged[-1]["end"] < gap:
            merged[-1]["end"] = s["end"]
            merged[-1]["duration"] = round(merged[-1]["end"] - merged[-1]["start"], 3)
        else:
            merged.append(dict(s))
    return merged


def build_islands(dur: float, silences: list[dict], split: float,
                  min_island: float = 0.22) -> list[dict]:
    """Vung co tieng = phan bu cua silence; gap >= split thi tach dao rieng."""
    speech: list[list[float]] = []
    cur = 0.0
    for s in silences:
        a, b = s["start"], s["end"]
        if a - cur > 0.001:
            speech.append([cur, a])
        cur = max(cur, b)
    if dur - cur > 0.001:
        speech.append([cur, dur])

    merged: list[list[float]] = []
    for sp in speech:
        if merged and sp[0] - merged[-1][1] < split:
            merged[-1][1] = sp[1]
        else:
            merged.append(list(sp))
    return [{"i": i + 1, "start": round(a, 3), "end": round(b, 3),
             "duration": round(b - a, 3)}
            for i, (a, b) in enumerate(x for x in merged
                                       if x[1] - x[0] >= min_island)]


def extract_wav(path: str, start: float, end: float, out: Path) -> Path:
    r = sh(["ffmpeg", "-y", "-v", "error", "-ss", f"{start:.3f}",
            "-to", f"{end:.3f}", "-i", path, "-vn", "-ac", "1", "-ar", "16000",
            str(out)])
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg extract failed: {r.stderr[-400:]}")
    return out


def load_audio(path: Path, sr: int = 16000):
    """Decode qua ffmpeg ra mang float32 — khong dung PyAV (API hay doi)."""
    import numpy as np  # noqa: PLC0415

    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-v", "error", "-i", str(path),
         "-vn", "-f", "f32le", "-acodec", "pcm_f32le", "-ac", "1",
         "-ar", str(sr), "pipe:1"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise RuntimeError("ffmpeg decode failed: "
                           + proc.stderr.decode("utf-8", "replace")[-600:])
    audio = np.frombuffer(proc.stdout, dtype=np.float32)
    if audio.size == 0:
        raise RuntimeError("decoded audio is empty")
    return audio


# ---------------------------------------------------------------- asr
def transcribe_islands(video: str, islands: list[dict], model_name: str,
                       lang: str, work: Path) -> list[dict]:
    if not os.environ.get("HF_HOME"):
        for hf in (Path.home() / ".dsh/tools/hf",
                   Path.home() / ".cache/huggingface"):
            if hf.exists():
                os.environ["HF_HOME"] = str(hf)
                break
    from faster_whisper import WhisperModel  # noqa: PLC0415

    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    tmp = work / "_islands"
    tmp.mkdir(parents=True, exist_ok=True)
    result = []
    for isl in islands:
        wav = tmp / f"i{isl['i']:02d}.wav"
        a = max(0.0, isl["start"] - 0.06)
        b = min(probe_duration(video), isl["end"] + 0.18)
        extract_wav(video, a, b, wav)
        audio = load_audio(wav)
        segs, _info = model.transcribe(
            audio, language=lang, word_timestamps=True, vad_filter=False,
            beam_size=5, condition_on_previous_text=False)
        words = []
        for seg in segs:
            for w in (getattr(seg, "words", None) or []):
                words.append({
                    "start": round(a + float(w.start), 3),
                    "end": round(a + float(w.end), 3),
                    "word": (w.word or "").strip(),
                })
        isl = dict(isl)
        isl["words"] = words
        isl["text"] = " ".join(w["word"] for w in words).strip()
        result.append(isl)
        print(f"  island {isl['i']:>2}  {isl['start']:7.2f}-{isl['end']:7.2f}"
              f"  {len(words):>3} tu  {isl['text'][:60]}", flush=True)
    return result


# ---------------------------------------------------------------- cau
def norm_tokens(text: str) -> list[str]:
    t = unicodedata.normalize("NFC", text.lower())
    t = re.sub(r"[^\w\s]", " ", t, flags=re.UNICODE)
    return [x for x in t.split() if x and x not in FILLERS]


def split_sentences(isl: dict) -> list[dict]:
    out, cur = [], []
    gap_break = 0.45
    for idx, w in enumerate(isl["words"]):
        cur.append(w)
        raw = w["word"]
        hard = raw.rstrip().endswith(tuple(PUNCT_END))
        nxt = isl["words"][idx + 1] if idx + 1 < len(isl["words"]) else None
        gap = (nxt["start"] - w["end"]) if nxt else 99.0
        soft = raw.rstrip().endswith(tuple(PUNCT_SOFT)) and gap >= 0.30
        if hard or gap >= gap_break or soft:
            out.append(list(cur))
            cur = []
    if cur:
        out.append(list(cur))
    sents = []
    for words in out:
        if not words:
            continue
        text = " ".join(w["word"] for w in words).strip()
        if not norm_tokens(text):
            continue
        sents.append({
            "start": round(words[0]["start"], 3),
            "end": round(words[-1]["end"], 3),
            "text": text,
            "words": words,
        })
    return sents


def lcs_pair(a: list[str], b: list[str]) -> tuple[int, int]:
    """(LCS length, longest contiguous run) giua a va b."""
    m = len(b)
    prev = [0] * (m + 1)
    run_best = 0
    for x in a:
        cur = [0] * (m + 1)
        for j, y in enumerate(b, 1):
            if x == y:
                cur[j] = prev[j - 1] + 1
                if cur[j] > run_best:
                    run_best = cur[j]
            else:
                cur[j] = max(prev[j], cur[j - 1])
        prev = cur
    return prev[m], run_best


def is_complete(tokens: list[str]) -> bool:
    return bool(tokens) and tokens[-1] not in TAIL_BAD


def find_retakes(sents: list[dict], window: float = 20.0, cover: float = 0.80,
                 min_tokens: int = 4) -> list[dict]:
    """Cau nao la take cu cua mot cau sau trong cung cua so thoi gian.

    `strong` = du ca 3 dieu kien (phu >= cover, >= min_tokens, ban sau du y).
    Manh hon nguong thap -> van tra ve nhung de nguoi doc quyet.
    """
    pairs = []
    taken = set()
    for i in range(1, len(sents)):
        b = sents[i]
        tb = norm_tokens(b["text"])
        if not tb or i in taken:
            continue
        hits = []
        for j in range(i - 1, -1, -1):
            a = sents[j]
            if b["start"] - a["end"] > window:
                break
            if j in taken:
                continue
            ta = norm_tokens(a["text"])
            if len(ta) < min_tokens:
                continue
            lcs, run = lcs_pair(ta, tb)
            ratio = lcs / len(ta)
            if lcs < min_tokens or ratio < 0.60:
                continue
            hits.append({
                "a": j, "b": i, "lcs": lcs, "run": run,
                "cover": round(ratio, 3),
                "complete": is_complete(tb) and len(tb) >= len(ta) - 1,
                "space": round(b["start"] - a["end"], 2),
                "strong": ratio >= cover and is_complete(tb)
                          and len(tb) >= len(ta) - 1,
            })
        if not hits:
            continue
        strong = [h for h in hits if h["strong"]]
        if strong:
            pair = min(strong, key=lambda p: p["a"])
            pair["bo"] = list(range(pair["a"], i))   # moi take bi bo
            pairs.append(pair)
            taken.update(pair["bo"])
        for h in hits:
            if not h["strong"]:
                pairs.append(h)
    return pairs


def classify_silences(sents: list[dict], sils: list[dict], dur: float,
                      lead: float = 0.12, trail: float = 0.10) -> list[dict]:
    """Gan moi khoang lang mot vai tro: giua 2 cau / trong 1 cau / dau / cuoi.

    `lead` = giu lai bao nhieu giay tieng truoc khi cat, `trail` = giu lai
    bao nhieu giay truoc cau sau. Nho -> noi lien mach.
    """
    out = []
    for s in sils:
        inside = None
        for x in sents:
            if x["start"] - 0.25 <= s["start"] and s["end"] <= x["end"] + 0.25:
                inside = x
                break
        if s["start"] <= 0.06:
            role, ref = "dau", None
        elif s["end"] >= dur - 0.25:
            role, ref = "cuoi", None
        elif inside is not None:
            role, ref = "trong", inside
        else:
            prev = max((x for x in sents if x["end"] <= s["start"] + 0.25),
                       key=lambda x: x["end"], default=None)
            nxt = min((x for x in sents if x["start"] >= s["end"] - 0.25),
                      key=lambda x: x["start"], default=None)
            role, ref = "giua", (prev, nxt) if prev and nxt else None
            if ref is None:
                role = "giua"
        d = s["duration"]
        if role == "dau":
            lead_, trail_, on = 0.0, 0.10, True
        elif role == "cuoi":
            lead_, trail_, on = 0.10, 0.0, True
        elif role == "giua":
            lead_, trail_, on = lead, trail, d >= 0.40
        else:  # trong cau: giu hoi tho, chi tia khi qua dai
            lead_, trail_, on = 0.28, 0.27, d >= 1.20
        a = round(s["start"] + lead_, 3)
        b = round(s["end"] - trail_, 3)
        if role == "dau":
            a = 0.0
            nxt = min((x for x in sents if x["start"] >= s["end"] - 0.10),
                      key=lambda x: x["start"], default=None)
            if nxt:
                b = round(min(b, nxt["start"] - 0.08), 3)
        if role == "cuoi":
            b = round(dur, 3)
            prev = max((x for x in sents if x["end"] <= s["start"] + 0.10),
                       key=lambda x: x["end"], default=None)
            if prev:
                a = round(max(a, prev["end"] + 0.08), 3)
        kept = max(0.0, min(a, s["end"]) - s["start"]) + \
            max(0.0, s["end"] - max(b, s["start"]))
        out.append({
            **s, "role": role, "ref": ref,
            "cut_from": a, "cut_to": b,
            "kept": round(kept, 2),
            "default_cut": on and (b - a) > 0.12,
        })
    return out


# ---------------------------------------------------------------- manh vu
OPENER_HARD = {"theo", "của", "với", "cho", "để", "về", "từ", "tại", "ở",
               "bởi", "vì", "bằng", "qua", "do", "tới"}
OPENER_SOFT = {"và", "nhưng", "mà", "nếu", "khi", "thì", "nên", "rồi",
               "hoặc", "còn", "bây", "giờ", "thế", "vậy", "sau", "tiếp",
               "cũng", "vâng", "ừ", "à", "ok", "ơ"}

# Tu dung de so trung giua hai cau lien tiep: bo tu noi, giu tu mang nghia.
STOP_OVERLAP = {
    "là", "của", "và", "mà", "thì", "cho", "với", "để", "có", "không",
    "một", "cái", "ấy", "vậy", "thế", "này", "đó", "khi", "nếu", "nhưng",
    "rồi", "nên", "ở", "ra", "vào", "tôi", "mình", "ta", "nó", "họ",
    "em", "anh", "chị", "ông", "bà", "ạ", "nhé", "à", "ừ", "đâu", "chả",
}
# Coi nhu co vi ngu / vi tu -> khong phai cau lac long.
CLAUSE_HINTS = {
    "là", "có", "không", "được", "phải", "sẽ", "đang", "đã", "muốn",
    "thấy", "nói", "làm", "đi", "đến", "về", "nghĩ", "biết", "hiểu",
    "cần", "nên", "bị", "cho", "nhìn", "coi", "gọi", "sống", "chết",
    "yêu", "thích", "ở", "ra", "vào", "lên", "xuống", "ăn", "uống",
    "ngủ", "đứng", "ngồi", "chạy", "cầm", "giữ", "bỏ", "cắt", "xem",
    "nghe", "hỏi", "trả", "lời", "chửi", "khen", "sợ", "lo", "tin",
    "mong", "chờ", "cảm", "chào", "hay", "đẹp", "tốt", "xấu",
    "đúng", "sai", "vui", "buồn", "khổ", "sướng", "giỏi", "dở", "nhanh",
    "chậm", "đông", "vắng", "đắt", "rẻ", "khó", "dễ", "quan", "trọng",
}
# Cau dap ngan, dung mot minh van du nghia -> khong cat.
RESPONSE_OPENERS = {
    "vâng", "dạ", "ừ", "à", "ok", "đúng", "được", "phải", "không", "có",
    "chứ", "thế", "vậy", "đấy", "nhỉ", "nhé", "ạ",
}


def _content_tokens(text: str) -> set[str]:
    return {t for t in norm_tokens(text) if t not in STOP_OVERLAP}


def find_fragments(sents: list[dict], sils: list[dict],
                   min_score: int = 4) -> list[dict]:
    """Cau khong co dau khong co cuoi: manh vu = noi vap, cat duoc.

    Cham diem theo tin hieu yeu (mo dau bang tu can bo ngu, qua ngan, qua
    ninh, dung sau lang dai) va tin hieu manh (cau tron y -> tru diem).

    Them luat "cau lac long": ngan, bi lang >= 0.8s o ca hai ben, khong
    trung tu mang nghia voi cau truoc lan cau sau, va khong co vi ngu/vi
    tu. Kieu cau nay khong du ngu canh de dung mot minh, cung khong ghep
    duoc vao cau nao -> cat.

    Them luat "cau mo do": cau ngan, mo dau bang dung 2 tu dau cua cau
    sau roi cau sau noi lai tu dau. Day la take dở, khong phai y rieng.
    """
    out = []
    for i, s in enumerate(sents):
        toks = norm_tokens(s["text"])
        if not toks:
            continue
        score, why = 0, []
        kind = "fragment"
        if toks[0] in OPENER_HARD:
            score += 2
            why.append(f"mở bằng '{toks[0]}'")
        elif toks[0] in OPENER_SOFT:
            score += 1
            why.append(f"mở bằng '{toks[0]}'")
        if len(toks) <= 3:
            score += 1
            why.append(f"{len(toks)} từ")
        d = s["end"] - s["start"]
        if d <= 1.20:
            score += 1
            why.append(f"{d:.2f}s")
        gap = next((x["duration"] for x in sils
                    if abs(x["end"] - s["start"]) <= 0.35), None)
        gap_next = next((x["duration"] for x in sils
                         if abs(x["start"] - s["end"]) <= 0.35), None)
        if gap is None:
            score -= 1
            why.append("nối liền câu trước")
        elif gap >= 1.0:
            score += 1
            why.append(f"sau lặng {gap:.1f}s")
        if s["text"].rstrip().endswith(tuple(PUNCT_END)) and len(toks) >= 6:
            score -= 2
            why.append("câu trọn")

        # --- cau mo do: nhac lai 2 tu dau cua cau sau roi noi lai
        next_toks = (norm_tokens(sents[i + 1]["text"])
                     if i + 1 < len(sents) else [])
        lead_in = (d <= 1.20 and len(toks) <= 6
                   and len(next_toks) >= len(toks)
                   and toks[:2] == next_toks[:2])
        if lead_in:
            score += 3
            kind = "lead_in"
            why.append(
                f"câu mở dở: nhắc lại '{' '.join(toks[:2])}' của câu sau")

        # --- cau lac long: khong du ngu canh, khong ghep duoc vao dau
        prev_c = _content_tokens(sents[i - 1]["text"]) if i > 0 else set()
        next_c = (_content_tokens(sents[i + 1]["text"])
                  if i + 1 < len(sents) else set())
        mine = _content_tokens(s["text"])
        isolated = ((i == 0 or (gap or 0.0) >= 0.8)
                    and (i + 1 == len(sents) or (gap_next or 0.0) >= 0.8))
        no_link = not (mine & prev_c) and not (mine & next_c)
        no_pred = not any(t in CLAUSE_HINTS for t in toks)
        short = len(toks) <= 5 and d <= 1.50
        if (short and isolated and no_link and no_pred
                and toks[0] not in RESPONSE_OPENERS and kind != "lead_in"):
            score += 4
            kind = "orphan"
            why.append(
                f"câu lạc lõng: {len(toks)} từ, lặng "
                f"{(gap or 0.0):.1f}s/{(gap_next or 0.0):.1f}s, "
                f"không nối được câu trước/sau")

        if score >= min_score:
            out.append({"i": i, "score": score, "why": why, "kind": kind})
    return out


# ---------------------------------------------------------------- bang
def fmt(t: float) -> str:
    return f"{t:.2f}"


def _sid(sents: list[dict], target: dict) -> int:
    for i, x in enumerate(sents):
        if x is target:
            return i + 1
    return 0


def _merge(cuts: list[tuple[float, float]]) -> list[list[float]]:
    out: list[list[float]] = []
    for a, b in sorted((a, b) for a, b in cuts if b - a > 0.02):
        if out and a <= out[-1][1] + 1e-6:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out


def _drop_runs(sents: list[dict], dropped: set[int],
               dur: float) -> list[tuple[float, float, str]]:
    """Gom cac cau bi bo lien tiep thanh mot khoang cat."""
    runs: list[list[int]] = []
    run: list[int] = []
    for i in range(len(sents)):
        if i in dropped:
            run.append(i)
        elif run:
            runs.append(run)
            run = []
    if run:
        runs.append(run)
    out = []
    for r in runs:
        first, last = r[0], r[-1]
        start = 0.0 if first == 0 else round(sents[first]["start"] - 0.05, 3)
        nxt = sents[last + 1]["start"] if last + 1 < len(sents) else dur
        out.append((start, round(nxt - 0.10, 3),
                    "noi lai: bo " + ", ".join(f"S{x + 1}" for x in r)))
    return out


def build_tables(data: dict) -> str:
    sents = data["sentences"]
    dur = data["duration"]
    params = data.get("params", {})
    pairs = find_retakes(sents, params.get("window", 20.0),
                         params.get("cover", 0.80), params.get("min_tokens", 4))
    sils = classify_silences(sents, merge_silences(data["silences"]), dur)
    L = []

    # ---- 1. transcript
    L.append("# 1. Transcript co giay\n")
    L.append(f"`{data['video']}` — {dur:.2f}s, {len(sents)} cau, "
             f"{sum(s['end'] - s['start'] for s in sents):.2f}s co tieng\n")
    L.append("| # | tu giay | den giay | dai (s) | loi thoai |")
    L.append("|---|---------|----------|---------|-----------|")
    for k, s in enumerate(sents, 1):
        txt = s["text"].replace("|", "\\|")
        L.append(f"| S{k} | {fmt(s['start'])} | {fmt(s['end'])} | "
                 f"{s['end'] - s['start']:.2f} | {txt} |")

    # ---- 2. silence
    L.append("\n# 2. Khoang khong noi gi\n")
    L.append("| # | tu | den | dai | vi tri | cat tu | den | con giu | mac dinh |")
    L.append("|---|----|-----|-----|--------|--------|-----|---------|----------|")
    n = 0
    cuts: list[tuple[float, float]] = []
    for s in sils:
        if s["duration"] < 0.50:
            continue
        n += 1
        r = s["role"]
        if r == "giua" and s["ref"]:
            prev, nxt = s["ref"]
            pos = f"giua S{_sid(sents, prev)}–S{_sid(sents, nxt)}"
        elif r == "giua":
            pos = "giua 2 cau"
        elif r == "trong":
            pos = f"trong S{_sid(sents, s['ref'])}"
        else:
            pos = "dau clip" if r == "dau" else "cuoi clip"
        on = s["default_cut"]
        if on:
            cuts.append((s["cut_from"], s["cut_to"]))
            cf, ct, kp = fmt(s["cut_from"]), fmt(s["cut_to"]), f"{s['kept']:.2f}"
        else:
            cf, ct, kp = "—", "—", f"{s['duration']:.2f}"
        L.append(f"| L{n} | {fmt(s['start'])} | {fmt(s['end'])} | "
                 f"{s['duration']:.2f} | {pos} | {cf} | {ct} | {kp} | "
                 f"{'**CAT**' if on else 'giu'} |")

    # ---- 3. retakes
    L.append("\n# 3. Noi lai — take truoc bi bo\n")
    ok = [p for p in pairs if p.get("strong")]
    maybe = [p for p in pairs if not p.get("strong")]
    if ok:
        L.append("| # | bo (giay) | giu (giay) | phu | cum trung | cau bi bo | cat tu | den |")
        L.append("|---|-----------|------------|-----|-----------|-----------|--------|-----|")
        for k, p in enumerate(ok, 1):
            a, b = sents[p["a"]], sents[p["b"]]
            bo = ", ".join(f"S{x + 1}" for x in p["bo"])
            cf, ct = round(max(0.0, a["start"] - 0.04), 3), round(b["start"] - 0.04, 3)
            cuts.append((cf, ct))
            L.append(f"| R{k} | {fmt(a['start'])}–{fmt(a['end'])} | "
                     f"{fmt(b['start'])}–{fmt(b['end'])} | {p['cover'] * 100:.0f}% | "
                     f"{p['lcs']} tu (run {p['run']}) | {bo} | {fmt(cf)} | {fmt(ct)} |")
    else:
        L.append("(khong co cap nao du dieu kien)")
    if maybe:
        L.append("\n**Gan dat — ban quyet** (trung nhung chua du ca 3 dieu kien):\n")
        for p in maybe:
            a, b = sents[p["a"]], sents[p["b"]]
            why = []
            if p["cover"] < 0.80:
                why.append(f"phu {p['cover'] * 100:.0f}%")
            if not p["complete"]:
                why.append("ban sau khong du y")
            cf, ct = round(max(0.0, a["start"] - 0.04), 3), round(b["start"] - 0.04, 3)
            L.append(f"- S{p['a'] + 1} `{fmt(a['start'])}–{fmt(a['end'])}` "
                     f"\"{a['text']}\"\n"
                     f"  → S{p['b'] + 1} `{fmt(b['start'])}–{fmt(b['end'])}` "
                     f"\"{b['text']}\"\n"
                     f"  trung {p['lcs']} tu (run {p['run']}), {', '.join(why)}"
                     f" · neu cat: `{fmt(cf)}–{fmt(ct)}`")

    # ---- 4. fragment de xuat
    removed = set()
    for p in pairs:
        removed.update(p.get("bo") or [p["a"]])
    frag = [f for f in find_fragments(sents, sils) if f["i"] not in removed]
    L.append("\n# 4. Manh vu / cau lac long / cau mo do — khong du ngu canh (cat luon)\n")
    if frag:
        L.append("| # | cau | tu | den | dai | diem | vi sao | noi dung |")
        L.append("|---|-----|----|-----|-----|------|--------|----------|")
        for k, f in enumerate(frag, 1):
            s = sents[f["i"]]
            L.append(f"| X{k} | S{f['i'] + 1} | {fmt(s['start'])} | {fmt(s['end'])} | "
                     f"{s['end'] - s['start']:.2f} | {f['score']} | "
                     f"{', '.join(f['why'])} | {s['text'].replace('|', chr(92) + '|')} |")
    else:
        L.append("(khong co)")

    # ---- 5. ket qua du kien
    if frag:
        for a_, b_, _lab in _drop_runs(sents, {f["i"] for f in frag}, dur):
            cuts.append((a_, b_))
    merged = _merge(cuts)
    kept = dur - sum(b - a for a, b in merged)
    L.append(f"\n# 5. Du kien\n")
    L.append(f"- Cat {len(merged)} khoang, tong {dur - kept:.2f}s.")
    L.append(f"- {dur:.2f}s → **{kept:.2f}s** (−{100 * (dur - kept) / dur:.1f}%)")
    L.append(f"- Vat lieu: {sum(s['end'] - s['start'] for s in sents):.2f}s tieng noi "
             f"trong {dur:.2f}s goc (ca phan bi bo).")
    return "\n".join(L)


# ---------------------------------------------------------------- lem
def cmd_build(a) -> None:
    video = a.video
    work = Path(a.out).parent
    work.mkdir(parents=True, exist_ok=True)
    dur = probe_duration(video)
    print(f"duration {dur}s", flush=True)
    sils = detect_silences(video, a.db, a.min_sil)
    print(f"silences: {len(sils)}", flush=True)
    islands = build_islands(dur, sils, a.split)
    print(f"islands: {len(islands)}", flush=True)
    islands = transcribe_islands(video, islands, a.model, a.lang, work)

    sents = []
    for isl in islands:
        for s in split_sentences(isl):
            sents.append(s)
    sents.sort(key=lambda s: s["start"])
    for k, s in enumerate(sents, 1):
        s["id"] = f"S{k}"

    pairs = find_retakes(sents, a.window, a.cover, a.min_tokens)
    data = {
        "video": str(Path(video).resolve()),
        "duration": dur,
        "model": a.model,
        "silences": sils,
        "islands": islands,
        "sentences": sents,
        "retakes": pairs,
        "params": {"window": a.window, "cover": a.cover,
                   "min_tokens": a.min_tokens},
    }
    outp = Path(a.out)
    outp.write_text(json.dumps(data, ensure_ascii=False, indent=1),
                    encoding="utf-8")
    md = build_tables(data)
    stem = outp.name.split(".")[0]
    (outp.parent / f"{stem}.tables.md").write_text(md, encoding="utf-8")
    print(md)


def cmd_table(a) -> None:
    p = Path(a.json)
    data = json.loads(p.read_text(encoding="utf-8"))
    md = build_tables(data)
    stem = p.name.split(".")[0]
    (p.parent / f"{stem}.tables.md").write_text(md, encoding="utf-8")
    print(md)


def probe_fps(path: str) -> float:
    r = sh(["ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=r_frame_rate",
            "-of", "default=nw=1:nk=1", path])
    s = (r.stdout or "").strip()
    if "/" in s:
        n, d = s.split("/")
        return round(float(n) / float(d or 1), 4) if float(d or 1) else 30.0
    return float(s or 30.0)


def cmd_edl(a) -> None:
    data = json.loads(Path(a.json).read_text(encoding="utf-8"))
    sents = data["sentences"]
    dur = data["duration"]
    params = data.get("params", {})
    fps = a.fps or probe_fps(data["video"])
    step = 1.0 / fps
    sils = classify_silences(sents, merge_silences(data["silences"]), dur,
                             lead=a.lead, trail=a.trail)
    pairs = find_retakes(sents, params.get("window", 20.0),
                         params.get("cover", 0.80), params.get("min_tokens", 4))

    dropped = set()
    if a.drop:
        for tok in a.drop.replace(" ", ",").split(","):
            tok = tok.strip().upper().lstrip("S")
            if tok.isdigit():
                dropped.add(int(tok) - 1)
    if a.fragments == "cut":
        for f in find_fragments(sents, sils):
            dropped.add(f["i"])

    cuts: list[tuple[float, float, str]] = []
    if a.silence == "all":
        for s in sils:
            if s["default_cut"]:
                cuts.append((s["cut_from"], s["cut_to"],
                             f"lang {s['duration']:.2f}s ({s['role']})"))

    # gom cac cau bi bo lien tiep thanh 1 khoang
    cuts.extend(_drop_runs(sents, dropped, dur))

    merged = _merge([(a_, b_) for a_, b_, _ in cuts])
    labels = []
    for a_, b_ in merged:
        why = [lab for ca, cb, lab in cuts if not (cb <= a_ or ca >= b_)]
        labels.append(" + ".join(dict.fromkeys(why)))

    # snap ve frame: bat dau cat lam tron len, ket thuc cat lam tron xuong
    def snap_up(t: float) -> float:
        return round(min(dur, (int(t / step) + (0 if abs(t / step - round(t / step)) < 1e-9 else 1)) * step), 4)

    def snap_dn(t: float) -> float:
        return round(max(0.0, int(t / step + 1e-9) * step), 4)

    snapped = [(snap_up(a_), snap_dn(b_), lab) for a_, b_, lab in zip(
        [m[0] for m in merged], [m[1] for m in merged], labels)]
    snapped = [(a_, b_, lab) for a_, b_, lab in snapped if b_ - a_ > 0.05]

    # hai khoang cat sat nhau (con lai < 0.25s) -> gop, khong de manh vun
    gop: list[tuple[float, float, str]] = []
    for a_, b_, lab in snapped:
        if gop and a_ - gop[-1][1] < 0.25:
            prev = gop[-1]
            gop[-1] = (prev[0], max(prev[1], b_),
                       " + ".join(dict.fromkeys([prev[2], lab])))
        else:
            gop.append((a_, b_, lab))
    snapped = gop

    kept: list[list[float]] = []
    cur = 0.0
    for a_, b_, _ in snapped:
        if a_ - cur > 0.05:
            kept.append([round(cur, 4), round(a_, 4)])
        cur = max(cur, b_)
    if dur - cur > 0.05:
        kept.append([round(cur, 4), round(dur, 4)])

    total = round(sum(b_ - a_ for a_, b_ in kept), 3)
    edl = {
        "ok": True,
        "mode": "roughcut",
        "fps": fps,
        "source_total": round(dur, 3),
        "output_estimate": total,
        "compression_pct": round(100 * (1 - total / dur), 1),
        "sources": [{
            "path": data["video"],
            "duration": round(dur, 3),
            "segments": [{"start": a_, "end": b_, "duration": round(b_ - a_, 3)}
                         for a_, b_ in kept],
        }],
        "cuts": [{"start": a_, "end": b_, "reason": lab}
                 for a_, b_, lab in snapped],
    }
    Path(a.out).write_text(json.dumps(edl, ensure_ascii=False, indent=1),
                           encoding="utf-8")

    L = ["**Da cat**\n", "| # | cat tu | den | dai | ly do |",
         "|---|--------|-----|-----|-------|"]
    for k, (a_, b_, lab) in enumerate(snapped, 1):
        L.append(f"| {k} | {a_:.2f} | {b_:.2f} | {b_ - a_:.2f} | {lab} |")
    L += ["", "**EDL**\n", "| # | in | out | dai | nguon | ly do |",
          "|---|----|-----|-----|-------|-------|"]
    for k, (a_, b_) in enumerate(kept, 1):
        inside = [f"S{i + 1}" for i, s in enumerate(sents)
                  if s["start"] < b_ - 0.05 and s["end"] > a_ + 0.05]
        L.append(f"| {k} | {a_:.2f} | {b_:.2f} | {b_ - a_:.2f} | 1020.mp4 | "
                 f"{', '.join(inside) or '—'} |")
    L.append(f"\n{dur:.2f}s → **{total:.2f}s** "
             f"(−{100 * (1 - total / dur):.1f}%), {len(kept)} doan")
    print("\n".join(L))
    if a.md:
        Path(a.md).write_text("\n".join(L), encoding="utf-8")


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build")
    b.add_argument("video")
    b.add_argument("--out", required=True)
    b.add_argument("--model", default="medium")
    b.add_argument("--lang", default="vi")
    b.add_argument("--db", type=float, default=-35.0)
    b.add_argument("--min-sil", type=float, default=0.40)
    b.add_argument("--split", type=float, default=1.00)
    b.add_argument("--window", type=float, default=20.0)
    b.add_argument("--cover", type=float, default=0.80)
    b.add_argument("--min-tokens", type=int, default=4)
    b.set_defaults(func=cmd_build)

    t = sub.add_parser("table")
    t.add_argument("json")
    t.set_defaults(func=cmd_table)

    e = sub.add_parser("edl")
    e.add_argument("json")
    e.add_argument("--out", required=True)
    e.add_argument("--drop", default="")
    e.add_argument("--silence", default="all", choices=["all", "none"])
    e.add_argument("--fragments", default="cut", choices=["cut", "keep"])
    e.add_argument("--lead", type=float, default=0.12)
    e.add_argument("--trail", type=float, default=0.10)
    e.add_argument("--fps", type=float, default=0.0)
    e.add_argument("--md", default="")
    e.set_defaults(func=cmd_edl)

    a = p.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
