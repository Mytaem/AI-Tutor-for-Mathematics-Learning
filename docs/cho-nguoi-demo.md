# Tải về và chạy demo Numeris

Viết cho **người tải dự án về máy mình để chạy thử hoặc demo**. Không cần biết code.
Làm lần lượt từng bước, khoảng **30 phút** (phần lớn là chờ tải).

Tài liệu khác: [huong-dan-su-dung.md](huong-dan-su-dung.md) (cách dùng app),
[demo-script.md](demo-script.md) (kịch bản nói khi demo),
[trien-khai.md](trien-khai.md) (cài lên máy chủ bằng Docker).

---

## 0. Cần cài sẵn

| Phần mềm | Phiên bản | Tải ở |
|---|---|---|
| Git | bất kỳ | https://git-scm.com |
| Python | **3.11** (3.10–3.12 đều được) | https://www.python.org — khi cài nhớ tích **Add Python to PATH** |
| Node.js | **22** (tối thiểu 20) | https://nodejs.org |
| Ollama | bản mới | https://ollama.com |

Máy nên có **16 GB RAM**. Có card NVIDIA thì phần Hỏi đáp nhanh hơn nhiều; không có
vẫn chạy được.

---

## 1. Tải code

Mở **Command Prompt** (hoặc PowerShell):

```bat
git clone https://github.com/Mytaem/AI-Tutor-for-Mathematics-Learning.git
cd AI-Tutor-for-Mathematics-Learning
```

## 2. Cài thư viện Python (khoảng 5–10 phút)

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Sau lệnh `activate`, đầu dòng lệnh có chữ `(.venv)`. **Mỗi lần mở cửa sổ mới để chạy
API đều phải gõ lại** `.venv\Scripts\activate`.

## 3. Tải mô hình AI (khoảng 6 GB)

```bat
ollama pull qwen2.5:7b-instruct
ollama pull bge-m3
```

Ollama thường tự chạy nền sau khi cài (có icon ở khay đồng hồ). Nếu lệnh trên báo
không kết nối được thì mở một cửa sổ riêng và chạy `ollama serve`.

> Chỉ dùng bản **7b**. Bản 3b có giấy phép cấm dùng thương mại và tiếng Việt kém hơn.

## 4. Cài giao diện web (khoảng 3 phút)

```bat
cd web
npm install
cd ..
```

## 5. (Tuỳ chọn) Kho giáo trình cho phần Hỏi đáp

Xin người viết code thư mục **`data/rag_index/`** (61 MB, gửi qua Google Drive/USB) rồi
đặt vào đúng chỗ:

```
AI-Tutor-for-Mathematics-Learning\data\rag_index\chunks.json
AI-Tutor-for-Mathematics-Learning\data\rag_index\embeddings.npy
AI-Tutor-for-Mathematics-Learning\data\rag_index\encoder.txt
```

**Không có kho này vẫn demo được:** Luyện tập, Gợi ý, Thư viện kiến thức, Lịch sử,
Tiến độ chạy đầy đủ, và Hỏi đáp vẫn trả lời được các câu khớp với **thẻ kiến thức**
(70 kỹ năng). Có kho thì câu trả lời có thêm trích dẫn giáo trình kèm số trang.

## 6. Kiểm tra máy đã sẵn sàng

```bat
python scripts\check_demo_ready.py
```

Script in ra mục nào còn thiếu kèm lệnh để sửa. Thấy `SẴN SÀNG DEMO.` là xong.

---

## Chạy demo

Mở **hai cửa sổ** Command Prompt, cả hai đứng ở thư mục `AI-Tutor-for-Mathematics-Learning`.

**Cửa sổ 1 — API:**

```bat
.venv\Scripts\activate
set ADMIN_TOKEN=demo-admin-123
python -m uvicorn src.api.app:create_app --factory --port 8000
```

Chờ tới khi thấy `Application startup complete.`

**Cửa sổ 2 — web:**

```bat
cd web
npm run dev
```

Mở trình duyệt vào **http://localhost:3000**.

> Cổng 8000 đã có chương trình khác dùng? Chạy API ở cổng khác (ví dụ `--port 8010`), rồi
> trước khi `npm run dev` gõ `set NEXT_PUBLIC_API_URL=http://localhost:8010`.

---

## Thử những gì (kịch bản 10 phút)

1. **Tạo tài khoản** — email bất kỳ, mật khẩu ≥ 8 ký tự có cả chữ và số.
   *Link xác thực email:* máy demo chưa cấu hình gửi mail, nên nội dung thư được in ra
   **cửa sổ 1 (API)** — tìm dòng có `/verify?token=` và dán link vào trình duyệt.
2. **Trang chủ** — vòng mục tiêu 10 bài/ngày, chuỗi ngày học. Chọn môn **MAS291** →
   **Tiếp tục luyện**.
3. **Nộp đáp án sai**, rồi bấm **Gợi ý rõ hơn** nhiều lần: gợi ý đi từ chương → công
   thức → các bước Bước 1, 2, 3 → làm mẫu bước đầu → lời giải. Không lộ đáp án sớm.
4. **Gõ đáp án kiểu tự nhiên** — `x²/2 + C`, `sinx`, `căn x`, `0,75` — hệ thống vẫn
   hiểu. Làm đúng thì bấm **Xem lời giải mẫu**.
5. **Thư viện** — 70 thẻ: công thức, lỗi hay gặp, ví dụ giải từng bước; bấm "Luyện …
   bài của phần này".
6. **Hỏi đáp** — hỏi *"Định lý Bayes dùng thế nào?"*: thẻ kiến thức hiện ngay, câu trả
   lời theo bước có ghi nguồn sau 20–60 giây. Hỏi *"Cách nấu phở bò"*: hệ thống **từ
   chối**, nói rõ là ngoài phạm vi.
7. **Lịch sử** → **Ôn lỗi sai**; **Tiến độ** — biểu đồ 14 ngày, mức thành thạo từng kỹ năng.
8. **Quản trị** (cột trái, chọn "Quản trị") — nhập `demo-admin-123`.

### Biết trước để không bất ngờ

- **Hỏi đáp chậm 20–60 giây** trên máy không có GPU. Thẻ kiến thức hiện ngay để có cái
  đọc trong lúc chờ. Quá 100 giây thì hệ thống trả về đoạn giáo trình thay vì treo.
- **Lời giải đầy đủ phải bấm hai lần** — cố ý, để người học thử tự làm bước cuối trước.
- **Lần mở đầu tiên** thư viện có thể mất ~15 giây để dựng thẻ; sau đó tức thì.

---

## Khi có chuyện

| Hiện tượng | Xử lý |
|---|---|
| Web hiện **"Không thể kết nối"** | Cửa sổ 1 chưa chạy hoặc đã tắt — chạy lại. API khác cổng 8000 thì xem ghi chú ở mục Chạy demo |
| `pip install` lỗi | Kiểm tra `python --version` là 3.10–3.12; nâng pip: `python -m pip install -U pip` |
| `npm install` lỗi | Kiểm tra `node --version` ≥ 20 |
| Hỏi đáp báo **"thiếu bộ mã hoá"** | `ollama pull bge-m3`, đảm bảo Ollama đang chạy |
| Hỏi đáp luôn trả đoạn tiếng Anh | Chưa tải `qwen2.5:7b-instruct` hoặc máy quá chậm — xem cửa sổ 1 |
| Mục **Quản trị** không hiện | Quên `set ADMIN_TOKEN=...` trước khi chạy API ở cửa sổ 1 |
| Quên mật khẩu tài khoản demo | Trang đăng nhập → **Quên mật khẩu?**; link đặt lại cũng in ra cửa sổ 1 |

Muốn tắt: bấm `Ctrl + C` ở từng cửa sổ.
