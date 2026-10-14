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

Đủ 4/4 môn, chạy được end-to-end từ web và Telegram. **784 test**, chạy hết trong
~75 giây, không cần GPU, không cần mạng, không cần model.

| Phần | Trạng thái |
|---|---|
| Kiểm chứng ký hiệu 4 môn | ✅ có kiểm chéo độc lập (Monte Carlo, liệt kê vét cạn, tính lặp) |
| Ngân hàng đề | ✅ 155 bài chép tay + 4.800 bài tự sinh, **phủ 70/70 kỹ năng**, mỗi bài verifier tự chấm lại mới nhận |
| Tập lỗi có nhãn | ✅ 7.978 mẫu / 97 mã lỗi, trung vị 63 mẫu mỗi mã |
| Thang gợi ý + guardrail | ✅ có cả bản template lẫn bản do model sinh |
| Chọn phạm vi luyện | ✅ môn → chương → bài → dạng bài, mỗi nhánh hiện số đề |
| Hỏi đáp lý thuyết (RAG) | ✅ **12.633 đoạn; 28/28 câu hỏi kiểm được trả lời ĐÚNG CHỦ ĐỀ**, 0 trả bừa, 0 chặn oan |
| Knowledge tracing | ✅ BKT, DKT, SAKT — đo trên cả học sinh mô phỏng lẫn ASSISTments thật |
| API, web app, Telegram bot | ✅ web có chủ đề trắng/đen và phân vai sinh viên / quản trị |
| Fine-tune LoRA | ✅ macro-F1 0,098 → 0,921 (Qwen 1.5B, QLoRA trên Kaggle T4) |
| Kho giáo trình | ✅ mọi chương của 4 môn đều có tài liệu; MAS291 bù bằng OpenStax *Introductory Statistics 2e* |
| Thực nghiệm người dùng thật | ⬜ chờ dữ liệu bài làm sai thật |
| Báo cáo, slide, video demo | ⬜ |

Số liệu: [docs/results.md](docs/results.md) (sinh tự động) và
[docs/evaluation-protocol.md](docs/evaluation-protocol.md) (cách đo, hạn chế).
Hướng dẫn chạy: [docs/running.md](docs/running.md).

### Vài con số đáng chú ý

- Qwen 2.5 3b **tự giải đúng 22,9%** số bài, **tự chấm đúng 50%** — trong khi bộ chấm
  ký hiệu đúng 100% trên cùng bộ dữ liệu. Đây là lý do tồn tại của cả tầng kiểm chứng.
- Model **tự lộ đáp án 6,2%** số lượt dù prompt không hề cho biết đáp án; guardrail
  đưa về 0% với giá 6/96 lượt phải viết lại.
- Trên **ASSISTments 2009 (log người học thật)**: DKT **0,849** AUC, BKT 0,729 —
  nằm đúng khoảng các bài báo gốc báo cáo, tức là phần cài đặt không có lỗi ẩn.
- Phân loại mã lỗi: model **1.5B sau fine-tune đạt macro-F1 0,921**, vượt xa model
  7B chỉ prompting (0,415) — cùng một tập test.
- Hỏi đáp lý thuyết: **60% → 100% đạt** qua ba bước — từ điển thuật ngữ Việt–Anh,
  từ chối trung thực khi chương chưa có tài liệu, và nạp thêm giáo trình mở cho MAS291.
  Quan trọng hơn con số: **"trả bừa" từ 20% về 0%** — trả lời trôi chảy, đúng môn,
  sai chủ đề là hành vi tệ nhất của một gia sư, vì người học không có cách nào biết
  mà đề phòng.
- Truy xuất đúng đoạn **vẫn chưa đủ**: model 3b từng viết "p-value là xác suất để H₀
  đúng" — sai thống kê kinh điển, mà câu đọc rất trôi. Phải chốt thuật ngữ và luật
  miền trong prompt mới hết.

### Ba kết quả NGƯỢC với giả định ban đầu

Ghi lại vì chúng đáng giá hơn các con số đẹp:

1. **Hybrid không phải lúc nào cũng tốt nhất.** Hỏi tiếng Việt trên kho tiếng Anh,
   hybrid (0,310) kém hẳn dense đơn thuần (0,595) — RRF trộn kết quả rác của BM25 vào
   làm loãng. Nhưng sau khi mở rộng truy vấn bằng thuật ngữ tiếng Anh thì kết luận này
   **đảo ngược**, vì lúc đó BM25 mới có cái để khớp.
2. **Đưa đoạn giáo trình vào prompt gợi ý không đổi gì đo được.** Model 3b bỏ qua đoạn
   trích và viết theo mã lỗi đã chẩn đoán (EXP-7b).
3. **ZPD cho trải nghiệm tốt nhất nhưng phủ kỹ năng kém nhất** — nó né đúng chỗ người
   học yếu. Phải thêm tiêu chí phủ mới cân lại (EXP-6).

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

Nguồn và **giấy phép** của mọi tài liệu trong kho: [docs/nguon-tai-lieu.md](docs/nguon-tai-lieu.md).
Bản thân các PDF không được commit (`.gitignore` chặn `data/raw/` và `*.pdf`) nên kho
git không phát tán lại tài liệu của ai; file đó ghi đường dẫn để tải lại.

## Chạy API và web

```bash
uvicorn src.api.app:app --reload          # API — http://localhost:8000/docs
cd web && npm install && npm run dev      # web — http://localhost:3000
```

Biến môi trường chính (xem `src/core/config.py` và `src/api/app.py`):

| Biến | Ý nghĩa |
|---|---|
| `VLLM_URL` | endpoint vLLM trên Kaggle qua tunnel — đổi mỗi lần khởi động lại |
| `OLLAMA_URL` | Ollama local, lớp dự phòng bắt buộc |
| `LLM_HINTS=1` | gợi ý do model diễn đạt; tắt thì dùng câu template |
| `DEMO_MODE=1` | chỉ đọc cache, không gọi mạng — dùng khi bảo vệ |
| `CORS_ORIGINS` | origin được phép gọi API, mặc định `localhost:3000`. **Thiếu đúng biến này thì web dựng ra đầy đủ mà không nút nào chạy** |
| `ADMIN_TOKEN` | bật phần quản trị. **Không đặt thì phần quản trị tắt hoàn toàn** — dữ liệu ở đó là bài làm của người thật |

Hướng dẫn đầy đủ: [docs/running.md](docs/running.md).

### Người demo đọc gì

Nếu bạn là **người demo chứ không phải người viết code**:
[docs/cho-nguoi-demo.md](docs/cho-nguoi-demo.md) — `git pull` một mình KHÔNG đủ, vì
284 MB dữ liệu (giáo trình, kho vector đã dựng) cố ý không nằm trong git.

```bash
python scripts/check_demo_ready.py    # in ra từng thứ còn thiếu kèm lệnh xử lý
```

### Kiểm tra trước khi demo

```bash
python scripts/rag_coverage.py        # chương nào chưa có giáo trình
python scripts/demo_full.py           # 6 cảnh, không cần model, không cần mạng
```

Chạy `rag_coverage.py` trước mỗi lần demo. Nó tồn tại vì một buổi demo thất bại:
sinh viên hỏi về một chương mà kho không có tài liệu, và hệ thống khi đó trả về một
đoạn của chương khác. Thiếu dữ liệu thì phải biết **trước** khi đứng trước hội đồng.

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
