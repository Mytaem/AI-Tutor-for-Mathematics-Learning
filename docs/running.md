# Chạy hệ thống

Ba tầng chạy độc lập, mở ba cửa sổ dòng lệnh.

## 1. API (bắt buộc)

```bash
python -m uvicorn src.api.app:create_app --factory --port 8000
```

Kiểm tra: mở http://localhost:8000/health — phải thấy đủ 4 môn và tổng số đề (~4.055,
gồm cả đề sinh tự động).

Biến môi trường đáng chú ý:

| Biến | Mặc định | Tác dụng |
|---|---|---|
| `LLM_HINTS` | tắt | `1` để gợi ý do Qwen diễn đạt (có guardrail); tắt thì dùng câu template |
| `KT_MODEL` | `bkt` | `dkt` để ước lượng năng lực bằng mạng hồi tiếp (cần `models/dkt/<môn>.pt`; thiếu thì tự quay về BKT) |
| `OLLAMA_MODEL` | `qwen2.5:3b-instruct` | đổi sang `qwen2.5:7b-instruct` khi cần chất lượng |
| `VLLM_URL` | trống | endpoint vLLM trên Kaggle; có thì ưu tiên hơn Ollama |
| `DEMO_MODE` | tắt | `1` để chỉ đọc cache, không gọi model — dùng khi bảo vệ |
| `DATABASE_URL` | `data/tutor.sqlite` | đổi file dữ liệu |
| `CORS_ORIGINS` | `localhost:3000`, `127.0.0.1:3000` | origin được phép gọi API |
| `ADMIN_TOKEN` | trống | bật phần quản trị; **trống = tắt hoàn toàn** |

### Hai biến dễ quên nhất

**`CORS_ORIGINS`** — web ở cổng 3000 gọi API ở cổng 8000, với trình duyệt đó là hai
origin khác nhau. Thiếu cấu hình này thì **giao diện dựng ra đầy đủ nhưng không nút
nào chạy**, và không có thông báo lỗi nào trên trang. Mặc định đã phủ trường hợp chạy
ở máy mình; chỉ cần đặt khi đưa web ra tunnel hay máy khác:

```bash
CORS_ORIGINS=https://abc.trycloudflare.com python -m uvicorn src.api.app:create_app --factory --port 8000
```

Thanh bên phải của web có **đèn báo kết nối backend** — xanh là gọi được, đỏ kèm chỉ
dẫn. Nó có mặt chính vì lỗi này từng lọt qua cả bộ test: `TestClient` và `curl` không
thi hành same-origin policy, chỉ trình duyệt thật mới chặn.

**`ADMIN_TOKEN`** — mặc định phần quản trị TẮT, không phải mở. Dữ liệu ở đó là bài làm
của người thật; "chưa cấu hình mà mở sẵn" là kiểu lỗ hổng tệ nhất vì không ai nhận ra
cho tới lúc muộn.

```bash
ADMIN_TOKEN=khoá-của-bạn python -m uvicorn src.api.app:create_app --factory --port 8000
```

Sau đó vào web, chuyển vai sang **Quản trị** rồi nhập khoá. Chuyển vai ở giao diện chỉ
đổi điều hướng; quyền thật do server kiểm bằng `secrets.compare_digest`.

## Endpoint chính

| Method | Path | Chức năng |
|---|---|---|
| GET | `/health` | trạng thái, số đề, số kỹ năng từng môn |
| GET | `/syllabus?subject=&user_id=` | cây môn → chương → bài → dạng bài, kèm số đề và mức thành thạo |
| POST | `/session/start` | tạo phiên, chạy test đầu vào |
| GET | `/item/next?user_id=&subject=&chapter=&skill=&topic=` | bài kế tiếp, ba bộ lọc cộng dồn |
| POST | `/attempt` | nộp bài → chấm → chẩn đoán lỗi → cập nhật năng lực |
| POST | `/hint` | gợi ý theo chính sách leo thang (`asked_for_solution` để xin lời giải) |
| POST | `/ask` | hỏi lý thuyết, nhận cả `subject` và `chapter` |
| GET | `/progress` | mức thành thạo từng kỹ năng |
| GET | `/admin/enabled` | phần quản trị có bật không — **không cần khoá** |
| GET | `/admin/overview` | số liệu cho giảng viên — cần `X-Admin-Token` |
| GET | `/admin/attempts`, `/admin/export.csv` | bài làm gần nhất, xuất CSV |

## 2. Web (Next.js)

```bash
cd web
npm install          # lần đầu
npm run dev          # http://localhost:3000
```

Trỏ sang API khác bằng `NEXT_PUBLIC_API_URL` (xem `web/.env.example`).

Ba trang: chọn môn → luyện tập (nộp bài, xin gợi ý từng mức) → tiến độ (mức thành
thạo từng kỹ năng do BKT ước lượng).

Frontend **không chứa logic sư phạm**: không tự chấm, không giữ đáp án, không tự
quyết mức gợi ý. Nhờ vậy web và bot Telegram luôn cho cùng kết quả trên cùng bài làm.

## 3. Model (tuỳ chọn)

```bash
ollama serve                      # nếu chưa chạy sẵn
ollama run qwen2.5:3b-instruct    # tải model lần đầu
```

Không có model thì hệ thống vẫn chạy: gợi ý rơi về câu template. Đây là điều cố ý —
buổi bảo vệ không được phụ thuộc vào tunnel hay mạng.

---

## Dựng lại dữ liệu

```bash
python scripts/build_bank.py all 1200      # sinh đề cho cả 4 môn
python scripts/build_error_dataset.py MAE101   # và MAI391 / MAS291 / MAD101
python scripts/build_rag_index.py --dense      # kho giáo trình (cần Ollama cho bge-m3)
```

**Dựng lại dữ liệu thì phải KHỞI ĐỘNG LẠI API.** Ngân hàng đề và kho RAG được nạp một
lần lúc khởi động rồi giữ trong bộ nhớ, nên API đang chạy vẫn phục vụ dữ liệu cũ. Triệu
chứng dễ gây hoang mang: script báo chương đã có 187 đề, mà `/syllabus` vẫn trả 0 — tôi
đã tự vấp đúng chỗ này khi kiểm tra.

## Kiểm tra TRƯỚC khi demo

```bash
python scripts/check_demo_ready.py    # máy đã sẵn sàng demo chưa (gộp mọi phép kiểm)
python scripts/rag_coverage.py        # chương nào chưa có giáo trình
python scripts/demo_full.py           # 6 cảnh, không cần model, không cần mạng
python -m pytest -q                   # 784 test, ~75 giây
```

**Người demo không phải người viết code** thì đọc [cho-nguoi-demo.md](cho-nguoi-demo.md):
`git pull` một mình không đủ, vì 284 MB dữ liệu cố ý không nằm trong git.

`rag_coverage.py` là bước quan trọng nhất trong ba bước trên, và nó tồn tại vì một
buổi demo thất bại: sinh viên hỏi "khoảng tin cậy là gì?", kho MAS291 không có chương
đó, và hệ thống khi ấy trả về một đoạn của chương Xác suất — trôi chảy, đúng môn, sai
chủ đề.

Hiện tại script báo **MAS291 thiếu 6/8 chương** và không có sách giáo trình chung để
bù. Hệ thống sẽ nói thẳng "chưa có tài liệu chương này" cho các câu hỏi đó — đúng hành
vi, nhưng vẫn là trống dữ liệu. **Khi demo nên tránh hỏi MAS291 về sáu chương đó**,
hoặc hỏi để trình diễn chính việc hệ thống thừa nhận trung thực.

## Thu thập và gán nhãn bài làm sai THẬT

Đây là việc duy nhất không tự động hoá được, và là chỗ đang chặn phần đánh giá:
mọi con số về chẩn đoán lỗi hiện đo trên lỗi do máy cài vào, tức là **chặn trên**.

**Cách nhanh nhất — để sinh viên tự sinh dữ liệu cho mình:**

```bash
python -m uvicorn src.api.app:create_app --factory --port 8000   # API
TELEGRAM_TOKEN=... python -m src.bot.main                        # bot
```

Nhờ 5–10 bạn, mỗi người làm 20 bài qua bot. Bài làm sai tự vào bảng `attempts`
kèm chẩn đoán của hệ thống. Sau đó gán nhãn:

```bash
python scripts/label_real_errors.py --from-db --limit 50
python scripts/label_real_errors.py --stats
```

Công cụ tự chấm sẵn và in đề, đáp án đúng, bài làm — người gán nhãn chỉ chọn mã
lỗi. **Đề xuất của máy phải gõ `may` mới hiện**, cố ý như vậy: nhìn thấy máy đoán
gì trước khi tự nghĩ thì rất dễ gật theo, mà nhãn đi xác nhận máy thì không còn
độc lập, và tập test thật mất sạch ý nghĩa.

Không có bot cũng được — chạy không tham số rồi gõ tay từng bài (mã đề + bài làm).

Mục tiêu 200 bài. Kết quả ghi vào `data/errors/real_labeled.jsonl`, cùng định dạng
với tập lỗi tổng hợp nên các script đo đạc dùng lại được ngay.

## Huấn luyện DKT để dùng thật

```bash
python scripts/train_dkt_for_serving.py            # cả 4 môn, ~3 phút, chỉ CPU
KT_MODEL=dkt python -m uvicorn src.api.app:create_app --factory --port 8000
```

Khác `scripts/exp5_kt.py` (huấn luyện để ĐO, có chia train/test): script này huấn
luyện để PHỤC VỤ và lưu ra `models/dkt/<môn>.pt`. Hiện học từ học sinh mô phỏng vì
mô hình phải nói về đúng tập kỹ năng của môn; khi có log người dùng thật thì huấn
luyện lại trên đó, đường dẫn và giao diện không đổi.

## Fine-tune LoRA (cần GPU — chạy trên Kaggle)

Máy cá nhân không có GPU. Luồng đã tự động hoá qua API Kaggle:

```bash
python scripts/build_sft_dataset.py 120     # dựng data/sft/{train,validation,test}.jsonl
python scripts/kaggle_push.py               # đẩy kernel, bật GPU + internet, chạy luôn
python scripts/kaggle_push.py --status      # xem chạy tới đâu
python scripts/kaggle_push.py --fetch       # tải log, adapter và metrics.json về
```

Cần `~/.kaggle/access_token` (lấy ở Kaggle → Settings → API → Create New Token).
Đẩy dataset lần đầu: `cd .kaggle_tmp/kg_data && python ../_cli.py datasets create -p .`
(phải chạy TỪ TRONG thư mục đó — CLI Kaggle dựng tên file tạm từ đường dẫn truyền
vào nên hỏng với đường dẫn tuyệt đối kiểu Windows).

Kernel tự đo model gốc trước khi học rồi đo lại sau, bằng đúng cách tính macro-F1
của baseline chạy ở máy, nên hai con số so trực tiếp được.

Muốn chạy trên Colab thay vì Kaggle thì dùng `scripts/train_lora_error_classifier.py`
(có `--resume` vì Colab hay ngắt phiên giữa chừng).

**Lưu ý mạng**: nếu `kaggle` treo ở bước kết nối, nhiều khả năng DNS trả địa chỉ
IPv6 NAT64; `scripts/kaggle_push.py` đã ép IPv4 sẵn.

## Chạy thí nghiệm

```bash
python scripts/exp4_retrieval.py --k 5            # BM25 / dense / hybrid
python scripts/exp4b_ask_quality.py --compare     # hỏi đáp lý thuyết, có/không từ điển
python scripts/exp5_kt.py --subject MAE101        # BKT / DKT / SAKT
python scripts/exp6_selection.py                  # bốn chiến lược chọn bài
python scripts/exp7_rag_ablation.py               # bỏ RAG khỏi prompt gợi ý
python scripts/exp8_leakage.py --per-subject 6    # chống lộ đáp án (cần model)
python scripts/make_report_tables.py              # sinh docs/results.md từ experiments/
```

Kết quả thô ghi vào `experiments/<tên>/`, bảng trong báo cáo sinh từ đó.

## Kiểm thử

```bash
python -m pytest -q
```

Khoảng 40 giây, không cần GPU, không cần mạng, không cần model — mọi thứ phụ thuộc
bên ngoài đều có bản giả trong test.
