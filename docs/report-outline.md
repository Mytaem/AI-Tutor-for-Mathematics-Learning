# Dàn ý báo cáo — ánh xạ sang code và số liệu

Mỗi mục ghi rõ **lấy số ở đâu** và **chạy lệnh nào để tái lập**. Chỗ nào chưa có
số thì ghi thẳng là chưa có, đừng để tới lúc viết mới phát hiện thiếu.

---

## Chương 1 — Mở đầu

Vấn đề: mô hình ngôn ngữ mã nguồn mở cỡ nhỏ giải toán hay sai và hay bịa bước, nên
một chatbot bọc API không đủ tin cậy để dạy học.

Ba đóng góp, mỗi đóng góp có bằng chứng định lượng:

| Đóng góp | Bằng chứng | Nằm ở |
|---|---|---|
| Kiểm chứng neuro-symbolic, có kiểm chéo độc lập | chấm đúng 100% trên 160 cặp, trong khi để LLM tự chấm chỉ đúng 50% và nhận nhầm 35% bài sai | `src/verify/`, EXP-2, EXP-7a |
| Thang gợi ý chống lộ đáp án, đo được | model tự lộ 6,2% số lượt; có guardrail còn 0% | `src/tutor/`, EXP-8 |
| Mô hình năng lực + chọn bài thích ứng | DKT AUC 0,852 so với BKT 0,639; năm chiến lược chọn bài | `src/kt/`, EXP-5, EXP-6 |

Con số trả lời thẳng câu "khác gì một chatbot bọc API": Qwen 2.5 3b **tự giải đúng
22,9%** số bài (41,7% nếu cho suy luận từng bước) và **tự chấm đúng 50%**. Phần tính
toán và phán xét vì thế không thể giao cho mô hình ngôn ngữ.

## Chương 2 — Cơ sở lý thuyết

ITS, knowledge tracing (BKT → DKT → SAKT), LLM cho toán, tool-augmented reasoning,
RAG, Socratic tutoring. Các bài gốc đã cài lại: Piech 2015 (DKT), Pandey 2019 (SAKT),
Corbett & Anderson 1995 (BKT).

## Chương 3 — Thiết kế hệ thống

Kiến trúc trong `PLAN.md`; lược đồ CSDL trong `src/api/db.py`; luồng dữ liệu:
bài làm → verifier → chẩn đoán → thang gợi ý → cập nhật năng lực → chọn bài kế.

Điểm đáng nói khi bảo vệ: **web và bot Telegram không chứa logic sư phạm**, cùng gọi
một API, nên log hai kênh nằm chung một bảng và phân tích gộp được.

## Chương 4 — Xây dựng dữ liệu

| Loại | Số lượng | Sinh bằng |
|---|---|---|
| Kỹ năng (KC) | 70, có đồ thị tiên quyết | `data/skills/` |
| Mã lỗi | 89 (mã `LA.*` dùng chung 2 môn) | `data/errors/*.json` |
| Đề chép tay | 155 | `data/items/*.jsonl` |
| Đề sinh tự động | 4.000, mỗi bài verifier tự chấm lại mới nhận | `scripts/build_bank.py all 1200` |
| Mẫu lỗi có nhãn | 5.990 | `scripts/build_error_dataset.py` |
| Kho giáo trình | 10.566 đoạn, hybrid BM25 + bge-m3 | `scripts/build_rag_index.py --dense` |

Chỗ phải nói thẳng: lỗi là do máy cài vào, phân bố khác lỗi thật; **chưa có bài làm
sai thật nào của sinh viên**.

## Chương 5 — Phương pháp

- **Kiểm chứng theo tính chất, không so dạng viết**: nguyên hàm kiểm bằng đạo hàm
  ngược, vector riêng bằng `A·v = λv`, hệ tuyến tính bằng thế ngược, logic bằng
  `satisfiable(¬(A↔B))`, truy hồi bằng tính lặp.
- **Kiểm chéo độc lập**: Monte Carlo 400.000 lần (MAS291), liệt kê vét cạn (MAD101).
- **Thang gợi ý 6 mức** và định nghĩa "lộ đáp án" đo được bằng máy: một câu gợi ý lộ
  đáp án khi có mảnh nào trong nó mà nộp lên verifier sẽ chấm đúng.
- **Mô hình năng lực**: BKT (khớp tham số bằng lưới) → DKT (GRU) → SAKT.
- **Chọn bài**: điểm = kỹ năng yếu + vừa sức (ZPD) + sẵn sàng tiên quyết + phủ kỹ
  năng − phạt lặp.

## Chương 6 — Cài đặt

Python 3.11, SymPy/NetworkX/SciPy/PyTorch, FastAPI + SQLite, Next.js, aiogram.
Chuỗi model ba lớp vLLM → Ollama → cache; `DEMO_MODE` cho buổi bảo vệ.
Hướng dẫn chạy: `docs/running.md`.

## Chương 7 — Thực nghiệm

| Thí nghiệm | Trạng thái | Lệnh |
|---|---|---|
| EXP-1 độ chính xác giải toán | xong (22,9% / 41,7%) | `scripts/exp1_solving.py` |
| EXP-2 chất lượng bộ chấm | xong trên lỗi tổng hợp; **thiếu tập lỗi thật** | `scripts/build_error_dataset.py` |
| EXP-3 phân loại mã lỗi | xong: prompting 7b 0,415 → LoRA 1.5B **0,921** | `scripts/exp3_error_classification.py`, `scripts/kaggle_push.py` |
| EXP-4 truy xuất | xong; còn thiếu 100 cặp gán nhãn tay | `scripts/exp4_retrieval.py` |
| EXP-5 knowledge tracing | xong trên cả mô phỏng và **ASSISTments thật** (DKT 0,849) | `scripts/exp5_kt.py --data assistments` |
| EXP-6 chọn bài | xong | `scripts/exp6_selection.py` |
| EXP-7a bỏ kiểm chứng ký hiệu | xong | `scripts/exp7_llm_judge.py` |
| EXP-7b ablation −RAG, −thang gợi ý | **chưa chạy** (cần người chấm) | — |
| EXP-8 chống lộ đáp án | xong | `scripts/exp8_leakage.py` |
| L2 rubric chất lượng gợi ý | phiếu chấm đã xuất, **chờ 3 người chấm** | `scripts/build_hint_rating_sheet.py` |

Bảng sinh tự động: `docs/results.md` (chạy `python scripts/make_report_tables.py`).
Diễn giải và hạn chế từng thí nghiệm: `docs/evaluation-protocol.md`; dữ liệu thô:
`experiments/`.

## Chương 8 — Kết luận và hạn chế

Hạn chế phải viết đúng như đã đo, không làm nhẹ đi:

1. **Chưa có người dùng thật.** Mọi kết luận về chọn bài và theo dõi năng lực đều đo
   trên học sinh mô phỏng, tức là đo HÀNH VI THUẬT TOÁN chứ không phải hiệu quả học.
2. **Khoảng cách DKT–BKT là chặn trên.** Học sinh mô phỏng có năng lực nền dùng chung
   cho mọi kỹ năng — thứ mà BKT về cấu trúc không nắm được.
3. **ZPD không thắng toàn diện.** Nó cho trải nghiệm tốt nhất nhưng thạo ít kỹ năng
   hơn dạy tuần tự; thêm tiêu chí phủ kỹ năng mới gỡ lại được một phần.
4. **Kho giáo trình chưa phủ hết syllabus**, MAS291 thiếu nhiều chương.
5. **Lỗi mức từng bước mới có dữ liệu ở dạng giải hệ** (khử Gauss). Các dạng bài
   khác vẫn chỉ sinh được đáp án cuối, nên chẩn đoán theo bước chưa phủ hết.
6. **Chứng minh hình thức** chỉ kiểm được cấu trúc, không kiểm được lập luận.

## Chương 9 — Phụ lục

Danh sách 89 mã lỗi, 70 kỹ năng kèm đồ thị tiên quyết, ví dụ hội thoại đầy đủ của cả
ba kênh (CLI, web, Telegram), và bảng đối chiếu mỗi con số trong báo cáo với lệnh sinh
ra nó.
