# Kịch bản video demo (4–5 phút)

**Quay sẵn, không demo trực tiếp.** Lý do ghi thẳng vào báo cáo: buổi bảo vệ phụ
thuộc mạng, tunnel và model là tự chuốc rủi ro không cần thiết. Mở video, rồi để
hệ thống chạy thật ở máy như phương án hai.

Chuẩn bị trước khi quay:

```bash
python scripts/rag_coverage.py                                   # ĐỌC TRƯỚC, xem bên dưới
python -m pytest -q                                              # 784 test, ~75 giây

LLM_HINTS=1 python -m uvicorn src.api.app:create_app --factory --port 8000   # cửa sổ 1
cd web && npm run dev                                            # cửa sổ 2
ollama serve                                                     # cửa sổ 3 (tuỳ chọn)
```

**Đọc kết quả `rag_coverage.py` trước khi quay.** Nó in ra chương nào chưa có giáo
trình. Hiện script in "Mọi chương đều có tài liệu để trả lời. Demo được." Vẫn phải đọc nó
trước mỗi lần quay: thêm hay bớt tài liệu là độ phủ đổi, và phát hiện lúc đang quay
thì muộn. Script này tồn tại vì một buổi demo đã thất bại đúng vì chuyện đó.

Phóng to chữ terminal lên cỡ 16–18pt, tắt thông báo hệ thống, dùng cửa sổ 1600×900.
Trên web, chọn chủ đề **Trắng** ở cột phải — nền đen quay video hay bị nhiễu khối.

---

## Cảnh 0 — Mở đầu (20 giây, nói trên nền slide tiêu đề)

> "Đây là hệ thống gia sư toán cho bốn môn MAE101, MAD101, MAI391, MAS291. Điểm
> khác với việc hỏi ChatGPT nằm ở một câu: **mô hình ngôn ngữ trong hệ thống này
> không có quyền quyết định đúng hay sai.**"

Chiếu luôn hai con số đo được, để khán giả biết vì sao:

| Qwen 2.5 3b tự giải toán | 22,9% đúng |
| Qwen 2.5 3b tự chấm bài | 50,0% đúng |
| Kiểm chứng ký hiệu chấm | 100% đúng |

---

## Cảnh 1 — Chấm đúng mọi cách viết (40 giây)

```bash
python scripts/demo_full.py --only 1
```

> "Cùng một bài tích phân, ba cách viết khác hẳn nhau về mặt chuỗi ký tự — kể cả
> dạng khai triển hết ra. Hệ thống chấm đúng cả ba, vì nó **đạo hàm ngược lại**
> rồi so với đề, chứ không so chuỗi."

Dừng ở dòng cuối: bài sai được gắn mã lỗi `MAE.INT.CONSTFACTOR`.

---

## Cảnh 2 — Kiểm chéo độc lập (35 giây)

```bash
python scripts/demo_full.py --only 2
```

> "Xác suất thì đối chứng bằng Monte Carlo 400 nghìn lần mô phỏng. Bài đếm thì đối
> chứng bằng liệt kê vét cạn. Hai cách tính khác hẳn bản chất mà ra cùng một số —
> nếu lệch, bài đó bị loại khỏi ngân hàng đề ngay từ lúc sinh."

---

## Cảnh 3 — Chỉ đúng bước sai (40 giây)

```bash
python scripts/demo_full.py --only 3
```

> "Đáp án cuối của sinh viên này ĐÚNG, nhưng trong lời giải có một phép biến đổi
> hàng tính sai. Hệ thống chỉ đúng bước 2 — chỉ chấm đáp án cuối thì bỏ lọt hoàn
> toàn ca này."

---

## Cảnh 4 — Thang gợi ý và guardrail (60 giây) ⭐ cảnh quan trọng nhất

Mở web, `/practice`, nhập một đáp án sai, bấm "Gợi ý thêm" bốn lần liên tiếp.

> "Gợi ý cho dần: khơi gợi → nhắc khái niệm → cảnh báo đúng cái bẫy đang mắc → chỉ
> chỗ sai. Không mức nào nói đáp án."

Rồi chuyển sang terminal:

```bash
python scripts/demo_full.py --only 4
```

> "Còn đây là guardrail. Nó không tự phán xét câu nào là lộ đáp án — nó **nộp từng
> mảnh trong câu gợi ý cho chính bộ chấm** và hỏi: mảnh này có được chấm đúng
> không? Nhờ vậy mọi cách viết tương đương đều bị chặn như nhau."

Chốt bằng số: mô hình tự lộ đáp án 6,2% số lượt dù prompt không hề cho biết đáp
án; có guardrail thì về 0%. Đổi sang model 7b chỉ giảm còn 5,0% — **đổi model
không thay được guardrail**.

---

## Cảnh 5 — Chọn bài thích ứng, kèm mặt trái (45 giây)

```bash
python scripts/demo_full.py --only 5
```

> "Người mới thì nhận bài dễ. Người đã vững nhưng yếu phần đồ thị Euler thì… hệ
> thống **né** luôn phần đó, vì bài Euler lúc này quá khó so với vùng vừa sức. Đây
> là mặt trái của ZPD mà thực nghiệm đo được: nó cho trải nghiệm tốt nhất ở 5 trên
> 6 chương, nhưng phủ kỹ năng kém nhất cũng ở 5 trên 6 chương. Thêm tiêu chí phủ
> kỹ năng thì kéo lại được."

Nói thẳng mặt trái là có chủ ý — hội đồng sẽ hỏi câu này, trả lời trước bằng số
liệu tốt hơn là để bị hỏi.

---

## Cảnh 6 — Hỏi lý thuyết: ba tình huống khác nhau (60 giây)

Mở web, trang **Hỏi lý thuyết**. Ba câu, theo đúng thứ tự này — chúng cho thấy hệ
thống phân biệt được ba tình huống mà một chatbot thường gộp làm một.

**1. Trong phạm vi, có tài liệu** — bấm nút "Chu trình Euler là gì?"

> "Trả lời kèm nguồn: tên file, chương, số trang. Em tự kiểm được."

**2. Ngoài phạm vi** — gõ "cách nấu phở bò ngon"

> "Ngoài bốn môn thì nói thẳng là không có, không đoán bừa. Ngưỡng nhận biết lấy
> theo độ tương đồng thật với kho giáo trình, không phải một luật từ khoá."

**3. Đúng chủ đề, chương từng KHÔNG có tài liệu** — môn MAS291, gõ "khoảng tin
cậy là gì?" rồi "p-value nghĩa là gì?"

> "Hai câu này trước đây hệ thống không trả lời được: kho MAS291 chỉ có 2 trong 8
> chương, và nó là môn duy nhất không có sách giáo trình nào để bù. Em bổ sung
> OpenStax *Introductory Statistics 2e* — sách mở giấy phép Creative Commons, phủ
> đúng sáu chương còn thiếu. Nguồn và giấy phép ghi trong báo cáo."

Nhấn vào hai điểm, vì đây là chỗ hội đồng sẽ hỏi:

> "Thứ nhất: **trước khi có sách, hệ thống nói thẳng là chưa có tài liệu chương
> đó**, chứ không trả về một đoạn của chương khác. Em đo được tỉ lệ 'trả lời trôi
> chảy nhưng sai chủ đề' là 20%, và đưa về 0%. Với một gia sư thì trả bừa là hành
> vi tệ nhất, vì người học không có cách nào biết mà đề phòng.
>
> Thứ hai: **truy xuất đúng đoạn vẫn chưa đủ**. Model 3b từng viết 'p-value là xác
> suất để H₀ đúng' — sai thống kê kinh điển, mà câu đọc rất trôi. Em phải chốt bảng
> thuật ngữ Việt–Anh và hai luật miền vào prompt mới hết lỗi đó."

Nếu còn thời gian, mở `scripts/rag_coverage.py` chạy trước mặt hội đồng — nó in ra
chương nào có tài liệu, chương nào không. Cho thấy mình **biết** chỗ trống của mình.

---

## Cảnh 7 — Khi mất mạng (25 giây)

Tắt Ollama, làm lại một lượt xin gợi ý.

> "Model chết thì gợi ý rơi về câu mẫu, hệ thống vẫn chạy. Ba lớp dự phòng: vLLM
> trên Kaggle, Ollama ở máy, rồi cache. Buổi bảo vệ không bao giờ kẹt vì model."

---

## Cảnh 8 — Kết (25 giây)

Chiếu `docs/results.md` và chạy:

```bash
python -m pytest -q          # 669 test, ~60 giây
```

> "Mọi con số trong báo cáo sinh tự động từ dữ liệu thô, không gõ tay. Và 669 test
> chạy được mà không cần GPU, không cần mạng, không cần model."

---

## Câu hỏi dự kiến và câu trả lời ngắn

| Câu hỏi | Trả lời |
|---|---|
| Khác gì ChatGPT? | Mô hình không được quyền chấm. Số liệu: nó tự chấm đúng 50%, kiểm chứng ký hiệu 100% |
| Sao không dùng GPT-4? | Ràng buộc chi phí và chủ quyền dữ liệu; đóng góp nằm ở kiến trúc, không ở model. Và đo được: đổi 3b→7b chỉ giảm tỉ lệ lộ đáp án 6,2%→5,0% |
| Làm sao biết gợi ý tốt? | Chống lộ đáp án đo tự động (EXP-8). Chất lượng sư phạm thì cần người chấm — phiếu đã chuẩn bị, **chưa chấm xong** |
| Dữ liệu ít vậy đánh giá sao tin được? | Knowledge tracing đo trên ASSISTments thật, AUC nằm đúng khoảng literature. Phần chẩn đoán lỗi thì thừa nhận là chặn trên, chưa có bài làm sai thật |
| Mở rộng sang môn khác thế nào? | Thêm một verifier + taxonomy kỹ năng; tầng trên không đổi. Bằng chứng: mã `LA.*` dùng chung cho MAE101 và MAI391 |
| Em gặp khó khăn gì? | Ba kết quả ngược kỳ vọng, xem mục 7.2 báo cáo: hybrid search thua dense khi hỏi khác ngôn ngữ, ZPD mất độ phủ, few-shot kém zero-shot |
