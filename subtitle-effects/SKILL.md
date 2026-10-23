---
name: phu-de-hieu-ung
description: Phụ đề động bằng Remotion cho clip dọc — chữ đậm, từ khóa nhấn màu, hiệu ứng pop/shake, sticker; chỉ dùng khi người dùng yêu cầu "tạo phụ đề kèm hiệu ứng" / "phụ đề động" / "caption effects". Không thêm tiếng động, chỉ giữ audio gốc.
---

# Phụ đề hiệu ứng (Remotion)

Skill con của `edit-chinh-tri`. **Chỉ dùng khi người dùng yêu cầu rõ**:
“tạo phụ đề kèm hiệu ứng”, “phụ đề động”, “caption effects”, “làm phụ đề như video tham khảo”.
Không tự ý bật cho các clip chỉ cắt thô.

## Nguyên tắc

- **Không thêm tiếng**: không SFX, không whoosh, không nhạc nền. Chỉ giữ audio gốc của clip.
- **Giữ nguyên màu video gốc**: không LUT, không gradient/vignette phủ toàn khung, không chỉnh sáng/tương phản. Chỉ overlay chữ.
- **Preview 360p trước**, chỉ render 1080p sau khi người dùng duyệt.
- Chữ phải khớp lời nói, không bịa nội dung; sửa lỗi ASR trước khi dựng.
- Caption **tối đa 2 dòng**, mỗi dòng **4–5 từ**, cỡ **17px ở 360p**, hạ thấp gần đáy khung.
- **Một font duy nhất cho cả câu**; từ khóa chỉ đổi màu/glow, không đổi font.
- Từ đang nói được pop nhẹ; không trộn serif/sans trong cùng một caption.
- **Highlight popup**: vài đoạn đắt giá (đáy xã hội, địa ngục, chẳng đâu bằng, Việt Nam…)
  bật **giữa màn hình** 27–34px, một dòng, có burst/glow; chỉ 3–4 lần mỗi clip.

## Tham chiếu style

Video tham khảo: `https://www.youtube.com/shorts/8SEGw6HHjhI`

Đặc điểm lấy từ video:
- Nền là clip talking-head dọc 9:16.
- Caption in hoa, đậm, trắng, viền/tối; **cùng một font sans cho cả câu**.
- Từ khóa nhấn bằng **màu vàng/cam/đỏ + glow**, không đổi font hay kiểu chữ.
- Nhóm đáng chú ý có pill tối, glow màu, rung nhẹ hoặc sticker emoji.
- Hiệu ứng vào nhanh bằng spring, không rườm rà; không thêm âm thanh.

## Cấu trúc project

```
remotion/
  package.json
  remotion.config.ts
  public/clip.mp4          # clip nguồn
  src/index.ts
  src/Root.tsx
  src/CaptionVideo.tsx
  src/captions.json
```

`CaptionVideo` là composition 360×640, 30fps, duration = số frame của clip.
`captions.json` là mảng caption:

```json
{
  "start": 0.0,
  "end": 0.9,
  "words": [{"start": 0.0, "end": 0.28, "text": "Ở"}],
  "accent": ["VIỆT", "NAM"],
  "style": "normal | danger | gold | hero",
  "emoji": "🔥",
  "popup": false,
  "lineBreak": 4
}
```

- `accent`: các từ đổi màu nhấn, **vẫn cùng font** với cả câu.
- `lineBreak`: số từ của dòng 1; dòng 2 là phần còn lại. Luôn ≤ 2 dòng.
- `popup`: `true` để bật highlight giữa màn hình; caption thường để `false`.
- `style`: `danger` đỏ + rung, `gold` vàng + glow, `hero` chốt lớn + cờ.
- `emoji`: sticker; cờ Việt Nam dùng badge CSS, không dùng emoji cờ (một số máy không render).

## Quy trình

1. **Transcribe word-level** clip đã cắt (faster-whisper, `word_timestamps=True`).
2. Sửa lời thoại, chia nhóm caption, gắn `accent`/`style`/`emoji`.
3. Copy clip vào `public/clip.mp4`.
4. Render preview 360p:
   ```sh
   pnpm install
   pnpm exec remotion render src/index.ts CaptionVideo out.mp4 \
     --browser-executable="C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" \
     --codec=h264 --crf=18 --audio-codec=aac
   ```
5. Đưa `out.mp4` cho người dùng duyệt — **chỉ cần preview 360p**.
6. 1080p chỉ render khi người dùng yêu cầu riêng, bằng composition
   `CaptionVideo1080`.

Đổi clip khác: thay `public/clip.mp4`, sửa `durationInFrames` trong `Root.tsx`
(= số giây × 30), thay `captions.json`. Component tự nhân kích thước theo
`width/360`, nên composition 1080 dùng lại layout 360 mà không cần sửa tay.

Nếu `node`/`pnpm` không có trong PATH, dùng Node bundled của DSH:
`C:\Users\Admin\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\node\bin\node.exe`
và `...\pnpm\bin\pnpm.mjs`.

## Lỗi thường gặp

| Lỗi | Xử lý |
|---|---|
| Chữ “ở/ằ/ệ” thành ô đen | dùng `Segoe UI` cho mọi chữ; tránh Arial Black |
| Emoji cờ không hiện | dùng badge CSS đỏ + sao vàng, không dùng 🇻🇳 |
| Chữ dính nhau | tăng `columnGap` lên 14px |
| Render không có tiếng | kiểm `OffthreadVideo` không bị `muted`; thêm `--audio-codec=aac` |
| Edge không mở | truyền đúng `--browser-executable` tới `msedge.exe` |
| Preview quá nặng | giữ 360×640, CRF 18–23, veryfast |
