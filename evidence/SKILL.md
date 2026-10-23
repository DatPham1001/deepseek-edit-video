---
name: bang-chung-bao-chi
description: Dùng cho clip bình luận chính trị / lịch sử / thời sự có luận điểm cần dẫn chứng. Sau transcript và cắt thô, xác định thông điệp, đánh dấu sự kiện/số liệu, tìm bài báo, chụp màn hình vào folder evidence của video, rồi lên draft kịch bản có link báo và vị trí hiệu ứng trước khi dựng.
---

# Bằng chứng báo chí + draft kịch bản

Skill con của `edit-chinh-tri`. **Chỉ chạy sau khi đã ghép hết asset người dùng**
(theo `assets/SKILL.md`), dùng cho các đoạn còn trống có **luận điểm chính trị/lịch sử/thời sự**
cần dẫn báo, hoặc khi người dùng nói “tìm bằng chứng”, “dẫn báo”, “làm video có evidence”.

## 1. Hiểu clip muốn nói gì

Sau khi có transcript + các đoạn cắt, viết 2–4 câu:

- **Thesis**: người nói muốn chứng minh/ám chỉ điều gì?
- **Giọng**: nghiêm túc, châm biếm, phản biện?
- **Đối tượng nghe**: người quan tâm thời sự trong nước / quốc tế?
- **Kết luận**: clip muốn người xem tin điều gì sau khi xem?

Không bắt đầu dựng hiệu ứng trước khi chốt thesis.

## 2. Đánh dấu luận điểm

Lập bảng các câu có thể kiểm chứng:

| ID | Câu nói | Loại | Cần bằng chứng? |
|---|---|---|---|
| C1 | “…” | sự kiện quốc tế | có |
| C2 | “…” | sự kiện Việt Nam | có |
| C3 | “…” | số liệu thống kê | có, bắt buộc |
| C4 | “…” | mốc lịch sử | có |
| C5 | “…” | quan điểm/cảm nhận | không |

Loại ưu tiên: **số liệu, mốc thời gian, tên luật/chính sách, sự kiện có ngày tháng**.
Câu cảm nhận (“như địa ngục”, “chẳng đâu bằng”) **không** gắn bằng chứng như thể là số liệu.

## 3. Tìm & xác minh nguồn

- Dùng `web_search` / `web_fetch`.
- Ưu tiên: báo lớn, hãng tin, tài liệu chính phủ/tổ chức quốc tế, báo cáo có số liệu gốc.
- Mỗi luận điểm quan trọng: **2 nguồn độc lập** nếu có thể; 1 nguồn thì ghi rõ.
- Ghi: tiêu đề, nhà báo/hãng, ngày đăng, URL, đoạn trích ngắn.
- Không dùng bài blog/facebook/threads không kiểm chứng làm “số liệu chính thức”.
- Nếu không tìm được nguồn: ghi **“không có bằng chứng”**, không bịa.

## 4. Chụp màn hình

```sh
python evidence/capture_evidence.py "URL" \
  --out "video1/evidence" --name "ten-ngan"
```

Ra `video1/evidence/<ten>.png` + `.json`.

Nếu đưa vào video dọc, xuất thêm bản **1080×1920** (crop đúng cột bài,
bỏ header/quảng cáo/sidebar, thêm strip nguồn + ngày ở đáy) — đó là format
“điện thoại xem”. Có thể dùng `--mobile` để chụp thử layout mobile, nhưng
nhiều báo vẫn tràn ngang; crop từ bản desktop thường sạch hơn.

Kiểm tra ảnh:
- Thấy **tiêu đề bài + tên báo + ngày** (cuộn/cắt nếu cần).
- Không che mất số liệu/đoạn quan trọng.
- Ảnh đủ nét; nếu trang có cookie/popup, chụp lại sau khi đóng.

## 5. `evidence.json`

```json
{
  "claims": [
    {
      "id": "E1",
      "claim": "Câu nói trong clip",
      "type": "stat|event|history|policy",
      "source_title": "...",
      "publisher": "...",
      "date": "2025-...",
      "url": "https://...",
      "screenshot": "evidence/e1.png",
      "insert": {"start": 12.4, "end": 16.8},
      "animation": "paper_flip|stat_counter|bar_compare",
      "sfx": "paper_flip"
    }
  ]
}
```

`insert.start/end` tính theo timeline **bản đã cắt**, không phải clip gốc.

## 6. Draft kịch bản trước khi dựng

Tạo `edited/draft.md` gồm:

1. Thesis + giọng.
2. Bảng giữ/bỏ từng câu: giữ, bỏ, lý do.
3. Bảng luận điểm → nguồn → screenshot → có chèn không.
4. Bảng dựng: thời gian, lời nói, hiệu ứng, SFX.
5. Câu kết.
6. Ghi chú “chờ người dùng duyệt draft”.

Chỉ render sau khi người dùng chốt draft.

## 7. Hiệu ứng evidence (Remotion)

- **Paper card**: ảnh báo trượt vào từ phải, nghiêng nhẹ, có viền giấy + bóng; giữ 2.5–4s.
- **Source strip**: tên báo + ngày + URL rút gọn dưới ảnh.
- **Paper flip SFX**: chỉ dùng khi có evidence; file có sẵn ở
  `subtitle-effects/remotion/public/sfx/paper_flip.wav`, âm lượng thấp (~-18 dB).
- **Stat counter**: số liệu đếm tăng; **bar compare**: 2 cột so sánh, label rõ nguồn.
- Không chèn quá 1 evidence / 8–10s; không che mặt người nói quá lâu.
- Không thêm SFX cho caption thường; chỉ SFX lật báo/stat khi có evidence.

## 8. Khi không có bằng chứng

Nếu clip chỉ là ý kiến/châm biếm, **không có sự kiện hay số liệu**, ghi rõ trong draft:
“Không chèn evidence — không có claim kiểm chứng; giữ clip là bình luận.”
Không lấy ảnh minh họa vô nguồn để làm như bằng chứng.
