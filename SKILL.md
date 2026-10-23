---
name: edit-chinh-tri
description: Cắt thô video bình luận chính trị / phân tích thời sự nói một mình, có bước người dùng duyệt trên web. Transcribe từng đảo tiếng, in bảng transcript có số giây, bỏ khoảng lặng, bỏ take nói lại, bỏ câu vụn nói vấp, câu lạc lõng, câu mở dở, rồi mở web view để người dùng tự bật/tắt từng câu, chỉnh khoảng nghỉ và sửa phụ đề trên chính clip gốc trước khi xuất. Có nhánh asset-first: xếp video/ảnh người dùng vào đúng đoạn thoại trước, phần còn trống mới tìm evidence trên mạng (chụp bài báo vào folder evidence), rồi lên draft kịch bản trước khi dựng. Use when the user drops a talking-head political commentary / current-affairs clip and says "cắt clip này", "cắt thô", "bỏ đoạn lặng", "bỏ đoạn nói lại", "sửa phụ đề", "edit-chinh-tri", "tìm bằng chứng", "dẫn báo", or wants a review page to trim cuts and captions before rendering.
---

# Cắt thô bình luận chính trị

Luồng 3 nhịp. **Không render trước khi người dùng chốt.**

```
open  →  (người dùng chỉnh trên web)  →  export
```

## Cần có

| Thứ | Kiểm bằng |
|---|---|
| `ffmpeg`, `ffprobe` | `ffmpeg -version` |
| Python 3.10+ | `python --version` |
| faster-whisper | `python -c "import faster_whisper"` |

Thiếu whisper: `pip install faster-whisper`. Nếu để nó trong venv riêng thì trỏ
`DSH_VIDEO_ASR_VENV` vào venv đó — `cut.py` tự chạy lại bằng python của venv ấy.

## Nhịp 1 — `open`

```sh
python scripts/cut.py open raw\clip.mp4
```

In ra rồi mở `http://127.0.0.1:8799/`. Việc nó làm:

1. Tách clip thành **đảo tiếng** tại mỗi khoảng lặng ≥ 0.8s, transcribe **từng đảo riêng**
   (ASR cả clip sẽ gộp mất take lặp).
2. Đo lặng thật bằng `silencedetect` ở **−50 dB** — mặc định −30/−35 dB trên clip nói nhỏ
   sẽ coi tiếng nói là lặng và cắt mất lời.
3. Ghi `output/<ten>.tables.md`: bảng câu có số giây, bảng khoảng lặng, bảng nói lại,
   bảng mảnh vụn (kèm điểm).
4. Mở web view.

**Báo cho người dùng**: số câu, tổng thời lượng dự kiến, những chỗ đáng ngờ
(`nói lại …%`, `nói vấp`), và URL. Bảng in ra chat thì tóm gọn; bảng đầy đủ đã ở file.

## Nhịp 1.5 — Asset người dùng → evidence → draft

Sau khi có transcript + xác định khoảng cắt:

1. Nếu người dùng đưa kèm video/ảnh: đọc
   [`assets/SKILL.md`](assets/SKILL.md), chạy `index_assets.py`, xem hết asset,
   rồi ghép asset vào đúng đoạn thoại **trước**.
2. Chỉ đoạn nào chưa có asset và có claim kiểm chứng mới đọc
   [`evidence/SKILL.md`](evidence/SKILL.md): tìm báo, chụp màn hình vào
   `video/evidence/`.
3. Hiểu **thesis**, đánh dấu sự kiện/số liệu; lên `edited/draft.md`:
   giữ câu nào, asset nào, link báo nào, hiệu ứng/SFX ở đâu.
4. **Chờ người dùng duyệt draft** trước khi dựng.
5. Clip chỉ là ý kiến/châm biếm, không có claim kiểm chứng → ghi rõ
   “không chèn evidence”.

## Nhịp 2 — người dùng chỉnh trên web

Trên trang: tick/bỏ từng câu, chọn khoảng nghỉ trước mỗi câu, sửa text phụ đề,
click waveform để nghe, `Space` phát, `X` bỏ/giữ câu đang nghe. Mọi thay đổi lưu vào
`output/<ten>.review.json`.

Không đoán hộ. Chờ họ nói "chốt".

## Nhịp 3 — preview 360p rồi `export`

Sau khi cắt, **luôn xuất preview 360p trước** để người dùng duyệt:

```sh
python scripts/cut.py export output\clip.review.json --preview --seamless
```

Ra `output/<ten>.preview.mp4` (360p, veryfast, cùng timing/audio với bản cuối).

Chỉ khi người dùng chốt mới chạy bản chính thức:

```sh
python scripts/cut.py export output\clip.review.json --seamless
```

`--seamless`: cắt đúng biên tiếng, **không đệm, không để hơi thở/ngập ngừng**
giữa các câu đã ghép thành một câu hoàn chỉnh; fade 20ms mỗi đầu.

Ra `output/<ten>.mp4` + `.edl.json` + `.report.md`. Nó tự:

- dựng segment từ `keep`/`pause` (snap về frame, bỏ đoạn < 0.25s);
- render trim+concat + loudnorm −14 + fade 20ms (seamless) hoặc 30ms mỗi đầu;
- tự kiểm: duration, loudness, khoảng lặng còn lại, **mức to nhất tại mỗi mối cắt**
  (phải ≤ −38 dB mới coi là cắt trong lặng).

Đọc `.report.md`, chỗ nào `CAN KIEM` thì sửa rồi chạy lại — tối đa 3 vòng trước khi giao.

## Nhịp 4 — phụ đề hiệu ứng (chỉ khi được yêu cầu)

Chỉ làm khi người dùng nói rõ **“tạo phụ đề kèm hiệu ứng”**, “phụ đề động”,
“caption effects”. Đọc và làm theo skill con:
[`subtitle-effects/SKILL.md`](subtitle-effects/SKILL.md).

- Dùng Remotion, không thêm tiếng động/SFX — chỉ giữ audio gốc.
- Chỉ cần render **preview 360p** để người dùng xem trước; không dựng web editor.
- 1080p chỉ render khi người dùng yêu cầu riêng.
- Không tự ý bật cho các clip chỉ cắt thô.

## Luật đang dùng

| Luật | Mặc định | Ghi chú |
|---|---|---|
| Ngưỡng lặng | −50 dB | clip nói nhỏ: −55; phòng ồn: −45 |
| Lặng tối thiểu để cắt | 0.40s | dưới nữa là nhịp thở, giữ |
| Lặng trong câu | ≥ 0.20s | cắt sát để câu dài chạy liền; chỉ giữ hơi thở ngắn |
| Nhịp nghỉ | 0.08s câu đầu; 0s trong nhóm 3 câu; 0.65s sau nhóm | 3 câu liền mạch, rồi mới một đoạn ngừng dài (trước câu 4, 7…) |
| Nói lại | phủ ≥ 80% + cụm ≥ 4 từ + bản sau đủ ý | yếu hơn vẫn gắn cờ, mặc định bỏ |
| Mảnh vụn | ≥ 4 điểm | mở bằng từ cần bổ ngữ, ≤3 từ, ≤1.2s, sau lặng ≥1s |
| Câu lạc lõng | ≤ 5 từ và ≤ 1.5s; lặng ≥ 0.8s cả hai bên; không trùng từ mang nghĩa với câu trước/sau; không có vị ngữ | bỏ; không đủ ngữ cảnh để đứng một mình, cũng không ghép được vào câu nào |
| Câu mở dở | ≤ 6 từ và ≤ 1.2s; 2 từ đầu trùng 2 từ đầu câu sau | bỏ; take dở mở đầu rồi nói lại |
| Câu phụ thuộc | mở bằng “nhưng”, “nếu”, “mà”… | ghép sát câu sau thành một câu dài, không để nghỉ giữa |
| Ghép câu hoàn chỉnh | 0 khoảng nghỉ, 0 hơi thở, 0 ngập ngừng | dùng `--seamless`: cắt đúng biên tiếng, fade 20ms, nối liền tức thì |
| Câu cụt cuối clip | kết thúc lửng, thiếu vị ngữ | bỏ; kết ở câu hoàn chỉnh |

Cắt đúng chỗ: mọi biên nằm trong lặng **đo từ audio**, không dùng timestamp của Whisper
(Whisper đặt biên từ *bên trong* tiếng nói).

## Khi lỗi

| Triệu chứng | Xử lý |
|---|---|
| ASR gộp take lặp | kiểm `--split`, hạ xuống 0.6 nếu clip ngắt hơi ngắn |
| Cắt mất lời | ngưỡng lặng đang cao; đo lại `volumedetect` rồi hạ về −50/−55 |
| Bảng nào cũng "giữ" | clip quá nhỏ tiếng — kiểm `max_volume`, hạ ngưỡng |
| Câu lạc lõng bị bỏ oan | kiểm từ trùng và lặng hai bên; thêm vị ngữ vào `CLAUSE_HINTS` hoặc nới ngưỡng 0.8s |
| Port bận | `--port 8800` |
| Trang trắng | mở thẳng `http://127.0.0.1:8799/state` xem JSON có lên không |
