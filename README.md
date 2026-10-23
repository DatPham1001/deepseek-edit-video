# edit-chinh-tri

Cắt thô video bình luận chính trị / phân tích thời sự nói một mình — có bước **duyệt trên web**
trước khi xuất.

Transcribe từng đoạn có tiếng, bỏ khoảng lặng, bỏ take nói lại, bỏ câu vụn nói vấp, câu lạc lõng, câu mở dở, rồi mở một
trang web để bạn tự bật/tắt từng câu, chỉnh khoảng nghỉ và sửa phụ đề **trên chính clip gốc**.
Chốt xong mới render — không tốn một lần encode nào cho những lần chỉnh giữa chừng.

```
open  →  chỉnh trên web  →  export
```

## Cần gì

- `ffmpeg`, `ffprobe` trong PATH
- Python 3.10+ và `pip install faster-whisper`

Không cần GPU. Model `medium` chạy CPU khoảng 2–3 phút cho 10 phút footage (lần đầu tải model).

## Dùng

```sh
# 1. transcribe + mở web view
python scripts/cut.py open raw/clip.mp4

# 2. chỉnh trên trang vừa mở, bấm Lưu

# 3. luôn duyệt bản preview 360p trước
python scripts/cut.py export output/clip.review.json --preview --seamless

# 4. chỉ xuất bản chính thức sau khi duyệt
python scripts/cut.py export output/clip.review.json --seamless
```

Kết quả: `output/clip.preview.mp4` (360p), `output/clip.mp4` + `clip.edl.json` + `clip.report.md`.

## Trang web

Mở `http://127.0.0.1:8799/`. Trang phát **file gốc** và tự nhảy qua các khoảng đã cắt, nên bạn
nghe đúng nhịp của bản dựng cuối mà không phải render.

| Thao tác | Ở đâu |
|---|---|
| Bỏ / giữ một câu | checkbox đầu dòng |
| Khoảng nghỉ trước câu | dropdown `liền` → `+0.70s` |
| Sửa lời thoại / phụ đề | ô text giữa dòng |
| Nghe từ câu đó | nút ▶ cuối dòng |
| Nhảy tới chỗ bất kỳ | click waveform (xanh = giữ, đỏ = cắt) |
| Phím tắt | `Space` phát/dừng · `X` bỏ/giữ câu đang nghe · `←` `→` ±1s |

Mọi thay đổi tự lưu vào `output/clip.review.json`.

## Nó cắt cái gì

| Luật | Mặc định | Vì sao |
|---|---|---|
| Ngưỡng lặng | **−50 dB** | clip nói nhỏ mà để −30/−35 dB thì tiếng nói bị coi là lặng và cắt mất lời |
| Lặng tối thiểu để cắt | 0.40s | ngắn hơn là nhịp thở, giữ lại |
| Lặng trong câu | ≥ 0.20s | cắt sát để câu dài chạy liền; chỉ giữ hơi thở ngắn |
| Nhịp nghỉ | 0.08s câu đầu, 0s trong nhóm 3 câu, 0.65s sau nhóm | 3 câu liền mạch, rồi mới ngừng dài (trước câu 4, 7…) |
| Nói lại | phủ ≥ 80% + cụm ≥ 4 từ + bản sau đủ ý | take trước bị bỏ, giữ take cuối |
| Mảnh vụn | ≥ 4 điểm | "Bây giờ", "theo văn của…" — không đầu không cuối |
| Câu lạc lõng | ≤ 5 từ, ≤ 1.5s, lặng ≥ 0.8s hai bên, không trùng từ với câu trước/sau, không vị ngữ | không đủ ngữ cảnh, không ghép được vào câu nào |
| Câu mở dở | ≤ 6 từ, ≤ 1.2s, 2 từ đầu trùng câu sau | take dở mở đầu rồi nói lại |
| Câu phụ thuộc | mở bằng “nhưng”, “nếu”, “mà”… | ghép sát câu sau thành câu dài |
| Ghép câu hoàn chỉnh | 0 khoảng nghỉ, 0 hơi thở | dùng `--seamless`, cắt đúng biên tiếng, fade 20ms |
| Câu cụt cuối clip | kết thúc lửng, thiếu vị ngữ | bỏ, kết ở câu hoàn chỉnh |

Hai điểm kỹ thuật quan trọng:

**Transcribe từng đảo tiếng, không transcribe cả clip.** Whisper gộp take lặp thành một câu khi
nghe liền mạch, nên bước phát hiện "nói lại" sẽ không thấy gì. Cắt tại mỗi khoảng lặng ≥ 0.8s
rồi transcribe riêng từng đoạn thì mỗi take thành một câu độc lập.

**Không dùng timestamp của Whisper để cắt.** Whisper đặt biên từ *bên trong* tiếng nói (một từ
có thể "dài" 4 giây nếu người nói ngừng giữa chừng). Mọi điểm cắt lấy từ `silencedetect` trên
audio thật, rồi mới đối chiếu lại.

## Tự kiểm sau khi render

`export` in ra và ghi `clip.report.md`:

- duration thật so với EDL
- loudness (đích −14 LUFS) và peak
- còn khoảng lặng dài nào không
- **mức to nhất tại mỗi mối cắt** — phải ≤ −38 dB mới tính là cắt trong lặng; chỗ nào ghi
  `CAN KIEM` là có khả năng cắt vào tiếng

## Nhánh mở rộng

- **`subtitle-effects/`** — phụ đề hiệu ứng bằng Remotion: một font, 17px, tối đa 2 dòng,
  4–5 từ/dòng, popup highlight giữa màn hình; preview 360p, giữ màu gốc, không SFX.
- **`assets/`** — quét video/ảnh người dùng đưa vào, ghép vào đúng đoạn thoại trước.
- **`evidence/`** — chỉ cho phần chưa có asset: tìm bài báo, chụp màn hình vào
  `video/evidence/`, dựng draft trước khi chèn.

## Giới hạn

- Viết cho **một người nói**, tiếng Việt (đổi được `--lang`). Nhiều người nói chen nhau thì
  bước tách đảo tiếng cần chỉnh tay.
- Luật "nói lại" so khớp từ, không hiểu ngữ nghĩa. Câu bị đánh dấu vẫn bật lại được trên web.
- Phụ đề sửa trên web nhưng chưa burn vào video — `edl.json` có sẵn trường `subtitles` để
  bước burn dùng tiếp.

## Giấy phép

MIT.
