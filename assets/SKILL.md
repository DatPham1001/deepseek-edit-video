---
name: b-roll-assets
description: Dùng khi người dùng đưa clip gốc kèm nhiều video/ảnh. Ưu tiên hiểu và xếp các asset người dùng đưa vào đúng đoạn thoại trước; chỉ phần chưa có asset mới đi tìm luận điểm/bằng chứng trên mạng. Lên draft bảng chèn asset + hiệu ứng trước khi dựng.
---

# Asset-first: xếp video/ảnh người dùng trước

Skill con của `edit-chinh-tri`. Thứ tự bắt buộc:

```
transcript + cắt thô
  → hiểu thesis
  → inventory asset người dùng
  → ghép asset vào đoạn phù hợp
  → phần còn trống mới tìm evidence trên mạng
  → draft
```

Không tìm báo trước khi đã xem hết asset người dùng.

## 1. Nhận asset

Người dùng có thể đưa:
- File nằm cùng folder video, hoặc
- Folder `assets/`, `b-roll/`, `hinh-anh/`…

Chạy:

```sh
python assets/index_assets.py "video1/assets" --out "video1/assets/assets.json"
```

Ra `assets.json` + `_thumbs/` để xem nhanh.

## 2. Hiểu từng asset

Điền vào `assets.json`:

- `description`: 1–2 câu asset cho thấy gì.
- `tags`: địa danh, nhân vật, sự kiện, con số, cảm xúc.
- Với video: xem 2–3 khung + nghe thoại nếu có; ghi asset có tiếng nói riêng không.
- Đánh dấu `quality`: `good|soft|noisy|crop` nếu cần.

Không đoán asset nếu chưa xem; mở thumbnail/frame thật.

## 3. Ghép asset vào lời nói

Lập bảng:

| Đoạn thoại | Thời gian | Asset | Cách chèn | Hiệu ứng |
|---|---|---|---|---|
| “…” | 4.2–7.8 | `assets/can-canh.mp4` | full-screen B-roll | cắt mềm 0.2s |
| “…” | 12.0–14.5 | `assets/bieu-do.png` | full-screen | zoom nhẹ 1.05→1.12 |
| “…” | 18.0–20.0 | `assets/anh-hien-truong.jpg` | picture-in-picture | trượt từ phải |

Ưu tiên khớp **đúng sự kiện/địa danh/nhân vật/con số**; nếu không có đúng, dùng asset gần nghĩa
nhất, không dùng ảnh chỉ “đẹp” mà sai nội dung.

## 4. Luật chèn

- **Full-screen B-roll**: 2–5s, cắt ở ranh giới câu; trả về mặt người nói sau đó.
- **Picture-in-picture**: dùng cho ảnh dọc/chi tiết, khung 40–45% bên trên caption.
- **Ảnh tĩnh**: Ken Burns 1.05→1.15, 2.5–4s; không rung.
- **Video ngang**: fit 9:16 bằng nền blur, không crop mất mặt/chữ.
- **Tiếng asset**: mặc định **mute** để giữ lời nói liền mạch. Nếu asset có tiếng quan trọng,
  hạ −18 dB và duck nhạc nền; không để tiếng asset đè lời.
- **Caption vẫn nằm trên** asset; không che caption.
- Không chèn quá 1 asset / 6–8s; ưu tiên nhịp thở giữa các câu.

## 5. Chỉ khi còn trống mới tìm evidence

Sau khi ghép hết asset người dùng, lập danh sách đoạn **chưa có hình** và **có claim**:

- số liệu, sự kiện quốc tế, sự kiện Việt Nam, mốc lịch sử, văn bản/chính sách.
- Chỉ những đoạn này mới sang [`evidence/SKILL.md`](../evidence/SKILL.md) để tìm báo + chụp màn hình.

Không lấp chỗ trống bằng ảnh vô nguồn.

## 6. Draft trước khi dựng

Tạo `edited/draft.md`:

1. Thesis.
2. Bảng giữ/bỏ câu.
3. Bảng **asset người dùng** (đoạn nào, asset nào, hiệu ứng gì).
4. Bảng **evidence web** cho phần còn trống (link + screenshot + có chèn không).
5. SFX: lật báo/stat chỉ khi có evidence; asset thường không thêm SFX.
6. Chờ người dùng duyệt draft.

Chỉ render sau khi chốt draft.
