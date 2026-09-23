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

Quy mô dữ liệu hiện tại — **5.990 mẫu lỗi có nhãn trên 89 mã lỗi**, sinh từ 4.155 đề
(155 chép tay + 4.000 sinh tự động):

| Môn | Đề chép tay | Đề sinh tự động | Mẫu lỗi có nhãn | Gán đúng mã |
|---|---|---|---|---|
| MAE101 | 41 | 300 | 1.660 | 72,3% |
| MAI391 | 35 | 1.200 | 1.899 | 99,7% |
| MAS291 | 36 | 1.200 | 1.432 | 100% |
| MAD101 | 43 | 1.200 | 999 | 100% |

Phân bố theo mã lỗi: 14 mã ≥ 100 mẫu, 54 mã 30–99, 20 mã 10–29, 1 mã dưới 10.

Mã duy nhất còn dưới 10 mẫu là `LA.ROWOP.INVALID` (phép biến đổi hàng không hợp lệ).
Nó là lỗi ở mức TỪNG BƯỚC, mà đề sinh tự động chỉ có đáp án cuối chứ không có lời
giải theo bước — muốn đủ mẫu thì phải sinh cả lời giải mẫu, việc này để sau.

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

## EXP-5 — mô hình theo dõi năng lực

```
python scripts/exp5_kt.py --subject MAE101 --students 360 --steps 50 --seeds 3
```

Bốn mô hình trên cùng dữ liệu, chia **theo người học** 70/15/15 (chia theo lượt thì
các lượt của cùng một người nằm cả ở train lẫn test, mô hình học thuộc người đó và
AUC đẹp lên một cách giả tạo). Dữ liệu trộn ba chiến lược chọn bài để mô hình không
học thuộc thói quen của một chiến lược.

### Kết quả — 360 học sinh mô phỏng × 50 lượt × 3 seed

| Mô hình | AUC (MAE101) | ± | ACC | log loss | AUC (MAD101) |
|---|---|---|---|---|---|
| majority | 0,500 | 0,000 | 0,622 | 0,664 | 0,500 |
| BKT (khớp tham số) | 0,639 | 0,012 | 0,637 | 0,640 | 0,551 |
| **DKT** (GRU) | **0,852** | 0,004 | 0,780 | 0,437 | **0,706** |
| SAKT (self-attention) | 0,776 | 0,006 | 0,727 | 0,543 | 0,681 |

- `majority` cho đúng 0,500 — kiểm chứng rằng hàm AUC không bị lỗi.
- Tham số BKT được **khớp từ dữ liệu** bằng tìm kiếm trên lưới 400 bộ, không dùng
  giá trị mặc định; nếu không thì phép so sánh thành "DKT đã huấn luyện" đấu với
  "BKT đoán bừa tham số".
- SAKT thua DKT ở cỡ dữ liệu này (25 nghìn lượt). Đúng như literature: self-attention
  cần nhiều dữ liệu hơn hồi tiếp mới phát huy.

**Cảnh báo khi trích dẫn con số này:** học sinh mô phỏng có một năng lực NỀN dùng
chung cho mọi kỹ năng. Mô hình chia sẻ được thông tin giữa các kỹ năng (DKT, SAKT)
đoán được ngay từ vài lượt đầu rằng người này khá hay yếu, còn BKT về cấu trúc không
làm được — mỗi kỹ năng là một biến độc lập. Nên khoảng cách 0,64 → 0,85 là **chặn
trên** cho lợi thế của DKT, không phải bằng chứng cho hiệu quả ngoài đời. Muốn kết
luận thật phải chạy lại trên ASSISTments hoặc log người dùng thật.

---

## EXP-6 — chiến lược chọn bài

```
python scripts/exp6_selection.py --subject MAE101 --prefix MAE.INT --students 80 --seeds 3
python scripts/exp6_selection.py --no-hint          # ablation giả thiết sư phạm
```

Đo trên **học sinh mô phỏng** (`src/kt/simulator.py`): mỗi người một vector năng lực
ẩn theo kỹ năng, khởi tạo từ độ sâu trong đồ thị tiên quyết; xác suất làm đúng theo
kiểu IRT có slip và guess; học sau mỗi lượt, học **nhiều hơn** khi làm sai mà được
gợi ý. Tốc độ học hiệu chỉnh theo một tiêu chí độc lập với mọi chiến lược: người học
trung bình thạo một kỹ năng sau khoảng 10 lượt luyện.

### Kết quả — 80 học sinh × 60 lượt × 3 seed

MAE101, chương tích phân (321 đề, 8 kỹ năng):

| Chiến lược | Tỉ lệ đúng | Kỹ năng thạo | Đạt mục tiêu | Sai liên tiếp |
|---|---|---|---|---|
| random | 62,2% | 4,6 | 86% | 4,1 |
| sequential | 64,6% | **4,8** | 95% | 4,6 |
| weakest | 51,1% | 4,7 | 81% | 5,9 |
| zpd | **69,9%** | 4,0 | 80% | **3,8** |
| zpd + phủ kỹ năng | 56,7% | 4,6 | 74% | 4,7 |

MAD101, chương đồ thị (3,7 vs 1,2 kỹ năng — chênh lệch lớn nhất quan sát được):

| Chiến lược | Tỉ lệ đúng | Kỹ năng thạo | Đạt mục tiêu |
|---|---|---|---|
| sequential | 72,2% | **3,7** | 100% |
| zpd | **76,4%** | 1,2 | 13% |
| zpd + phủ kỹ năng | 69,6% | 2,8 | 92% |

**Kết luận trung thực, ngược với kỳ vọng ban đầu:** ZPD cho trải nghiệm tốt nhất —
tỉ lệ đúng sát mục tiêu 75% và chuỗi sai liên tiếp ngắn nhất — nhưng **không** giúp
thạo nhiều kỹ năng hơn cách dạy theo thứ tự giáo trình. Lý do đã truy được: ZPD bám
lấy kỹ năng đang cho xác suất đúng ≈ 0,75 rồi đào sâu ở đó, bỏ quên các kỹ năng còn
quá khó — kinh điển là bài toán khai thác/khám phá.

Thêm tiêu chí **phủ kỹ năng** (ưu tiên kỹ năng ít được luyện) sửa được một phần. Bảng
quét trọng số trên chương đồ thị MAD101 cho thấy rõ cái giá phải trả:

| Trọng số phủ | 0 | 1,5 | 3 | 6 | 12 |
|---|---|---|---|---|---|
| Kỹ năng thạo | 1,2 | 1,9 | 2,1 | 2,8 | 3,3 |
| Tỉ lệ đúng | 76,1% | 70,2% | 69,3% | 69,0% | 69,4% |

Càng nặng thì càng phủ rộng nhưng càng mất tính "vừa sức", tới mức hoá ra quay vòng
đều như dạy tuần tự. Mặc định chọn 6.

Chạy EXP-6 cũng tìm ra một lỗi thật trong bộ chọn bài: `expected_success` **không hề
dùng độ khó của bài**, nên mọi bài của cùng một kỹ năng đều cho cùng xác suất và tiêu
chí "vừa sức" không phân biệt nổi bài dễ với bài khó.

Hạn chế: học sinh ở đây do mô hình sinh ra. Kết luận chỉ nói được về HÀNH VI CỦA
THUẬT TOÁN dưới giả định đó, không nói được về hiệu quả học tập ngoài đời.

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

### Kết quả — Qwen 2.5 3b-instruct qua Ollama (CPU), 96 ca mỗi cấu hình

24 bài làm sai (6 mỗi môn, mỗi mã lỗi và mỗi đề nhiều nhất một ca) × 4 mức gợi ý.
Dữ liệu thô: `experiments/exp8/qwen2.5_3b-instruct.json`.

| Cấu hình | Lộ (guardrail) | Lộ (nguyên văn) | Dùng được câu LLM | Về template | Lượt TB |
|---|---|---|---|---|---|
| `raw` | 6,2% | 3,1% | 100% | 0% | 1,00 |
| `raw+answer` | 8,3% | 4,2% | 100% | 0% | 1,00 |
| `full` | 0% | 0% | 99,0% | 1,0% | 1,09 |
| `full+answer` | 0% | 0% | 97,9% | 2,1% | 1,10 |

Đọc bảng:

- **Model nhỏ tự lộ đáp án 6,2% số lượt dù prompt không hề cho biết đáp án.** Nó tự
  giải ra rồi nói luôn ("Em đã tìm được nguyên hàm của 1/cos²(x) là tan(x) + C").
- **Đưa đáp án vào prompt làm tỉ lệ lộ tăng lên 8,3%** — lớp phòng vệ 1 (giấu đáp án)
  cắt được khoảng một phần tư số ca, nhưng một mình nó KHÔNG đủ.
- **Guardrail chặn nốt phần còn lại**, giá phải trả rất nhỏ: chỉ 6/96 lượt phải viết
  lại, 1% rơi về câu template.
- Trong 6 ca `raw` bị chặn có 1 ca chặn oan (gợi ý nhắc cận tích phân "từ 1 đến e"
  trong khi đáp án đúng bằng 1). Thiên lệch này là cố ý: chặn oan tốn một lượt sinh
  lại, để lọt là lộ đáp án thật.
- Trễ trung vị ~6–8 giây mỗi lượt trên CPU. Đây là lý do phải có cache và DEMO_MODE.

Chạy thí nghiệm này còn tìm ra hai lỗi thật, cả hai đều không lộ ra khi chỉ chạy test:

1. **Guardrail thủng vì dấu câu.** "Nguyên hàm là tan(x) + C." lọt qua, do dấu chấm
   dính vào token cuối làm biểu thức parse hỏng. Thước đo độc lập thấy, guardrail
   thì không — đúng lý do phải giữ hai thước đo khác nhau.
2. **Bộ chấm MAD101 cho điểm bài chép lại nguyên đề.** Phản đảo tương đương logic với
   mệnh đề gốc, nên "p → q" đúng trên mọi dòng bảng chân trị.

---

## Những gì KHÔNG đo được và phải nói thẳng

- **Chứng minh hình thức** (quy nạp, phản chứng trong MAD101): chỉ kiểm được cấu trúc,
  không kiểm được tính đúng đắn của lập luận.
- **Nguyên hàm sai khác hằng số nhân với hàm mũ**: `e^(-x)` và bội của nó là hàm riêng
  của phép đạo hàm, nên một lớp lỗi hệ số không phân biệt được bằng đạo hàm ngược.
- **Kho giáo trình chưa phủ hết syllabus**: MAS291 mới có chương xác suất và biến ngẫu
  nhiên liên tục; chương biến ngẫu nhiên rời rạc, ước lượng, kiểm định chưa có tài liệu.
  Gợi ý mức 1–2 cho các chương đó phải lấy đoạn lạc chương.
