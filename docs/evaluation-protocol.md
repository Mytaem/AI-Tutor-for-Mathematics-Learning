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

| Trục | Kết quả chính | Trạng thái |
|---|---|---|
| EXP-1 LLM tự giải toán | 22,9% (hỏi thẳng) → 41,7% (có suy luận từng bước) | xong |
| EXP-2 chất lượng bộ chấm | phát hiện 100%; gán đúng mã 72–100% tuỳ môn | xong trên lỗi tổng hợp |
| EXP-3 phân loại mã lỗi | prompting 7b 0,415 → **LoRA 1.5B 0,921** macro-F1 | xong |
| EXP-4 truy xuất | Recall@5: 0,595 (hỏi tiếng Việt) / 0,976 (tiếng Anh) | xong |
| EXP-5 knowledge tracing | **ASSISTments thật**: DKT 0,849 > SAKT 0,792 > BKT 0,729 | xong |
| EXP-6 chọn bài | ZPD tốt nhất về trải nghiệm, kém nhất về phủ kỹ năng | xong trên mô phỏng |
| EXP-7a bỏ kiểm chứng ký hiệu | LLM chấm đúng 50%, bộ chấm ký hiệu 100% | xong |
| EXP-7b bỏ RAG khỏi gợi ý | không đổi gì đo được (bám giáo trình 8% cả hai bên) | xong |
| EXP-8 chống lộ đáp án | model tự lộ 6,2% → guardrail đưa về 0% | xong |
| Rubric chất lượng gợi ý | — | chưa chạy |

---

## EXP-1 — mô hình ngôn ngữ tự giải toán được bao nhiêu

```
python scripts/exp1_solving.py --per-subject 12            # hỏi thẳng
python scripts/exp1_solving.py --per-subject 12 --mode cot # cho nghĩ từng bước
```

48 bài (12 mỗi môn), **chấm bằng chính verifier của môn** — chấp nhận mọi dạng viết
tương đương. Lấy mô hình ra tự chấm thì con số chỉ đo được sự tự tin của nó.

| Model | Chế độ | MAE101 | MAI391 | MAS291 | MAD101 | Tổng | Thời gian |
|---|---|---|---|---|---|---|---|
| 3b | hỏi thẳng | 25,0% | 0,0% | 25,0% | 41,7% | **22,9%** | 7,1 s/bài |
| 3b | suy luận từng bước | 50,0% | 33,3% | 50,0% | 33,3% | **41,7%** | 34,3 s/bài |
| 7b | hỏi thẳng | 58,3% | 25,0% | 33,3% | 58,3% | **43,8%** | 6,4 s/bài |

Cho nghĩ từng bước gần như gấp đôi tỉ lệ đúng nhưng chậm gấp 5 lần, và vẫn dưới 50%.
Model 7b hỏi thẳng (43,8%) ngang với model 3b phải nghĩ từng bước (41,7%) — nhưng
nhanh hơn 5 lần, nên nếu chỉ cần lời giải thì đổi model rẻ hơn đổi cách hỏi.

MAI391 (ma trận, gradient, PCA) là môn model yếu nhất ở cả hai cỡ: 3b hỏi thẳng
đúng 0/12, 7b được 3/12.

Đây là lý do tồn tại của cả tầng kiểm chứng: **phần tính toán giao cho SymPy, mô
hình chỉ lo diễn đạt**. Một chatbot bọc API, dù prompt khéo tới đâu, cũng đang đứng
ở mốc 23–42% này.

---

## EXP-7a — bỏ tầng kiểm chứng ký hiệu thì sao

```
python scripts/exp7_llm_judge.py --pairs 40
```

160 cặp cân bằng (80 bài làm đúng, 80 bài làm sai có nhãn), cùng một bộ dữ liệu cho
cả hai bộ chấm:

| Bộ chấm | Chính xác | Báo ĐÚNG cho bài SAI | Báo SAI cho bài ĐÚNG |
|---|---|---|---|
| Qwen 2.5 3b làm giám khảo | 50,0% | 35,0% | 65,0% |
| Kiểm chứng ký hiệu | **100%** | **0%** | **0%** |

Mô hình chấm đúng đúng bằng tung đồng xu, và **nhận nhầm 35% bài sai thành đúng** —
sinh viên sẽ mang nguyên lỗi đó đi tiếp. Nó cũng bác nhầm 65% bài đúng, phần lớn vì
không chấp nhận dạng viết tương đương (`x**3/3 + C` và `(1/3)x³ + C`).

Ghi chú về cách dựng bộ dữ liệu: lỗi ở mức BƯỚC và lỗi giữ nguyên giá trị (quên
`+ C`) bị loại khỏi tập "sai", vì thí nghiệm chỉ nộp đáp án cuối và hệ thống cố ý
chấm những ca đó là đúng giá trị rồi gắn mã lỗi riêng. Bản đầu để lẫn vào làm bộ
chấm ký hiệu trông như "bỏ sót 3,8%" trong khi nó chấm đúng theo đúng thiết kế.

---

## EXP-7b — bỏ RAG khỏi prompt sinh gợi ý

```
python scripts/exp8_leakage.py --per-subject 5 --out experiments/exp7/rag_on.json
python scripts/exp8_leakage.py --per-subject 5 --no-rag --out experiments/exp7/rag_off.json
python scripts/exp7_rag_ablation.py
```

80 lượt gợi ý mỗi cấu hình, cùng bộ đề, cùng model (qwen2.5:3b-instruct):

| Cấu hình | Lộ đáp án | Về template | Lượt TB | Độ dài TB | Bám giáo trình |
|---|---|---|---|---|---|
| Có RAG | 0,0% | 1,2% | 1,09 | 125 ký tự | 8% |
| Không RAG | 0,0% | 2,5% | 1,10 | 105 ký tự | 8% |

**Đây là một kết quả âm tính, và nó đáng báo cáo.** Chỉ số "bám giáo trình" đếm tỉ lệ
gợi ý dùng lại ít nhất một thuật ngữ có trong đoạn được truy xuất. Ở cấu hình *không
RAG*, đoạn trích được truy xuất lại sau khi đã sinh gợi ý, chỉ để đối chứng — model
chưa hề nhìn thấy nó. Hai bên bằng nhau ở 8% nghĩa là: **gợi ý sinh khi CÓ đoạn giáo
trình trong prompt không dùng thuật ngữ của đoạn đó nhiều hơn gợi ý chưa từng thấy
nó.** Model 3b về cơ bản bỏ qua đoạn trích và viết theo mã lỗi đã chẩn đoán.

Kết luận có phạm vi hẹp: **ở cỡ model này, RAG trong khâu sinh GỢI Ý không đáng giá
tiền** — vẫn phải trả chi phí truy xuất mỗi lượt. Nó không nói gì về RAG ở khâu `/ask`
(hỏi lý thuyết), nơi đoạn trích chính là câu trả lời và không có nguồn nào thay được.

Tỉ lệ về template nhích từ 1,2% lên 2,5% khi bỏ RAG, nhưng trên 80 lượt thì chênh lệch
đó là 1 lượt — không kết luận được gì.

**Độ trễ không so ở đây.** Hai lần chạy cách nhau về thời điểm và tỉ lệ trúng cache
khác nhau, nên con số 6,2 s với 10,5 s trong `rag_ablation.json` đo tải máy chứ không
đo cấu hình. Muốn so độ trễ thì phải chạy xen kẽ hai cấu hình trong cùng một phiên.

Chất lượng sư phạm **không đo ở đây** — cần phiếu chấm tay (L2).

## EXP-2 — chất lượng bộ chấm

Đo trên tập lỗi có nhãn `data/errors/*_injected.jsonl` (nhãn sạch 100% vì lỗi do máy
cài vào), và sau này trên bài làm sai THẬT do sinh viên nộp.

Quy mô dữ liệu hiện tại — **8.732 mẫu lỗi có nhãn trên 91 mã lỗi**, sinh từ 4.955 đề
(155 chép tay + 4.800 sinh tự động):

| Môn | Đề chép tay | Đề sinh tự động | Kỹ năng được phủ | Mẫu lỗi có nhãn | Gán đúng mã |
|---|---|---|---|---|---|
| MAE101 | 41 | 1.200 | 16/21 | 4.350 | 97,2% |
| MAI391 | 35 | 1.200 | 16/16 | 1.951 | 99,7% |
| MAS291 | 36 | 1.200 | 15/15 | 1.432 | 100% |
| MAD101 | 43 | 1.200 | 17/18 | 999 | 100% |

MAE101 ban đầu chỉ sinh được đề giải tích (8/21 kỹ năng), phần đại số tuyến tính chỉ
có 20 bài chép tay. Tách các dạng bài đại số tuyến tính thành module dùng chung cho
cả MAE101 lẫn MAI391 — hai môn vốn đã dùng chung bảng mã lỗi `LA.*` — thì phủ lên
16/21 kỹ năng và mã `LA.*` mỏng nhất từ 1–2 mẫu lên 53 mẫu.

MAE101 từng chỉ đạt 72,3%; phần phân tích lỗi ở dưới nói rõ nó được kéo lên bằng
cách nào.

Mọi mã lỗi đều có mặt ở cả ba tập train/validation/test, mã hiếm nhất còn 9 mẫu.

Mã `LA.ROWOP.INVALID` (biến đổi hàng không hợp lệ) từng chỉ có ĐÚNG MỘT mẫu: nó là
lỗi ở mức TỪNG BƯỚC, mà đề sinh tự động khi đó chỉ có đáp án cuối. Sau khi cho bài
giải hệ sinh kèm lời giải mẫu dạng ma trận mở rộng (các bước khử Gauss), mã này có
52 mẫu.

```
python scripts/build_error_dataset.py MAE101      # và MAI391 / MAS291 / MAD101
```

In ra ba tỉ lệ, cố ý tách riêng vì ba mức độ khó khác hẳn nhau:

- **phát hiện** — bộ chấm biết bài làm là sai (dễ nhất, gần như phải đạt 100%);
- **gán nhãn** — gán được ít nhất một mã lỗi;
- **đúng mã** — trong các mã gán ra có đúng mã đã cài vào (khó nhất).

Hạn chế phải ghi rõ trong báo cáo: lỗi tổng hợp phân bố khác lỗi thật, nên con số ở
đây là chặn trên. Tập test thật (~200 bài làm gán nhãn tay) mới là thước đo cuối.

### EXP-2b — chỉ đúng BƯỚC SAI ĐẦU TIÊN

```
python scripts/exp2_step_detection.py
```

Phần trên chỉ đo ở mức đáp án cuối. Nhưng giá trị sư phạm nằm ở chỗ chỉ đúng chỗ sai
trong lời giải: gợi ý mức 3 nói "bước 2 của em chưa đúng" mà chỉ sai bước thì thành
vô nghĩa.

| Chỉ số | Kết quả |
|---|---|
| Phát hiện có chỗ sai trong chuỗi bước | 301/301 = 100% |
| Chỉ **đúng** bước đã bị cài lỗi | 301/301 = 100% |
| Báo oan trên lời giải mẫu (đúng) | 0/301 = 0% |

**Con số đẹp này có phạm vi rất hẹp, đừng trích dẫn trần trụi:** nó chỉ phủ 2 trong
89 mã lỗi (`MAE.ALG.STEP` và `LA.ROWOP.INVALID`), và cả hai đều là lỗi do máy cài
vào với dấu hiệu rõ ràng — một bước không tương đương bước trước. Bài làm thật có
những kiểu sai mờ hơn nhiều (viết tắt, nhảy bước, trình bày lộn xộn). Muốn có số
đáng tin thì phải chấm tay bài làm thật, đó là việc còn lại.

---

## Phân tích lỗi của chính hệ thống (L4)

```
python scripts/exp_error_analysis.py
```

"Gán đúng mã 72,3%" là một con số chết nếu không biết 27,7% còn lại hỏng vì cái gì.
Script này chấm lại toàn bộ 6.042 mẫu lỗi rồi phân loại NGUYÊN NHÂN.

### Lần chạy đầu

| Nguyên nhân | Số ca | Tỉ lệ |
|---|---|---|
| gán đúng mã | 5.314 | 88,0% |
| không gán nổi mã nào | 362 | 6,0% |
| có mã đúng nhưng kèm mã thừa | 262 | 4,3% |
| gán sang mã khác | 104 | 1,7% |
| **chấm bài SAI thành đúng** | **0** | **0%** |

Dòng cuối là dòng quan trọng nhất: **không có ca nào** bộ chấm nhận nhầm bài sai
thành đúng. Ba dòng trên là chuyện chẩn đoán chưa đủ tinh, còn dòng cuối mới là
chuyện mất lòng tin.

### Hai nguyên nhân lớn nhất và cách sửa

1. **`MAE.INT.DERIV_INSTEAD` — 224 ca không gán được mã.** Sinh viên lấy đạo hàm
   thay vì nguyên hàm; bộ chấm biết là sai nhưng không có luật nào nhận ra. Thêm
   một phép so: đáp án có bằng `f′(x)` không (bỏ qua hằng số cộng).
2. **`MAE.INT.LINEARITY` — 125 ca.** Tưởng `∫f·g = (∫f)(∫g)`. Thêm luật: nếu biểu
   thức dưới dấu tích phân là tích hai thừa số lấy được nguyên hàm, so đáp án với
   tích hai nguyên hàm đó.

Ngoài ra, 262 ca "kèm mã thừa" đều là lỗi DẤU nhưng mã `MAE.INT.CONSTFACTOR` lại
đứng trước `MAE.SIGN` trong danh sách — mà gợi ý mức 2 lấy mã đầu tiên, nên người
học nhận câu nhắc chệch hẳn cái bẫy đang mắc. Sửa bằng cách xếp mã CỤ THỂ lên trước.

### Kết quả sau khi sửa

| | Trước | Sau |
|---|---|---|
| MAE101 gán đúng mã | 72,3% | **95,8%** |
| Toàn bộ 4 môn | 88,0% | **91,9%** |
| Không gán nổi mã nào | 362 ca | **19 ca** |

Một lần thử sai đáng ghi lại: ban đầu tôi cho bộ chấm trả về **một** mã cụ thể
nhất thay vì kèm mã chung, và tỉ lệ gán đúng **tụt xuống 89,4%**. Lý do: nhìn vào
đáp án cuối thì "quên nhân du khi đổi biến" và "sai một hệ số hằng" cho ra đúng
một thứ — không có cách nào phân biệt. Bỏ bớt một mã là giả vờ chắc chắn hơn thực
tế. Giữ cả hai, xếp mã cụ thể trước, thì vừa đúng vừa dẫn đúng chỗ.

---

## EXP-3 — phân loại mã lỗi

```
python scripts/build_sft_dataset.py 120                    # dựng dữ liệu
python scripts/exp3_error_classification.py --limit 150    # baseline prompting
python scripts/kaggle_push.py                              # fine-tune LoRA trên GPU Kaggle
```

89 mã lỗi, 150 mẫu test. Chỉ số chính là **macro-F1** chứ không phải accuracy: dữ
liệu lệch nặng nên chỉ cần đoán vài mã phổ biến là accuracy đã khá, trong khi phần
lớn mã không bao giờ được nhận ra.

| Cấu hình | macro-F1 | accuracy | đúng tầng lỗi | bịa mã | trễ |
|---|---|---|---|---|---|
| Qwen 2.5 **3b** zero-shot | 0,358 | 38,0% | 48,7% | 1,3% | 4,7 s |
| Qwen 2.5 3b few-shot (6 ví dụ) | 0,343 | 35,3% | 49,3% | 0,0% | 5,3 s |
| Qwen 2.5 **7b** zero-shot | 0,415 | 46,7% | 63,3% | 2,7% | 5,8 s |
| Qwen 2.5 1.5B — chưa học | 0,098 | 15,7% | 29,3% | 16,0% | — |
| **Qwen 2.5 1.5B + QLoRA** | **0,921** | **95,0%** | **97,3%** | **0,0%** | — |

Ba điều đáng nói:

- **Few-shot không giúp gì, còn kém hơn zero-shot.** 6 ví dụ cho 89 lớp thì quá
  loãng, và model có xu hướng đoán quanh mấy mã vừa được cho xem.
- Model to gấp hơn hai lần chỉ thêm được 0,06 macro-F1. Prompting, dù ở cỡ nào,
  cũng không qua nổi 50% accuracy.
- **Model 1.5B sau khi fine-tune vượt xa model 7B chỉ prompting** (0,921 so với
  0,415) — đúng kết quả mà kế hoạch đặt cược vào. Model gốc 1.5B còn tệ hơn cả 3b
  (0,098, và 16% số lượt bịa ra mã không tồn tại); chính việc học 3.636 mẫu đã
  biến nó thành bộ phân loại dùng được, chứ không phải cỡ model.

Huấn luyện: QLoRA 4-bit, r = 16, 2 epoch trên Kaggle T4, ~2,3 giờ. Loss chỉ tính
trên phần đáp án (prompt dài ~900 token, đáp án vài token). Chi tiết lệnh chạy:
`docs/running.md`.

**Hạn chế phải ghi thẳng vào báo cáo, đừng để hội đồng phải hỏi:** tập test ở đây
là lỗi do MÁY CÀI VÀO, mỗi mã lỗi có một dấu hiệu khá cố định (quên `+ C`, thiếu
hệ số, đổi dấu). Một model fine-tune học được dấu hiệu đó là chuyện dễ hiểu, nên
0,921 là **chặn trên**. Trên bài làm thật — viết tắt, nhảy bước, sai nhiều thứ
cùng lúc — con số chắc chắn thấp hơn. Khoảng cách giữa fine-tune và prompting thì
đáng tin, vì cả hai đo trên cùng tập test đó.

65/80 mã lỗi trong tập test đạt F1 = 1,0. Số còn yếu nhất là những cặp mã dễ lẫn
nhau về mặt ngữ nghĩa: `MAI.SVM.SQUARED` và `MAI.SVM.HALFMARGIN` (cùng là sai công
thức lề, khác ở chỗ bình phương hay chia đôi), `MAI.GEO.NOSQRT` (quên căn) và
`MAD.COUNT.ORDER` (nhầm tổ hợp với chỉnh hợp).

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

### Kết quả — 70 câu hỏi sinh từ taxonomy kỹ năng, k = 5

```
python scripts/exp4_retrieval.py --k 5            # hỏi bằng tiếng Việt
python scripts/exp4_retrieval.py --k 5 --english  # hỏi bằng thuật ngữ tiếng Anh
```

| Ngôn ngữ câu hỏi | BM25 | dense (bge-m3) | hybrid (RRF) |
|---|---|---|---|
| Tiếng Việt | 0,167 | **0,595** | 0,310 |
| Tiếng Anh | 0,929 | 0,833 | **0,976** |

*(Recall@5; MRR theo thứ tự: 0,130 / 0,385 / 0,159 và 0,883 / 0,712 / 0,865.)*

**Kết quả ngược với giả định ban đầu:** hybrid KHÔNG phải lúc nào cũng tốt nhất. Với
câu hỏi tiếng Việt trên kho tiếng Anh, hybrid (0,310) kém hẳn dense đơn thuần (0,595)
— RRF trộn kết quả rác của BM25 vào và làm loãng thứ hạng tốt của bge-m3. Ngược lại,
khi hỏi bằng đúng ngôn ngữ của kho thì BM25 rất mạnh và hybrid nhỉnh hơn cả hai.

Hệ quả đã cài vào hệ thống (`RagIndex._fusion_mode`): câu hỏi tiếng Việt → chỉ dùng
nhánh dense; câu hỏi tiếng Anh (gồm cả truy vấn nội bộ bằng `skill.name_en`) → hợp
nhất hai nhánh.

Nhãn ở đây dựa trên khớp thuật ngữ tiếng Anh nên là **chặn dưới**: một đoạn giải
thích đúng khái niệm nhưng dùng từ khác ("u-substitution" thay vì "integration by
substitution") bị tính là sai. Bộ 100 cặp gán nhãn tay vẫn còn phải làm.

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

### Kết quả trên dữ liệu NGƯỜI HỌC THẬT — ASSISTments 2009–2010

```
kaggle datasets download -d kanishkjain03/assistments-skill -p data/kt --unzip
python scripts/exp5_kt.py --data assistments --students 2000 --seeds 3 --epochs 20
```

2.000 học sinh, 121.398 lượt, 116 kỹ năng, tỉ lệ đúng chung 65,3%. Làm sạch theo
đúng quy ước của các bài báo DKT: bỏ lượt không gắn kỹ năng, bỏ bài "scaffolding"
(`original = 0`, sinh ra sau khi học sinh làm sai — giữ lại là rò rỉ), sắp theo
`order_id`, bỏ học sinh dưới 10 lượt.

| Mô hình | AUC | ± | ACC | log loss | Literature báo cáo |
|---|---|---|---|---|---|
| majority | 0,500 | 0,000 | 0,668 | 0,637 | — |
| BKT (khớp tham số) | 0,729 | 0,009 | 0,719 | 0,564 | ~0,67–0,73 |
| **DKT** | **0,849** | 0,005 | 0,788 | 0,426 | ~0,80–0,86 |
| SAKT | 0,792 | 0,007 | 0,752 | 0,508 | ~0,79–0,85 |

**Đây mới là con số đáng trích dẫn**, và nó nằm đúng khoảng mà các bài báo gốc báo
cáo trên cùng bộ dữ liệu — tức là phần cài đặt (mã hoá tương tác, mặt nạ, chia theo
người học, tính AUC) không có lỗi ẩn nào. Khoảng cách DKT − BKT ở đây là **0,12**,
nhỏ hơn hẳn mức 0,21 đo trên học sinh mô phỏng, đúng như dự đoán ở phần cảnh báo
bên dưới.

**Cảnh báo khi trích dẫn con số MÔ PHỎNG:** học sinh mô phỏng có một năng lực NỀN dùng
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

Chạy lại trên **6 chương của cả 4 môn** (60 học sinh × 60 lượt × 2 seed mỗi chương)
để xem kết luận có lặp lại không — một chương thì luôn có thể là ngẫu nhiên:

| Chương | tuần tự | ZPD | ZPD + phủ kỹ năng |
|---|---|---|---|
| | *tỉ lệ đúng / số kỹ năng thạo* | | |
| MAD101 · đếm | 78% / 2,8 | 79% / 2,2 | 78% / **3,0** |
| MAD101 · đồ thị | 72% / **3,6** | 76% / 1,2 | 69% / 2,8 |
| MAE101 · tích phân | 65% / **4,9** | 70% / 4,0 | 57% / 4,7 |
| MAE101 · đại số tuyến tính | 69% / **3,5** | 70% / 1,9 | 68% / 2,9 |
| MAI391 · phân rã ma trận | 71% / 2,1 | 76% / 1,0 | 64% / **3,0** |
| MAS291 · phân phối | 78% / 2,8 | 77% / 2,5 | 76% / **3,9** |

Lặp lại rất đều: **ZPD cho tỉ lệ đúng cao nhất ở 5/6 chương, nhưng thạo ít kỹ năng
nhất ở 5/6 chương.** Chỗ nó tệ nhất là chương đồ thị MAD101 (1,2 so với 3,6) và
chương phân rã ma trận MAI391 (1,0 so với 2,1) — đều là chương có vài kỹ năng khó
hẳn so với phần còn lại, nên ZPD né luôn những kỹ năng đó.

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

Chạy lại với Qwen 2.5 **7b** (80 ca mỗi cấu hình) để xem cỡ model có giúp không:

| Model | Lộ khi không guardrail | Lộ khi prompt có đáp án | Có guardrail |
|---|---|---|---|
| qwen2.5 3b | 6,2% | 8,3% | 0% |
| qwen2.5 7b | 5,0% | 7,5% | 0% |

Model to hơn gấp đôi chỉ giảm tỉ lệ lộ được hơn một điểm phần trăm. **Đổi model
không thay được guardrail** — đây là lý do lớp phòng vệ phải nằm ngoài model.

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
