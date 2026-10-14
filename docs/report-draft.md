# AI Tutor for Mathematics Learning — bản thảo báo cáo

*Bản thảo do Claude soạn, số liệu lấy từ `docs/results.md` (sinh tự động). Chỗ nào
còn thiếu dữ liệu người thật đều ghi rõ là thiếu, đừng xoá những chỗ đó đi.*

---

# Chương 1. Mở đầu

## 1.1. Bối cảnh và vấn đề

Sinh viên năm nhất, năm hai ở FPT University học bốn môn toán nền tảng: MAE101
(toán kỹ thuật), MAD101 (toán rời rạc), MAI391 (toán cho học máy), MAS291 (xác
suất thống kê). Khi bí bài, các em hỏi ChatGPT hoặc các trợ lý tương tự. Cách này
có hai vấn đề mà bất kỳ ai dạy toán cũng thấy ngay:

**Thứ nhất, mô hình ngôn ngữ giải toán không đáng tin.** Đo trực tiếp trong đồ án
này: Qwen 2.5 3b giải đúng **22,9%** số bài trong ngân hàng đề (41,7% nếu cho suy
luận từng bước, nhưng chậm gấp 5 lần); bản 7b được 43,8%. Tệ hơn, khi bắt chính mô
hình chấm bài, nó chấm đúng **50%** — ngang tung đồng xu — và **nhận nhầm 35% bài
sai thành bài đúng**. Sinh viên tin vào đó sẽ mang nguyên lỗi đi tiếp.

**Thứ hai, trả lời thẳng đáp án không phải là dạy.** Một gia sư giỏi hỏi ngược lại,
chỉ chỗ sai, để người học tự sửa. Mô hình ngôn ngữ thì mặc định "giúp" tối đa: đo
được trong đồ án này, ngay cả khi prompt KHÔNG hề chứa đáp án, mô hình vẫn tự giải
ra rồi nói luôn đáp án ở **6,2%** số lượt xin gợi ý.

## 1.2. Mục tiêu

Xây dựng một hệ thống gia sư toán chạy hoàn toàn bằng mô hình mã nguồn mở trên máy
cá nhân, trong đó **mô hình ngôn ngữ không được quyền quyết định đúng/sai**, mà chỉ
lo phần diễn đạt. Phần phán xét giao cho kiểm chứng ký hiệu.

## 1.3. Ba đóng góp

| Đóng góp | Bằng chứng định lượng |
|---|---|
| Kiểm chứng neuro-symbolic có kiểm chéo độc lập | chấm đúng **100%** trên 160 cặp cân bằng, trong khi mô hình ngôn ngữ chỉ 50% |
| Thang gợi ý chống lộ đáp án, đo được bằng máy | mô hình tự lộ 6,2% → guardrail đưa về **0%**, giá 6/96 lượt viết lại |
| Mô hình năng lực + chọn bài thích ứng | DKT **AUC 0,849** trên ASSISTments thật; 5 chiến lược chọn bài so trên 6 chương |

Phụ thêm, và là kết quả mạnh nhất về mặt học máy: **bộ phân loại mã lỗi fine-tune
trên model 1,5 tỉ tham số đạt macro-F1 0,921, vượt xa model 7 tỉ tham số chỉ
prompting (0,415)**.

## 1.4. Phạm vi

Bốn môn, mỗi môn 3–4 mảng kiến thức, tổng 70 kỹ năng. **Loại trừ rõ ràng**: chứng
minh hình thức tự do, chuỗi Fourier, tích phân bội, ANOVA nhiều nhân tố.

---

# Chương 2. Cơ sở lý thuyết và công trình liên quan

## 2.1. Hệ dạy học thông minh (ITS)

Bốn thành phần kinh điển: mô hình lĩnh vực, mô hình người học, mô hình sư phạm,
giao diện. Đồ án này ánh xạ lần lượt vào `src/verify/`, `src/kt/`, `src/tutor/`,
`web/` + `src/bot/`.

## 2.2. Theo dõi năng lực (Knowledge Tracing)

- **BKT** (Corbett & Anderson, 1995): bốn tham số mỗi kỹ năng, giải thích được cho
  người học xem. Điểm yếu: mỗi kỹ năng một biến độc lập.
- **DKT** (Piech et al., 2015): mạng hồi tiếp, một trạng thái ẩn cho cả chuỗi.
- **SAKT** (Pandey & Karypis, 2019): thay hồi tiếp bằng self-attention.

Cả ba đều được cài lại trong đồ án và đo trên cùng dữ liệu.

## 2.3. Mô hình ngôn ngữ cho toán và tool-augmented reasoning

Hướng tiếp cận "để mô hình gọi công cụ tính toán" (PAL, Toolformer, Qwen-Math)
mạnh hơn hẳn để mô hình tự tính. Đồ án đi xa hơn một bước: **công cụ không chỉ để
tính, mà là bộ phán xét cuối cùng** — mô hình không có quyền phủ quyết.

## 2.4. Dạy theo lối Socrates và chống lộ đáp án

Điểm thiếu trong literature: hầu hết công trình đánh giá "chất lượng gợi ý" bằng
rubric người chấm. Đồ án này thêm một định nghĩa **đo được bằng máy**: một gợi ý
làm lộ đáp án khi có mảnh nào trong nó mà nộp lên bộ chấm sẽ được chấm ĐÚNG.

---

# Chương 3. Phân tích yêu cầu và thiết kế hệ thống

## 3.1. Kiến trúc

Ba tầng: giao diện (web Next.js + bot Telegram) → điều phối (FastAPI) → các module
nghiệp vụ (kiểm chứng, gia sư, RAG, mô hình năng lực). Chuỗi mô hình ba lớp
vLLM → Ollama → cache.

Điểm đáng nói khi bảo vệ: **web và bot không chứa một dòng logic sư phạm nào** —
không tự chấm, không giữ đáp án, không tự quyết mức gợi ý. Nhờ vậy hai kênh luôn
cho cùng kết quả trên cùng bài làm, và log của chúng nằm chung một bảng.

## 3.2. Lược đồ cơ sở dữ liệu

`users`, `sessions`, `attempts`, `hints`, `mastery`. Bảng `attempts` lưu nguyên
văn bài làm, kết quả kiểm chứng dạng JSON, bước sai đầu tiên và mã lỗi — đủ để
sau này phân tích lại mà không phải chấm lại.

## 3.3. Luồng dữ liệu một lượt làm bài

bài làm → kiểm chứng → chẩn đoán mã lỗi → chọn mức gợi ý → sinh gợi ý → guardrail
→ cập nhật năng lực → chọn bài kế tiếp.

---

# Chương 4. Xây dựng dữ liệu

## 4.1. Quy mô

| Loại | Số lượng |
|---|---|
| Kỹ năng (knowledge component) | 70, có đồ thị tiên quyết, **phủ 70/70 bằng đề** |
| Mã lỗi | 97 (mã `LA.*` dùng chung MAE101 và MAI391) |
| Đề chép tay từ giáo trình | 155 |
| Đề sinh tự động | 4.800 |
| Mẫu lỗi có nhãn | 7.978 (trung vị 63 mẫu mỗi mã, mỏng nhất 12) |
| Đoạn giáo trình trong kho RAG | 10.566, trong đó 485 đoạn mục lục/chỉ mục bị loại |

Độ phủ kỹ năng đạt 70/70 sau **hai** lần bịt lỗ, và cả hai lần đều do một phép đo
phát hiện chứ không do đọc code: lần đầu là mảng đại số tuyến tính của MAE101 (8/21 →
16/21), lần sau là hai chương giới hạn và đạo hàm (16/21 → 21/21) mà cây nội dung phơi
ra khi nó hiện số đề từng chương.

**Độ phủ kho giáo trình thì chưa đều, và phải nói rõ:**

| Môn | Chương có slide riêng | Sách giáo trình chung |
|---|---|---|
| MAE101 | 7/7 | OpenStax Calculus 1–2, 3.160 đoạn |
| MAD101 | 7/7 | Rosen 7th ed., 4.730 đoạn |
| MAI391 | 2/8 | Deisenroth, 1.253 đoạn — đủ bù |
| MAS291 | **2/8** | **không có** (2 đoạn lẻ) |

MAS291 là lỗ thật: sáu chương không có tài liệu nào để truy xuất. Hệ thống trả lời
"chưa có tài liệu chương này" thay vì đoán, nhưng đó vẫn là trống dữ liệu, không phải
một tính năng.

## 4.2. Sinh đề tự động có kiểm chứng

Mỗi dạng bài là một template random hoá tham số; đáp án **không viết tay** mà lấy
từ chính hàm tham chiếu của bộ chấm. Quan trọng nhất: **mọi bài sinh ra phải tự
chấm đúng mới được nhận vào ngân hàng**. Với MAS291, hàng rào này bao gồm cả đối
chứng Monte Carlo, nên một template đặt tham số phi lý không thể lọt.

## 4.3. Sinh lỗi có chủ đích

`error_injector.py` biến lời giải đúng thành lời giải sai theo đúng một mã lỗi,
nên nhãn sạch 100%. Có một chốt chặn đáng nói: `is_genuinely_wrong()` hỏi ngược
lại bộ chấm xem đáp án vừa bịa ra có thật sự sai không — vì đã gặp ca cài lỗi "sai
hệ số" vào `∫e^(-x)dx` mà kết quả vẫn đúng (hàm mũ là hàm riêng của phép đạo hàm).

## 4.4. Hạn chế của dữ liệu

**Chưa có bài làm sai thật nào của sinh viên.** Lỗi tổng hợp có dấu hiệu cố định
hơn lỗi thật (viết tắt, nhảy bước, sai nhiều thứ cùng lúc), nên mọi con số về chẩn
đoán trong báo cáo này là **chặn trên**.

---

# Chương 5. Phương pháp

## 5.1. Kiểm chứng theo TÍNH CHẤT, không so dạng viết

| Loại bài | Kiểm bằng |
|---|---|
| Nguyên hàm | đạo hàm ngược lại rồi so với biểu thức dưới dấu tích phân |
| Vector riêng | `A·v = λv`, chấp nhận mọi bội vô hướng |
| Ma trận nghịch đảo | `A·B = I` |
| Hệ tuyến tính | thế ngược `A·x − b = 0`, chấp nhận mọi tham số hoá |
| Logic | `satisfiable(¬(A ↔ B))` là False |
| Hệ thức truy hồi | tính lặp n bước đầu |

Nền chung: lấy mẫu số để **bác bỏ** trước (nhanh, gần như không nhầm), rút gọn ký
hiệu có giới hạn thời gian để **xác nhận** sau.

## 5.2. Kiểm chéo độc lập

MAS291 đối chứng bằng Monte Carlo 400.000 lần (khớp trong 4 sai số chuẩn); MAD101
đối chứng bài đếm bằng liệt kê vét cạn, bài truy hồi bằng tính lặp. Hai cách khác
hẳn bản chất mà ra cùng kết quả thì độ tin cậy rất cao.

## 5.3. Thang gợi ý 6 mức và guardrail

Mức 0 khơi gợi → 1 nhắc khái niệm → 2 cảnh báo bẫy → 3 chỉ bước sai → 4 sửa và
giải thích → 5 lời giải đầy đủ. Ba lớp chống lộ đáp án, mỗi lớp đo riêng được
(chi tiết ở EXP-8).

## 5.4. Mô hình năng lực và chọn bài

BKT (khớp tham số bằng lưới 400 bộ) → DKT → SAKT. Điểm chọn bài:

```
score = w₁·(kỹ năng yếu) + w₂·ZPD(p) + w₃·(sẵn sàng tiên quyết)
      + w₄·(phủ kỹ năng) − w₅·(phạt lặp lại)
```

Tiêu chí **phủ kỹ năng** được thêm vào SAU khi EXP-6 cho thấy ZPD thuần đào sâu
một kỹ năng và bỏ quên cả chương.

---

# Chương 6. Cài đặt

Python 3.11, SymPy/NetworkX/SciPy/PyTorch, FastAPI + SQLite, Next.js 15, aiogram.
20.696 dòng Python, **669 test** chạy hết trong ~60 giây, không cần GPU, không cần
mạng, không cần mô hình — mọi thứ phụ thuộc bên ngoài đều có bản giả trong test.

Fine-tune LoRA chạy trên Kaggle T4 (~2,3 giờ), tự động hoá qua API: dựng dữ liệu ở
máy → đẩy kernel → tải kết quả. Chi tiết trong `docs/running.md`.

---

# Chương 7. Thực nghiệm và đánh giá

Toàn bộ số liệu: `docs/results.md` (sinh tự động từ `experiments/`), diễn giải và
hạn chế từng thí nghiệm: `docs/evaluation-protocol.md`.

## 7.1. Bảng tổng hợp

| Thí nghiệm | Kết quả chính |
|---|---|
| EXP-1 mô hình tự giải toán | 3b: 22,9% → 41,7% (có suy luận); 7b: 43,8% |
| EXP-2 chất lượng bộ chấm | phát hiện sai **100%**; gán đúng mã 95,8–100% |
| EXP-2b chỉ đúng bước sai | 301/301, không báo oan lần nào (phạm vi hẹp) |
| EXP-3 phân loại mã lỗi | prompting 7b 0,415 → **LoRA 1.5B 0,921** |
| EXP-4 truy xuất giáo trình | Recall@5 0,595 (hỏi tiếng Việt) / 0,976 (tiếng Anh) |
| EXP-5 theo dõi năng lực | **ASSISTments thật**: DKT 0,849 > SAKT 0,792 > BKT 0,729 |
| EXP-6 chọn bài | ZPD được trải nghiệm, mất độ phủ — lặp lại ở 5/6 chương |
| EXP-7a bỏ kiểm chứng ký hiệu | LLM chấm đúng 50%, ký hiệu 100% |
| EXP-8 chống lộ đáp án | 6,2% → **0%**, đổi sang model 7b chỉ giảm còn 5,0% |

## 7.2. Ba kết quả NGƯỢC với kỳ vọng ban đầu

Ghi lại đầy đủ, vì đây là phần nói lên nhiều nhất về hệ thống:

1. **Hybrid search không phải lúc nào cũng tốt nhất.** Câu hỏi tiếng Việt trên kho
   tiếng Anh: dense 0,595 nhưng hybrid chỉ 0,310 — RRF trộn kết quả rác của BM25
   vào làm loãng. Hệ quả: tìm kiếm giờ tự chọn nhánh theo ngôn ngữ câu hỏi.
2. **ZPD không thắng toàn diện.** Tỉ lệ đúng cao nhất ở 5/6 chương nhưng thạo ít
   kỹ năng nhất cũng ở 5/6 — nó bám kỹ năng đang cho xác suất ≈ 0,75 rồi né hẳn
   những kỹ năng còn quá khó.
3. **Few-shot kém hơn zero-shot** khi phân loại 89 mã lỗi (0,343 so với 0,358):
   6 ví dụ cho 89 lớp quá loãng, và mô hình đoán quanh mấy mã vừa được xem.

## 7.3. Phân tích lỗi của chính hệ thống

Chấm lại 6.042 mẫu rồi phân loại nguyên nhân cho thấy hai lỗ hổng lớn nhất đều là
"biết là sai nhưng không gán nổi mã nào": lấy đạo hàm thay vì nguyên hàm (224 ca)
và tưởng `∫f·g = (∫f)(∫g)` (125 ca). Thêm hai luật nhận diện → MAE101 từ 72,3% lên
**95,8%**.

Một lần thử sai đáng ghi: cho bộ chấm trả về **một** mã cụ thể nhất thay vì kèm mã
chung, tỉ lệ **tụt xuống 89,4%** — vì nhìn đáp án cuối thì "quên nhân du khi đổi
biến" và "sai một hệ số hằng" là một. Bỏ bớt mã là giả vờ chắc chắn hơn thực tế.

---

# Chương 8. Kết luận và hạn chế

## 8.1. Kết luận

Hệ thống chứng minh được ba điều: (i) giao phần phán xét cho kiểm chứng ký hiệu
làm độ tin cậy nhảy từ 50% lên 100% trên cùng bộ dữ liệu; (ii) chống lộ đáp án là
thứ **đo được**, và phải nằm ngoài mô hình chứ không trông vào việc đổi mô hình to
hơn; (iii) một mô hình 1,5 tỉ tham số fine-tune trên dữ liệu tự sinh vượt xa mô
hình 7 tỉ tham số chỉ prompting.

## 8.2. Hạn chế — viết đúng như đã đo

1. **Chưa có người dùng thật.** Mọi kết luận về chọn bài đo trên học sinh mô
   phỏng, tức là đo HÀNH VI THUẬT TOÁN chứ không phải hiệu quả học tập.
2. **Chưa có bài làm sai thật.** Mọi con số chẩn đoán là chặn trên.
3. **macro-F1 0,921 của LoRA là chặn trên**: tập test là lỗi máy cài vào với dấu
   hiệu cố định. Khoảng cách với prompting thì đáng tin vì cùng tập test.
4. **Kho giáo trình chưa phủ hết syllabus.** MAS291 chỉ có 2/8 chương và không có
   sách giáo trình chung để bù; sáu chương còn lại không có tài liệu nào. Hệ thống
   nói thẳng điều đó thay vì đoán, nhưng mọi câu hỏi về sáu chương ấy hiện không
   trả lời được. Đo bằng `scripts/rag_coverage.py`.
5. **Chứng minh hình thức** chỉ kiểm được cấu trúc, không kiểm được lập luận.
6. **Nguyên hàm sai khác hằng số nhân với hàm mũ** không phân biệt được bằng đạo
   hàm ngược, vì `e^x` là hàm riêng của phép đạo hàm.
7. **Từ điển thuật ngữ là bảng tra tay, không phải dịch máy.** 199 mục phủ các khái
   niệm cốt lõi của bốn môn; câu hỏi dùng thuật ngữ ngoài bảng sẽ quay về đúng hành
   vi cũ (dense đơn thuần, dễ lệch chủ đề). Mở rộng sang môn khác cần bổ sung bảng.
8. **Phân quyền quản trị dùng MỘT khoá dùng chung**, không có tài khoản, không có
   nhiều mức quyền, không ghi vết ai đã xem gì. Đủ cho mạng nội bộ của một đồ án;
   đưa ra Internet thật thì phải thay bằng đăng nhập có tài khoản.
9. **Lỗi ở mức BƯỚC chưa đo được trên dữ liệu thật**, vì đề sinh tự động phần lớn
   chỉ có đáp án cuối. Một mã lỗi đã phải bỏ vì lý do này: `MAE.LIM.NOSIMPLIFY`
   không phân biệt được với `MAE.LIM.INDET_ZERO` nếu chỉ nhìn đáp án cuối.

## 8.3. Hướng phát triển

Thu log người dùng thật qua bot Telegram rồi huấn luyện lại DKT trên đó (đường dẫn
và giao diện không đổi); thêm reranker cho RAG; OCR bài làm viết tay; mở rộng sang
môn thứ năm để kiểm chứng lại chi phí port.

---

# Phụ lục

- A. Danh sách 91 mã lỗi kèm mô tả và câu gợi ý
- B. 70 kỹ năng và đồ thị tiên quyết
- C. Ví dụ hội thoại đầy đủ trên cả ba kênh (CLI, web, Telegram)
- D. Bảng đối chiếu: mỗi con số trong báo cáo ↔ lệnh sinh ra nó
