# Giao thức đánh giá

Tài liệu này chốt **cách đo** trước khi có số, để không rơi vào cảnh chọn chỉ số sau
khi đã nhìn kết quả. Mỗi thí nghiệm nêu rõ: đo cái gì, so với baseline nào, chạy bằng
script nào, và kết quả thô nằm ở đâu.

Nguyên tắc chung:

- Mọi con số trong báo cáo phải tái lập được bằng một lệnh, với seed cố định.
- Kết quả thô lưu JSON trong `experiments/<tên thí nghiệm>/`; bảng trong báo cáo sinh
  từ file đó, không gõ tay.
- Baseline phải là thứ người ta thực sự sẽ làm nếu không có đồ án này (LLM hỏi thẳng,
  chọn bài ngẫu nhiên, trả đáp án luôn), không phải baseline dựng lên cho dễ thắng.

---

## Bảng chỉ số tổng hợp

| Trục | Chỉ số | Baseline để so | Trạng thái |
|---|---|---|---|
| Giải đúng | Accuracy theo môn | LLM thuần, không công cụ | chưa chạy |
| Kiểm chứng | Precision/Recall phát hiện bước sai | luật so khớp đơn giản | chưa chạy |
| Chẩn đoán lỗi | Macro-F1 mã lỗi | prompting zero-shot | một phần (EXP-3a) |
| Chất lượng gợi ý | Rubric 4 trục (1–5) | trả đáp án trực tiếp | chưa chạy |
| Knowledge tracing | AUC, ACC | chọn bài ngẫu nhiên | chưa chạy |
| Chống lộ đáp án | % gợi ý bị rò | không guardrail | **đã chạy (EXP-8)** |

---

## EXP-2 — chất lượng bộ chấm

Đo trên tập lỗi có nhãn `data/errors/*_injected.jsonl` (nhãn sạch 100% vì lỗi do máy
cài vào), và sau này trên bài làm sai THẬT do sinh viên nộp.

```
python scripts/build_error_dataset.py MAE101      # và MAI391 / MAS291 / MAD101
```

In ra ba tỉ lệ, cố ý tách riêng vì ba mức độ khó khác hẳn nhau:

- **phát hiện** — bộ chấm biết bài làm là sai (dễ nhất, gần như phải đạt 100%);
- **gán nhãn** — gán được ít nhất một mã lỗi;
- **đúng mã** — trong các mã gán ra có đúng mã đã cài vào (khó nhất).

Hạn chế phải ghi rõ trong báo cáo: lỗi tổng hợp phân bố khác lỗi thật, nên con số ở
đây là chặn trên. Tập test thật (~200 bài làm gán nhãn tay) mới là thước đo cuối.

---

## EXP-4 — truy xuất giáo trình

Kho hiện tại: 10.529 đoạn từ giáo trình và slide của cả 4 môn, index lai BM25 +
bge-m3, hợp nhất bằng RRF.

Một phát hiện đã đo được và ảnh hưởng tới thiết kế: **giáo trình là tiếng Anh, nên hỏi
bằng câu tiếng Việt cho kết quả kém hơn hẳn.** Truy vấn «tích phân từng phần» trả về
trang định nghĩa "hàm xác định từng phần" (BM25 bám vào chữ "từng phần" trong một chú
thích tiếng Việt), trong khi «integration by parts» trả đúng mục *3.1 Integration by
Parts*. Khi câu tiếng Việt KHÔNG có gì để BM25 bám vào thì bge-m3 bắc cầu rất tốt:
«xác suất có điều kiện» và «conditional probability» trả về đúng cùng ba trang của
`02_probability.pdf`.

Hệ quả thiết kế: gợi ý truy xuất bằng `skill.name_en` của kỹ năng gắn với đề, không
bằng câu hỏi tiếng Việt của sinh viên (`src/rag/hint_retriever.py`).

Việc còn phải làm: bộ 100 cặp (câu hỏi, đoạn đúng) để đo Recall@k và MRR cho ba cấu
hình dense / BM25 / hybrid.

---

## EXP-8 — chống lộ đáp án

Thí nghiệm đo **ba lớp phòng vệ** của bộ sinh gợi ý, mỗi lớp tách riêng được:

1. prompt ở mức < 4 không chứa đáp án (model không biết thì không nói ra được);
2. guardrail kiểm từng câu sinh ra, lộ thì bắt viết lại (tối đa 2 lần);
3. viết lại vẫn lộ thì dùng câu template — loại chắc chắn an toàn.

```
python scripts/exp8_leakage.py --per-subject 6 --levels 0,1,2,3
```

Bốn cấu hình, cùng một tập ca, chỉ khác hai công tắc:

| Cấu hình | Đáp án trong prompt | Guardrail | Trả lời câu hỏi |
|---|---|---|---|
| `raw` | không | không | model tự lộ bao nhiêu? |
| `raw+answer` | **có** | không | lớp phòng vệ 1 đáng giá bao nhiêu? |
| `full` | không | **có** | hệ thống thật |
| `full+answer` | **có** | **có** | guardrail chịu tải tới đâu? |

**Định nghĩa "lộ" (đo được bằng máy, không cảm tính):** một câu gợi ý làm lộ đáp án khi
có một mảnh trong nó mà nếu nộp làm bài thì verifier của môn sẽ chấm ĐÚNG. Guardrail
không tự phán xét thế nào là đáp án — nó hỏi thẳng verifier, nên mọi dạng viết tương
đương (nguyên hàm khác dạng, vector riêng nhân bội, công thức logic viết khác) đều bị
chặn như nhau.

**Cách đọc số cho trung thực:** tỉ lệ lộ của `full` đo bằng chính guardrail nên bằng 0
theo cấu tạo — con số đó KHÔNG phải bằng chứng. Ba thứ đáng tin ở cấu hình này là: số
lần phải viết lại, tỉ lệ rơi về template, và tỉ lệ lộ theo một thước đo độc lập
(`substring_leak`: đáp án chuẩn xuất hiện nguyên văn). Mọi câu sinh ra đều được lưu lại
trong `experiments/exp8/*.json` để chấm tay.

Kết quả: xem `experiments/exp8/`.

---

## Những gì KHÔNG đo được và phải nói thẳng

- **Chứng minh hình thức** (quy nạp, phản chứng trong MAD101): chỉ kiểm được cấu trúc,
  không kiểm được tính đúng đắn của lập luận.
- **Nguyên hàm sai khác hằng số nhân với hàm mũ**: `e^(-x)` và bội của nó là hàm riêng
  của phép đạo hàm, nên một lớp lỗi hệ số không phân biệt được bằng đạo hàm ngược.
- **Kho giáo trình chưa phủ hết syllabus**: MAS291 mới có chương xác suất và biến ngẫu
  nhiên liên tục; chương biến ngẫu nhiên rời rạc, ước lượng, kiểm định chưa có tài liệu.
  Gợi ý mức 1–2 cho các chương đó phải lấy đoạn lạc chương.
