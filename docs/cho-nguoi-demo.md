# Dựng máy để demo — hướng dẫn cho người demo

Tài liệu này viết cho **người sẽ demo hệ thống**, không phải cho người viết code.

Ba tài liệu khác, chọn đúng cái bạn cần:
[huong-dan-su-dung.md](huong-dan-su-dung.md) để biết cách dùng app,
[huong-dan-cai-dat.md](huong-dan-cai-dat.md) nếu muốn dựng lại mọi thứ từ đầu,
[demo-script.md](demo-script.md) là kịch bản nói cho từng cảnh.

Nói trước một điều để đỡ mất thời gian: **`git pull` một mình KHÔNG đủ.** Kho git
cố ý không chứa bốn thứ nặng, và thiếu chúng thì app mở ra nhưng hỏng theo kiểu
khó đoán:

| Thứ | Dung lượng | Vì sao không có trong git |
|---|---|---|
| `data/raw/` — giáo trình, slide | 223 MB | có tài liệu bản quyền, không được phát tán lại |
| `data/rag_index/` — kho đã dựng | 61 MB | file sinh ra, và quá nặng cho git |
| `web/node_modules/` | 363 MB | cài lại bằng `npm install` |
| Model Ollama | ~8 GB | tải bằng `ollama pull` |

---

## Đường nhanh nhất (khoảng 20 phút)

### Bước 1 — Lấy code và thư viện

```bash
git clone https://github.com/Mytaem/AI-Tutor-for-Mathematics-Learning.git
cd AI-Tutor-for-Mathematics-Learning

python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

pip install -r requirements.txt
```

Cần **Python 3.11** (3.10 trở lên cũng được) và **Node.js 20+**.

### Bước 2 — Xin thư mục `data/rag_index/` từ người viết code ⭐

**Đây là bước tiết kiệm nhất.** Thư mục đó 61 MB và **tự đủ**: nó chứa cả nội dung
đoạn giáo trình lẫn vector đã mã hoá, nên bạn:

- **không cần** `data/raw/` (223 MB giáo trình),
- **không cần** chạy lại bước mã hoá (~40 phút trên CPU),
- **không cần** `ollama pull bge-m3`.

Nhận qua Google Drive / USB rồi đặt vào đúng chỗ:

```
AI-Tutor-for-Mathematics-Learning/
└── data/
    └── rag_index/
        ├── chunks.json        (~10 MB)
        ├── embeddings.npy     (~51 MB)
        └── encoder.txt
```

### Bước 3 — Cài Ollama và tải model

```bash
# cài từ https://ollama.com
ollama serve                        # để chạy ở một cửa sổ riêng
ollama pull qwen2.5:7b-instruct     # ~4,7 GB
```

Dùng bản **7b** cho demo. Bản 3b nhanh gấp đôi nhưng tiếng Việt kém hơn rõ rệt và
từng diễn đạt sai khái niệm thống kê.

### Bước 4 — Cài web

```bash
cd web
npm install
cd ..
```

### Bước 5 — Kiểm trước khi tin

```bash
python scripts/check_demo_ready.py
```

Script này in ra từng mục còn thiếu kèm **lệnh cần chạy để xử lý**. Chỉ khi nó in
`SẴN SÀNG DEMO.` thì mới coi là xong.

Chạy thêm cho chắc:

```bash
python -m pytest -q              # phải thấy 784 passed, khoảng 60 giây
python scripts/rag_coverage.py   # phải thấy "Mọi chương đều có tài liệu"
python scripts/demo_full.py      # 6 cảnh, không cần mạng, không cần model
```

---

## Bật hệ thống

Ba cửa sổ dòng lệnh:

```bash
# cửa sổ 1 — Ollama
ollama serve

# cửa sổ 2 — API
set LLM_HINTS=1
set OLLAMA_MODEL=qwen2.5:7b-instruct
python -m uvicorn src.api.app:create_app --factory --port 8000

# cửa sổ 3 — web
cd web && npm run dev
```

Mở **http://localhost:3000**

Trên thanh bên phải có **đèn báo kết nối backend**. Xanh là gọi được API. Đỏ thì
đọc chỉ dẫn ngay trên đó — thường là chưa bật cửa sổ 2.

Muốn mở thêm phần quản trị cho giảng viên:

```bash
set ADMIN_TOKEN=khoá-bạn-tự-đặt
```

Rồi trên web chuyển vai sang **Quản trị** và nhập đúng khoá đó. Không đặt biến này
thì phần quản trị tắt hoàn toàn.

---

## Nếu không xin được `data/rag_index/`

Tự dựng được, mất thêm khoảng một tiếng:

```bash
# 1. Tải giáo trình mở — đường dẫn trong docs/nguon-tai-lieu.md
#    MAS291 bắt buộc có: OpenStax Introductory Statistics 2e (847 trang)
#    đặt vào data/raw/MAS291/textbook/

# 2. Mã hoá
ollama pull bge-m3
python scripts/build_rag_index.py --dense     # ~40 phút trên CPU

# 3. Kiểm
python scripts/rag_coverage.py
```

**Đừng bỏ cờ `--dense`.** Không có embedding thì hệ thống mất thang tương đồng, và
cơ chế **từ chối câu hỏi ngoài phạm vi tắt hoàn toàn** — đo được là cả 3/3 câu kiểu
"cách nấu phở bò ngon" đều nhận về một đoạn giáo trình, và tỉ lệ trả lời sai chủ đề
nhảy từ 0% lên 32%. Hội đồng hỏi lệch một câu là vỡ demo.

---

## Chuẩn bị riêng cho buổi demo

### Đọc trước kịch bản

[docs/demo-script.md](demo-script.md) — 8 cảnh, có sẵn lời nói cho từng cảnh và câu
trả lời cho 5 câu hỏi hội đồng chắc chắn sẽ hỏi.

### Bật chế độ cache nếu sợ mạng hoặc máy chậm

```bash
set DEMO_MODE=1
```

Chế độ này chỉ đọc lại câu trả lời đã lưu trong cache, không gọi model. Phải chạy
qua các ví dụ **một lần ở chế độ thường trước** để cache có nội dung. Báo cáo ghi rõ
đây là cache, không giấu.

### Ba câu đáng demo nhất ở phần Hỏi lý thuyết

Chúng cho thấy hệ thống phân biệt được ba tình huống mà chatbot thường gộp làm một:

| Câu hỏi | Môn | Hệ thống làm gì |
|---|---|---|
| "Chu trình Euler là gì?" | MAD101 | trả lời kèm nguồn: tên file, chương, số trang |
| "Khoảng tin cậy là gì?" | MAS291 | trả lời từ giáo trình OpenStax mới nạp |
| "Cách nấu phở bò ngon" | bất kỳ | **từ chối**, nói thẳng là ngoài phạm vi |

### Hai chỗ nên biết trước để không bị bất ngờ

1. **Gợi ý dừng ở mức 4.** Bấm "Gợi ý thêm" nhiều lần thì nó leo `1 → 2 → 3 → 4` rồi
   **không chịu đưa lời giải đầy đủ**. Đó là cố ý: phải bấm nút xin lời giải hai lần
   mới lên mức 5. Nếu hội đồng tưởng là lỗi thì giải thích đúng như vậy.

2. **Câu trả lời đầu tiên chậm** vài giây đến vài chục giây vì model chạy trên CPU.
   Các câu sau nhanh hơn nhờ cache. Khi quay video thì cắt phần chờ.

---

## Khi có chuyện lúc demo

| Hiện tượng | Nguyên nhân thường gặp | Xử lý |
|---|---|---|
| Web mở ra nhưng **không nút nào chạy** | chưa bật API, hoặc API chạy ở origin khác | xem đèn báo ở cột phải; đặt `CORS_ORIGINS` nếu web không ở `localhost:3000` |
| Hỏi lý thuyết trả `"Kho giáo trình chưa được dựng"` | thiếu `data/rag_index/` | quay lại Bước 2 |
| Gợi ý ra câu cứng, giống nhau | chưa bật `LLM_HINTS=1` hoặc Ollama chưa chạy | bật lại cửa sổ 1 và 2 |
| Mục **Quản trị** không hiện | chưa đặt `ADMIN_TOKEN` | đặt biến rồi khởi động lại API |
| Mới dựng lại dữ liệu mà số không đổi | API nạp dữ liệu một lần lúc khởi động | khởi động lại API |
| Một chương báo "chưa có tài liệu" | kho thiếu chương đó | `python scripts/rag_coverage.py` để xem chương nào |

---

## Những gì KHÔNG cần cho demo

Đỡ mất thời gian cài:

- **`data/raw/`** — chỉ cần khi muốn dựng lại kho.
- **`models/`** — thiếu thì mô hình năng lực tự quay về BKT, vẫn chạy đúng.
- **`requirements-train.txt`** — chỉ dùng khi huấn luyện LoRA trên Kaggle.
- **GPU** — toàn bộ phần demo chạy trên CPU.
- **Mạng** — sau khi cài xong thì không cần mạng nữa. `demo_full.py` chạy được cả
  khi rút dây.
