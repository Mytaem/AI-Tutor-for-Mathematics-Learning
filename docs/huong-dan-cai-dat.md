# Hướng dẫn cài đặt đầy đủ

Tài liệu này viết cho người **dựng lại toàn bộ hệ thống từ đầu** trên một máy mới —
kể cả phần dựng lại dữ liệu và huấn luyện mô hình.

Ba tài liệu liên quan, chọn đúng cái bạn cần để đỡ mất thời gian:

| Bạn là | Đọc |
|---|---|
| chỉ cần **demo** hệ thống | [cho-nguoi-demo.md](cho-nguoi-demo.md) — nhanh hơn nhiều, bỏ qua phần dựng dữ liệu |
| **dùng** hệ thống (sinh viên, giảng viên) | [huong-dan-su-dung.md](huong-dan-su-dung.md) |
| **đọc và sửa code** | [kien-truc.md](kien-truc.md) |

---

## 0. Yêu cầu

| | Bắt buộc | Ghi chú |
|---|---|---|
| Python | **3.11** | 3.10+ chạy được; 3.13 chưa thử |
| Node.js | **20+** | chỉ cần cho giao diện web |
| RAM | 8 GB | 16 GB nếu chạy model 7B |
| Đĩa trống | ~12 GB | model Ollama chiếm phần lớn |
| GPU | **không cần** | toàn bộ phần phục vụ chạy CPU; chỉ fine-tune LoRA cần GPU, và việc đó làm trên Kaggle |

Hệ điều hành: đã chạy thật trên **Windows 11**. macOS/Linux dùng cùng lệnh, chỉ khác
cách kích hoạt môi trường ảo.

---

## 1. Lấy code và cài thư viện

```bash
git clone https://github.com/Mytaem/AI-Tutor-for-Mathematics-Learning.git
cd AI-Tutor-for-Mathematics-Learning

python -m venv .venv
.venv\Scripts\activate            # Windows
# source .venv/bin/activate       # macOS / Linux

pip install -r requirements.txt
```

**Cài đúng trình thông dịch.** Nếu máy có nhiều bản Python, dùng `python -m pip` thay
cho `pip` — `pip` có thể trỏ sang bản khác, và lúc đó thư viện cài vào một chỗ còn code
chạy ở chỗ khác. Kiểm:

```bash
python -c "import sys; print(sys.version, sys.executable)"
```

Kiểm ngay bước này đã xong chưa:

```bash
python -m pytest -q
```

Phải thấy **784 passed**, khoảng 60–120 giây. Bộ test này **không cần GPU, không cần
mạng, không cần model** — mọi thứ phụ thuộc bên ngoài đều có bản giả.

Test đỏ ở bước này thì dừng lại sửa, đừng đi tiếp.

---

## 2. Dữ liệu có sẵn trong git (không phải làm gì)

Những thứ này đã nằm trong kho, dùng được ngay:

| Thư mục | Nội dung |
|---|---|
| `data/skills/` | 70 kỹ năng của 4 môn + đồ thị tiên quyết |
| `data/items/` | 4.955 đề — 155 chép tay + 4.800 sinh tự động |
| `data/errors/` | bảng 97 mã lỗi + 7.978 mẫu lỗi có nhãn |
| `data/eval/` | phiếu chấm chất lượng gợi ý |

Chúng được commit vì **sinh lại được y hệt từ seed**, và là một phần kết quả của đồ án.

---

## 3. Dựng kho giáo trình (bắt buộc cho phần Hỏi lý thuyết)

Đây là bước nặng nhất và dễ sai nhất.

### 3.1. Tải giáo trình

Đường dẫn và **giấy phép** của mọi tài liệu ghi ở [nguon-tai-lieu.md](nguon-tai-lieu.md).
Bản thân PDF không nằm trong git — vừa vì nặng, vừa vì có tài liệu bản quyền không được
phát tán lại.

Thả vào đúng thư mục, **môn học suy ra từ tên thư mục**:

```
data/raw/
├── MAE101/        ├── MAD101/
├── MAI391/        └── MAS291/
```

Hỗ trợ `.pdf`, `.docx`, `.pptx`, `.txt`, `.md`. File hỏng bị bỏ qua chứ không làm chết
cả lần nạp.

**Tối thiểu nên có cho MAS291**: OpenStax *Introductory Statistics 2e* (847 trang, CC
BY-NC-SA 4.0). Không có nó thì 6 trong 8 chương của môn không có tài liệu nào, vì MAS291
là môn duy nhất không có sách giáo trình chung khác bù.

### 3.2. Cài bộ mã hoá

```bash
# cài Ollama từ https://ollama.com
ollama serve              # giữ chạy ở một cửa sổ riêng
ollama pull bge-m3        # ~1,2 GB
```

**`bge-m3` cần cả khi chỉ TRA CỨU, không chỉ khi dựng kho.** Kho lưu vector của các đoạn
giáo trình, còn câu hỏi của người dùng phải mã hoá tại chỗ mỗi lần tra. Thiếu nó thì
`/ask` báo lỗi cấu hình và không trả lời được câu nào — nó cố ý **không** âm thầm rơi về
BM25, vì ở chế độ đó cơ chế từ chối câu ngoài phạm vi tắt hoàn toàn.

### 3.3. Dựng

```bash
python scripts/build_rag_index.py --dense
```

Mất khoảng **40 phút** trên CPU cho ~12.000 đoạn. Vector đã mã hoá được cache theo hash
nội dung, nên lần dựng sau chỉ mã hoá phần mới.

> ### ⚠ Đừng bỏ cờ `--dense`
>
> Không có embedding thì hệ thống **mất thang tương đồng**, và cơ chế từ chối câu hỏi
> ngoài phạm vi **tắt hoàn toàn**. Đo được trên 28 câu kiểm:
>
> | Kho | Đạt | Trả lời sai chủ đề | Câu ngoài phạm vi |
> |---|---|---|---|
> | chỉ BM25 | 68% | 32% | **lọt 3/3** |
> | có embedding | **100%** | **0%** | chặn 3/3 |
>
> Hỏi "cách nấu phở bò ngon" sẽ nhận về một đoạn giáo trình.

### 3.4. Kiểm

```bash
python scripts/rag_coverage.py
```

Script in ra **chương nào chưa có tài liệu**. Mục tiêu: *"Mọi chương đều có tài liệu để
trả lời."*

---

## 4. Dựng lại ngân hàng đề (tuỳ chọn)

Chỉ cần khi muốn sinh lại, hoặc khi thêm dạng bài mới.

```bash
python scripts/build_bank.py all 1200       # cả 4 môn, mỗi môn 1.200 đề
python scripts/build_bank.py MAE101 1200    # một môn
```

Mỗi đề sinh ra **phải tự chấm lại được** mới được nhận, nên số thực tế có thể ít hơn số
yêu cầu — script in cả hai con số.

Rồi dựng lại tập lỗi có nhãn:

```bash
python scripts/build_error_dataset.py MAE101   # và MAD101 / MAI391 / MAS291
```

Script in ba chỉ số: tỉ lệ **phát hiện** được bài sai, tỉ lệ **gán được nhãn**, và tỉ lệ
**gán đúng mã** đã cài vào. Con số thứ ba là thứ cần theo dõi.

> **Dựng lại dữ liệu thì phải KHỞI ĐỘNG LẠI API.** Ngân hàng đề và kho RAG nạp một lần
> lúc khởi động rồi giữ trong bộ nhớ. Triệu chứng hay gây hoang mang: script báo chương
> đã có 187 đề, mà `/syllabus` vẫn trả 0.

---

## 5. Model ngôn ngữ

Hệ thống thiết kế **ba lớp**, và nó chạy được cả khi không có lớp nào:

| Lớp | Khi nào dùng | Cấu hình |
|---|---|---|
| vLLM trên Kaggle | cần chất lượng cao nhất | `VLLM_URL=<url tunnel>` |
| **Ollama local** | mặc định, luôn có | `OLLAMA_MODEL=qwen2.5:7b-instruct` |
| Cache | lúc bảo vệ, không phụ thuộc mạng | `DEMO_MODE=1` |

```bash
ollama pull qwen2.5:7b-instruct     # ~4,7 GB — khuyến nghị
ollama pull qwen2.5:3b-instruct     # ~1,9 GB — nhanh gấp đôi, tiếng Việt kém hơn
```

**Không có model nào thì hệ thống vẫn chạy**: gợi ý rơi về câu template, phần Hỏi lý
thuyết trả nguyên đoạn giáo trình kèm nguồn. Kém mượt nhưng vẫn đúng — đây là đường lui
đã chuẩn bị sẵn, không phải phương án chữa cháy.

---

## 6. Giao diện web

```bash
cd web
npm install
npm run dev          # http://localhost:3000
cd ..
```

Trỏ sang API khác thì đặt `NEXT_PUBLIC_API_URL` (xem `web/.env.example`).

---

## 7. Chạy hệ thống

```bash
# cửa sổ 1 — Ollama (tuỳ chọn)
ollama serve

# cửa sổ 2 — API
set LLM_HINTS=1
set OLLAMA_MODEL=qwen2.5:7b-instruct
set ADMIN_TOKEN=khoá-bạn-tự-đặt
python -m uvicorn src.api.app:create_app --factory --port 8000

# cửa sổ 3 — web
cd web && npm run dev
```

Kiểm nhanh: mở http://localhost:8000/health — phải thấy đủ 4 môn và ~4.955 đề.

### Biến môi trường

| Biến | Mặc định | Tác dụng |
|---|---|---|
| `LLM_HINTS` | tắt | `1` để gợi ý do model diễn đạt (có guardrail) |
| `OLLAMA_MODEL` | `qwen2.5:3b-instruct` | đổi sang `7b` khi cần chất lượng |
| `VLLM_URL` | trống | endpoint vLLM; có thì ưu tiên hơn Ollama |
| `DEMO_MODE` | tắt | `1` chỉ đọc cache, không gọi model |
| `KT_MODEL` | `bkt` | `dkt` để dùng mạng hồi tiếp (cần `models/dkt/<môn>.pt`) |
| `DATABASE_URL` | `data/tutor.sqlite` | đổi file dữ liệu |
| **`CORS_ORIGINS`** | `localhost:3000` | origin được phép gọi API |
| **`ADMIN_TOKEN`** | trống | bật phần quản trị; **trống = tắt hoàn toàn** |

### Hai biến dễ quên nhất

**`CORS_ORIGINS`** — web ở cổng 3000 gọi API ở cổng 8000, với trình duyệt đó là hai
origin khác nhau. Thiếu cấu hình này thì **giao diện dựng ra đầy đủ nhưng không nút nào
chạy**, và trên trang không có thông báo lỗi gì. Mặc định đã phủ trường hợp chạy ở máy
mình; chỉ cần đặt khi đưa web ra tunnel hoặc máy khác.

Lỗi này từng lọt qua **cả 685 test** vì `TestClient` và `curl` không thi hành
same-origin policy — chỉ trình duyệt thật mới chặn. Thanh bên phải của web có đèn báo
kết nối chính vì chuyện đó.

**`ADMIN_TOKEN`** — mặc định phần quản trị **tắt**, không phải mở. Dữ liệu ở đó là bài
làm của người thật; "chưa cấu hình mà mở sẵn" là kiểu lỗ hổng tệ nhất vì không ai nhận
ra cho tới lúc muộn.

---

## 8. Telegram bot (tuỳ chọn)

```bash
# lấy token: mở Telegram, nhắn @BotFather, gõ /newbot
set TELEGRAM_TOKEN=<token>
python -m src.bot.main
```

Bot là **client mỏng** gọi API ở cổng 8000, không nhân bản logic. Nhờ vậy log từ bot và
web nằm chung một bảng, phân tích chung được, và cùng một bài làm cho cùng một kết quả.

Phải bật API trước.

---

## 9. Huấn luyện mô hình (tuỳ chọn)

### 9.1. DKT để phục vụ — chạy ở máy, ~3 phút, chỉ CPU

```bash
python scripts/train_dkt_for_serving.py       # cả 4 môn
set KT_MODEL=dkt
python -m uvicorn src.api.app:create_app --factory --port 8000
```

Lưu ra `models/dkt/<môn>.pt`. Thiếu file thì API **tự quay về BKT**, không lỗi.

Khác `scripts/exp5_kt.py` (huấn luyện để **đo**, có chia train/test): script này huấn
luyện để **phục vụ**, dùng toàn bộ dữ liệu. Hiện học từ học sinh mô phỏng, vì mô hình
phải nói về đúng tập kỹ năng của môn; khi có log người dùng thật thì huấn luyện lại trên
đó, đường dẫn và giao diện không đổi.

### 9.2. Fine-tune LoRA — cần GPU, chạy trên Kaggle

```bash
python scripts/build_sft_dataset.py 120     # dựng data/sft/{train,validation,test}.jsonl
python scripts/kaggle_push.py               # đẩy kernel, bật GPU + internet, chạy luôn
python scripts/kaggle_push.py --status
python scripts/kaggle_push.py --fetch       # tải log, adapter và metrics.json về
```

Cần `~/.kaggle/access_token` (Kaggle → Settings → API → Create New Token).

Kernel tự đo model gốc **trước** khi học rồi đo lại **sau**, bằng đúng cách tính macro-F1
của baseline chạy ở máy, nên hai con số so trực tiếp được.

Muốn chạy trên Colab thì dùng `scripts/train_lora_error_classifier.py` (có `--resume` vì
Colab hay ngắt phiên giữa chừng).

**Lưu ý mạng**: nếu `kaggle` treo ở bước kết nối, nhiều khả năng DNS trả địa chỉ IPv6
NAT64; `scripts/kaggle_push.py` đã ép IPv4 sẵn.

---

## 10. Chạy thí nghiệm

```bash
python scripts/exp1_solving.py                    # model tự giải toán
python scripts/exp2_step_detection.py             # phát hiện bước sai
python scripts/exp3_error_classification.py       # phân loại mã lỗi
python scripts/exp4_retrieval.py --k 5            # BM25 / dense / hybrid
python scripts/exp4b_ask_quality.py --compare     # hỏi đáp lý thuyết
python scripts/exp5_kt.py --subject MAE101        # BKT / DKT / SAKT
python scripts/exp6_selection.py                  # chiến lược chọn bài
python scripts/exp7_llm_judge.py --pairs 40       # bỏ tầng kiểm chứng ký hiệu
python scripts/exp7_rag_ablation.py               # bỏ RAG khỏi prompt gợi ý
python scripts/exp8_leakage.py --per-subject 6    # chống lộ đáp án (cần model)
python scripts/exp_error_analysis.py              # phân tích lỗi của hệ thống

python scripts/make_report_tables.py              # sinh docs/results.md từ experiments/
```

Kết quả thô ghi vào `experiments/<tên>/`. **Mọi bảng trong báo cáo sinh từ script, không
gõ tay** — nên đổi số liệu thì chạy lại `make_report_tables.py`.

---

## 11. Kiểm toàn bộ

```bash
python scripts/check_demo_ready.py    # gộp mọi phép kiểm, in việc còn thiếu kèm lệnh
python -m pytest -q                   # 784 test
python scripts/rag_coverage.py        # độ phủ kho giáo trình
python scripts/demo_full.py           # 6 cảnh, không cần mạng, không cần model
```

---

## Xử lý sự cố

| Hiện tượng | Nguyên nhân | Xử lý |
|---|---|---|
| `pip install` xong vẫn `ModuleNotFoundError` | `pip` và `python` khác bản | dùng `python -m pip install` |
| Web mở ra, **không nút nào chạy** | thiếu CORS, hoặc API chưa bật | xem đèn báo cột phải; đặt `CORS_ORIGINS` |
| `/ask` báo `"Kho giáo trình chưa được dựng"` | thiếu `data/rag_index/` | làm lại mục 3 |
| Hỏi gì cũng ra đoạn lạc chủ đề | dựng kho mà **thiếu `--dense`** | dựng lại với `--dense` |
| `/ask` báo `"thiếu bộ mã hoá của kho giáo trình"` | chưa có bge-m3 trên máy này | `ollama pull bge-m3` |
| Dựng lại dữ liệu mà số không đổi | API nạp một lần lúc khởi động | khởi động lại API |
| Mục **Quản trị** không hiện | chưa đặt `ADMIN_TOKEN` | đặt biến rồi khởi động lại API |
| Gợi ý toàn câu mẫu giống nhau | chưa bật `LLM_HINTS=1` hoặc Ollama chưa chạy | bật lại |
| Bộ test đỏ vì `UnicodeEncodeError` | terminal dùng cp1252 | `set PYTHONIOENCODING=utf-8` |
| `npm run dev` lỗi module lạ | cache của Next.js hỏng | xoá `web/.next/` rồi chạy lại |
| Cổng 3000 hoặc 8000 "đã bị chiếm" | tiến trình cũ còn sống | tìm PID theo cổng rồi tắt |
| Ollama trả lời rất chậm | model 7B trên CPU | đổi sang `3b`, hoặc bật `DEMO_MODE=1` |

---

## Những thứ KHÔNG cần

Đỡ mất thời gian cài:

- **GPU** — toàn bộ phần phục vụ chạy CPU.
- **Mạng** sau khi cài xong — `demo_full.py` và bộ test chạy được khi rút dây.
- **`requirements-train.txt`** — chỉ khi huấn luyện LoRA.
- **`data/raw/`** nếu đã có `data/rag_index/` — kho đã dựng tự đủ, nó giữ cả nội dung
  đoạn. Đây là cách tiết kiệm nhất khi chuyển hệ thống sang máy khác: gửi 61 MB thay vì
  223 MB, và bỏ luôn 40 phút mã hoá. **Nhưng `bge-m3` thì vẫn phải có** — xem 3.2.
- **`models/`** — thiếu thì mô hình năng lực tự quay về BKT.
