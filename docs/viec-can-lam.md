# Việc cần bạn làm — checklist

Phần code và thí nghiệm đã xong. Còn lại **ba việc cần người thật**, không ai làm
thay được. Tài liệu này có sẵn mọi thứ để copy: tin nhắn rủ bạn bè, hướng dẫn cho
người chấm, lệnh cần chạy.

Thứ tự ưu tiên: việc 1 quan trọng nhất (nó chặn cả phần đánh giá), việc 3 có thì
tốt, không có vẫn bảo vệ được.

---

## Việc 1 — Bài làm sai THẬT của sinh viên ⭐ quan trọng nhất

**Vì sao cần:** mọi con số về chẩn đoán lỗi trong báo cáo hiện đo trên lỗi do máy
cài vào. Hội đồng sẽ hỏi đúng chỗ này. Có 100–200 bài thật là phần đánh giá đứng
vững hẳn.

**Mục tiêu:** 200 bài, chấp nhận được từ 100.

### Cách nhanh nhất (2 buổi)

Bật hệ thống rồi nhờ bạn bè làm bài — bài sai tự vào cơ sở dữ liệu:

```bash
python -m uvicorn src.api.app:create_app --factory --port 8000
set TELEGRAM_TOKEN=... && python -m src.bot.main
```

Token bot lấy ở @BotFather trên Telegram (nhắn `/newbot`, đặt tên, nó trả token).

**Tin nhắn gửi bạn bè — copy nguyên văn:**

> Mọi người ơi, mình đang làm đồ án tốt nghiệp về gia sư toán AI, nhờ mọi người
> giúp 15 phút. Vào bot Telegram này: @<tên_bot>, gõ /start rồi /subject chọn môn
> mình đã học (MAE101, MAD101, MAI391 hay MAS291), làm khoảng 20 bài.
>
> Quan trọng: **cứ làm thật, sai cũng được, đừng tra mạng**. Bài sai mới là thứ
> mình cần — mình đang đo xem hệ thống chẩn đoán lỗi có đúng không. Làm sai càng
> tự nhiên càng giúp mình nhiều.
>
> Không cần đăng ký gì, không thu thông tin cá nhân, chỉ lưu bài làm thôi. Cảm ơn
> mọi người nhiều!

### Rồi gán nhãn

```bash
python scripts/label_real_errors.py --from-db --limit 50
python scripts/label_real_errors.py --stats
```

Mỗi bài, công cụ in sẵn đề + đáp án đúng + bài làm, bạn chỉ chọn mã lỗi từ danh
sách (gõ `list` để xem bảng mã). Khoảng 20–30 giây một bài, tức ~1,5 giờ cho 200
bài.

**Đừng gõ `may` trước khi tự nghĩ.** Lệnh đó hiện đáp án máy đoán; xem trước thì
rất dễ gật theo, mà nhãn đi xác nhận máy thì không còn kiểm được máy nữa.

### Nếu không nhờ được ai

Vẫn làm được, chậm hơn: xin thầy cô vài bài kiểm tra cũ đã chấm, hoặc chụp vở bài
tập của bạn cùng lớp, rồi gõ tay:

```bash
python scripts/label_real_errors.py      # nhập mã đề rồi nhập bài làm
```

---

## Việc 2 — Ba người chấm chất lượng gợi ý

**Vì sao cần:** chống lộ đáp án thì đo được bằng máy, nhưng "gợi ý này có dạy được
không" thì phải người đánh giá. Cần **3 người chấm độc lập** để tính được độ đồng
thuận (Cohen's kappa) — một người chấm thì không ai biết điểm đó có đáng tin không.

**Ai chấm:** bạn + 2 người nữa. Ưu tiên người đã học môn đó. Không cần giỏi toán
lắm, cần hiểu bài là được.

**Thời gian:** 128 dòng, khoảng 1 giờ mỗi người.

### Các bước

1. Gửi file `data/eval/hint_ratings_template.csv` cho từng người (mỗi người **một
   bản sao riêng**, không chấm chung file — chấm chung là mất tính độc lập).
2. Gửi kèm hướng dẫn ở dưới.
3. Nhận lại, gộp thành một file: giữ các cột đầu, đổi tên cột điểm thành
   `dung_toan_1`, `dung_toan_2`, `dung_toan_3`, tương tự cho ba cột còn lại.
4. Chạy: `python scripts/build_hint_rating_sheet.py --kappa data/eval/hint_ratings_filled.csv`

**Hướng dẫn gửi người chấm — copy nguyên văn:**

> Cảm ơn bạn giúp mình chấm. File có 128 dòng, mỗi dòng là một câu gợi ý mà hệ
> thống đưa cho sinh viên làm sai. Bạn đọc cột `de_bai`, `bai_lam_sai`, `goi_y`
> rồi cho điểm 1–5 vào bốn cột:
>
> - **dung_toan** — câu gợi ý có nói gì sai về toán không? (5 = hoàn toàn đúng,
>   1 = nói sai kiến thức)
> - **khong_lo** — nó có giữ được đáp án không? Cột `muc` là mức gợi ý: **mức 1,
>   2, 3 mà nói ra đáp án thì cho 1 điểm**; mức 4 thì được phép nói.
> - **su_pham** — nó có dẫn dắt để người học tự nghĩ không, hay làm hộ luôn?
>   (5 = gợi mở đúng chỗ, 1 = làm hộ hoặc nói lung tung)
> - **tieng_viet** — câu tiếng Việt có tự nhiên, đúng giọng thầy trò không?
>
> Cột `ghi_chu`: viết lý do khi bạn cho điểm 1 hoặc 2. Phần này mình đưa vào báo
> cáo nên càng cụ thể càng tốt.
>
> **Đừng bàn với người khác trong lúc chấm** — mình cần ba ý kiến độc lập để tính
> độ đồng thuận.

---

## Việc 3 — Thực nghiệm người dùng (có thì tốt, thiếu vẫn bảo vệ được)

12–20 sinh viên, mỗi người: làm bài kiểm tra trước (8–10 câu) → luyện với hệ thống
3–4 buổi → làm bài kiểm tra sau tương đương độ khó. Chia hai nhóm: nhóm A dùng thang
gợi ý đầy đủ, nhóm B chỉ nhận đáp án.

Mất 2–3 tuần. **Nếu không kịp thì bỏ**, và ghi rõ trong mục Hạn chế — nhiều đồ án
tốt nghiệp dừng ở mức đó, hội đồng chấp nhận. Che giấu mới là vấn đề.

---

## Việc 4 — Slide MAS291 ⭐ việc nhanh nhất mà đáng giá nhất

**10 phút của bạn, và nó mở lại 6/8 chương của một môn.**

Kiểm bằng: `python scripts/rag_coverage.py`

Kho giáo trình MAS291 chỉ có **2/8 chương** (Xác suất, Biến ngẫu nhiên liên tục) và
**không có sách giáo trình chung nào** để bù — khác ba môn kia, mỗi môn có một quyển
dày hàng nghìn đoạn (Rosen 4.730, OpenStax 3.160, Deisenroth 1.253).

Sáu chương đang trống:

| Chương |
|---|
| Biến ngẫu nhiên rời rạc |
| Thống kê mô tả |
| Khoảng tin cậy |
| Kiểm định giả thuyết |
| So sánh hai mẫu |
| Hồi quy |

Hỏi về sáu chương này, hệ thống nói thẳng *"chưa có tài liệu chương đó"* — đúng hành
vi, nhưng vẫn là trống. **Không kỹ thuật truy xuất nào bù được chuyện thiếu dữ liệu.**

```bash
# thả file vào đây rồi chạy:
#   data/raw/MAS291/slides/
python scripts/build_rag_index.py --dense
python scripts/rag_coverage.py        # kiểm lại
```

Tiện thì xin thêm **slide MAI391 chương 3, 6, 7, 9, 10, 12** — môn này có sách
Deisenroth bù nên không gấp, nhưng có slide thì câu trả lời sát bài giảng hơn.

## Việc 5 — Mấy thứ nhỏ (5 phút)

- **Huỷ token Kaggle cũ** (nó đã lộ trong ảnh chụp màn hình gửi qua chat): vào
  Kaggle → Settings → API → Expire Token, rồi tạo token mới.
- **Đổi `ADMIN_TOKEN`** nếu còn dùng khoá thử trong lúc phát triển.
- **Xác nhận phạm vi với giảng viên hướng dẫn**: 4 môn có rộng quá không, thầy cô
  muốn trọng tâm ở verifier hay ở knowledge tracing.

---

## Đã xong, không cần bạn làm nữa

Ghi lại để bạn không mất thời gian vào những việc này:

- ~~MAE101 chương Giới hạn và Đạo hàm không có đề~~ → đã thêm 11 dạng bài, phủ 21/21
  kỹ năng.
- ~~Hỏi lý thuyết trả lời sai chủ đề~~ → từ điển thuật ngữ Việt–Anh, 60% → 100% đạt.
- ~~Web hiện ra mà không nút nào chạy~~ → API thiếu CORS.

---

## Sau khi có dữ liệu, tôi làm nốt

| Bạn giao | Tôi chạy |
|---|---|
| `real_labeled.jsonl` | EXP-2 trên dữ liệu thật, cập nhật mọi bảng và mục hạn chế |
| Phiếu chấm đã điền | Tính kappa, viết mục L2 của báo cáo |
| Log người dùng thật | Huấn luyện lại DKT trên log thật thay vì học sinh mô phỏng |
| Slide còn thiếu | Dựng lại kho RAG, chạy lại EXP-4 |
