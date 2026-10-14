# Nguồn tài liệu trong kho tri thức

Mọi tài liệu dùng làm kho truy xuất đều ghi ở đây, kèm **giấy phép** và **cách
trích dẫn**. Có file này vì hai lý do:

1. Báo cáo tốt nghiệp phải trích dẫn được nguồn của mọi câu trả lời hệ thống đưa ra.
2. Giấy phép CC-BY và CC-BY-NC-SA **bắt buộc ghi công tác giả**. Dùng tài liệu mở mà
   không ghi nguồn là vi phạm giấy phép, dù tài liệu đó miễn phí.

Bản thân các file PDF **không** được commit (`.gitignore` chặn `data/raw/` và `*.pdf`),
nên kho git không phát tán lại tài liệu của ai. Tải lại bằng các đường dẫn dưới đây.

---

## MAS291 — Xác suất và Thống kê

### OpenStax, *Introductory Statistics 2e*

| | |
|---|---|
| Tác giả | Barbara Illowsky, Susan Dean và cộng sự |
| Nhà xuất bản | OpenStax, Rice University |
| Giấy phép | **CC BY-NC-SA 4.0** |
| Tải | https://assets.openstax.org/oscms-prodcms/media/documents/introductory-statistics-2e_-_WEB.pdf |
| Trang sách | https://openstax.org/details/books/introductory-statistics-2e |
| File trong kho | `data/raw/MAS291/textbook/openstax_introductory_statistics_2e.pdf` |
| Quy mô | 847 trang |

**Vì sao chọn sách này.** `scripts/rag_coverage.py` cho thấy MAS291 chỉ có 2/8 chương
có tài liệu và là môn DUY NHẤT không có sách giáo trình chung để bù. Sách này phủ đúng
sáu chương còn thiếu:

| Chương MAS291 còn thiếu | Chương tương ứng trong sách |
|---|---|
| Thống kê mô tả | Ch 2 Descriptive Statistics |
| Biến ngẫu nhiên rời rạc | Ch 4 Discrete Random Variables |
| Khoảng tin cậy | Ch 8 Confidence Intervals |
| Kiểm định giả thuyết | Ch 9 Hypothesis Testing with One Sample |
| So sánh hai mẫu | Ch 10 Hypothesis Testing with Two Samples |
| Hồi quy | Ch 12 Linear Regression and Correlation |

Thêm vào đó Ch 7 *The Central Limit Theorem* — đúng câu hỏi mà hệ thống từng phải
từ chối khi demo.

**Lưu ý về điều khoản NonCommercial.** Giấy phép cho dùng phi thương mại. Một đồ án
tốt nghiệp là phi thương mại, nên dùng được; nhưng nếu về sau triển khai hệ thống có
thu phí thì **phải đổi sang nguồn khác** (ví dụ *OpenIntro Statistics*, CC BY-SA, hoặc
OpenStax *Statistics* bản CC BY 4.0). Ghi rõ ở đây để sau không ai dùng nhầm bối cảnh.

---

## MAE101 — Toán cho kỹ thuật

### OpenStax, *Calculus Volume 1* và *Volume 2*

| | |
|---|---|
| Tác giả | Gilbert Strang, Edwin "Jed" Herman và cộng sự |
| Nhà xuất bản | OpenStax, Rice University |
| Giấy phép | **CC BY-NC-SA 4.0** |
| Trang sách | https://openstax.org/details/books/calculus-volume-1 · https://openstax.org/details/books/calculus-volume-2 |

### Slide giảng dạy FPT University Quy Nhơn

Slide của môn, do giảng viên cung cấp. **Không phải tài liệu mở** — chỉ dùng nội bộ
cho đồ án, không phát tán lại, không commit vào git.

---

## MAI391 — Toán cho học máy

### Deisenroth, Faisal, Ong — *Mathematics for Machine Learning* (2020)

| | |
|---|---|
| Nhà xuất bản | Cambridge University Press |
| Bản PDF | tác giả phát hành miễn phí cho mục đích học tập tại https://mml-book.github.io/ |
| Lưu ý | **Không phải CC**. Tác giả cho tải và đọc miễn phí; không được phát tán lại |

---

## MAD101 — Toán rời rạc

### Rosen — *Discrete Mathematics and Its Applications* (7th ed.)

| | |
|---|---|
| Nhà xuất bản | McGraw-Hill |
| Giấy phép | **Có bản quyền, không phải tài liệu mở** |
| Lưu ý | Dùng như giáo trình của môn, chỉ nội bộ cho đồ án. Không phát tán lại, không commit vào git. Muốn mở hoàn toàn thì thay bằng *Discrete Mathematics: An Open Introduction* (Oscar Levin, CC BY-SA) |

---

## Việc còn phải làm về nguồn

- [ ] Xin slide MAS291 của trường cho 6 chương còn thiếu — sách OpenStax phủ được nội
      dung, nhưng slide của chính giảng viên sát đề thi hơn.
- [ ] Xin slide MAI391 các chương 3, 6, 7, 9, 10, 12.
- [ ] Nếu muốn toàn bộ kho là tài liệu mở: thay Rosen bằng Levin (CC BY-SA) và cân
      nhắc đổi OpenStax sang bản CC BY cho MAS291.
