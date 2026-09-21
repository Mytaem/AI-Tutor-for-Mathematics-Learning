# AI Tutor for Mathematics Learning

Hệ thống gia sư toán ảo cho sinh viên đại học, phủ 4 môn **MAE101 / MAD101 / MAI391 / MAS291**.
Đồ án tốt nghiệp ngành AI. Kế hoạch đầy đủ: [PLAN.md](PLAN.md).

## Điểm khác biệt

Không phải một chatbot bọc API. Ba trụ kỹ thuật:

1. **Neuro-symbolic verification** — không tin lời giải của LLM. Mọi bước biến đổi và
   mọi đáp án đều được kiểm chứng độc lập bằng SymPy / NetworkX / SciPy / Monte Carlo.
2. **Socratic hint ladder** — gợi ý phân tầng 5 mức, có guardrail tự động chặn lộ đáp án,
   dựa trên chẩn đoán *bước sai đầu tiên* và *mã lỗi cụ thể*.
3. **Knowledge tracing + adaptive selection** — mô hình hóa năng lực theo ~80 kỹ năng con,
   chọn bài kế tiếp trong vùng phát triển gần nhất.

Chạy hoàn toàn bằng model mã nguồn mở, không phụ thuộc API trả phí.

## Cài đặt

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt

pytest tests/ -q
```

Phần huấn luyện (LoRA, knowledge tracing) cài riêng trên Colab/Kaggle:
`pip install -r requirements-train.txt`

## Cấu trúc

| Thư mục | Nội dung |
|---|---|
| `src/verify/` | Tầng kiểm chứng — **lõi kỹ thuật của đồ án**. Một bộ chấm cho mỗi mảng
  kiến thức (`calculus`, `linalg`, `mml`, `ode` tuỳ chọn), ghép thành môn trong `registry.py` |
| `src/tutor/` | Chẩn đoán lỗi, hint ladder, guardrail |
| `src/rag/` | Truy xuất kiến thức từ giáo trình |
| `src/kt/` | Knowledge tracing (BKT, DKT, SAKT) + bộ chọn bài |
| `src/api/` | FastAPI orchestrator |
| `src/bot/` | Telegram bot |
| `data/items/` | Ngân hàng bài tập (JSONL) |
| `data/skills/` | Cây kỹ năng + đồ thị tiên quyết |
| `experiments/` | Config và kết quả thô của từng thí nghiệm |

## Tình trạng

- [x] **Gate 0** — lõi so sánh tương đương, verifier MAE101 (tích phân, có xử lý đổi biến)
- [x] **Sinh dữ liệu** — 18 template → 300 bài tự sinh (+21 chép tay); mẫu lỗi có nhãn: 1612 (MAE101), 63 (MAI391)
- [x] **Tutor engine** — hint ladder 6 mức, chính sách leo thang, guardrail chống lộ đáp án
- [x] **LLM client** — chuỗi dự phòng vLLM → Ollama → cache, có DEMO_MODE
- [x] **API** — FastAPI + SQLite, BKT, bộ chọn bài theo vùng phát triển gần
- [x] **RAG** — chia chunk theo cấu trúc, hybrid BM25 + embedding, lọc theo metadata
- [x] **Cold start** — tiên nghiệm theo đồ thị tiên quyết, lan truyền ngược, bài đo đầu vào 6 câu
- [ ] Gate 1 — còn lại: nạp giáo trình thật, web app Next.js
- [x] **Gate 2 — sắp lại theo đề cương thật** — bộ chấm theo mảng kiến thức ghép thành môn:
  MAE101 = giải tích + đại số tuyến tính (41 bài chép tay); MAI391 = Math for ML (Deisenroth)
  + đại số tuyến tính (35 bài, 16 kỹ năng). Mã lỗi theo kiểu sai: `LA.*` dùng chung hai môn
- [ ] Gate 3 — knowledge tracing + cá nhân hóa
- [ ] Gate 4 — MAD101 + MAS291
- [ ] Gate 5 — Telegram bot, fine-tune LoRA, thực nghiệm người dùng
- [ ] Gate 6 — báo cáo, slide, video demo

## Nạp giáo trình

Thả tài liệu vào `data/raw/<MÃ MÔN>/` — môn học suy ra từ tên thư mục:

```
data/raw/MAE101/    data/raw/MAD101/    data/raw/MAI391/    data/raw/MAS291/
```

```bash
python scripts/build_rag_index.py              # chỉ BM25 — chạy ngay, không tải gì
python scripts/build_rag_index.py --dense      # thêm embedding (tải bge-m3 ~2GB)
python scripts/build_rag_index.py --ask "tích phân từng phần là gì"
```

Hỗ trợ `.pdf`, `.docx`, `.pptx`, `.txt`, `.md`. File hỏng bị bỏ qua chứ không làm
chết cả lần nạp.

## Chạy API

```bash
uvicorn src.api.app:app --reload
# http://localhost:8000/docs
```

Biến môi trường chính (xem `src/core/config.py`):

| Biến | Ý nghĩa |
|---|---|
| `VLLM_URL` | endpoint vLLM trên Kaggle qua tunnel — đổi mỗi lần khởi động lại |
| `OLLAMA_URL` | Ollama local, lớp dự phòng bắt buộc |
| `DEMO_MODE=1` | chỉ đọc cache, không gọi mạng — dùng khi bảo vệ |

## Ba nguyên tắc thiết kế không được vi phạm

**1. Không kiểm chứng được thì im lặng, không kết tội.**
`StepCheck.ok` có ba giá trị: `True` (đúng), `False` (sai), `None` (không đủ cơ sở kết luận).
Một gia sư báo sinh viên làm sai trong khi thực ra máy không kiểm tra nổi sẽ phá huỷ
hoàn toàn lòng tin — và đó là thứ khó lấy lại nhất.

**2. Tầng gợi ý chỉ được đọc `VerificationResult`.**
Không đọc lại đầu ra thô của LLM. Nếu gợi ý có thể bịa thì việc kiểm chứng ở tầng dưới
trở nên vô nghĩa.

**3. Đáp án không rời khỏi server trước khi sinh viên được phép thấy.**
API có lớp `PublicItem` riêng, cố ý không chứa `answer`, `integrand` và
`reference_solution_steps`. Nếu endpoint trả bài tập kèm lời giải thì hint ladder và
guardrail đều vô nghĩa — chỉ cần mở tab Network của trình duyệt là đọc được.
