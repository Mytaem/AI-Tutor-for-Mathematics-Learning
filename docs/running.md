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
python scripts/exp5_kt.py --subject MAE101     # BKT / DKT / SAKT
python scripts/exp6_selection.py               # bốn chiến lược chọn bài
python scripts/exp8_leakage.py --per-subject 6 # chống lộ đáp án (cần model)
```

Kết quả thô ghi vào `experiments/<tên>/`, bảng trong báo cáo sinh từ đó.

## Kiểm thử

```bash
python -m pytest -q
```

Khoảng 40 giây, không cần GPU, không cần mạng, không cần model — mọi thứ phụ thuộc
bên ngoài đều có bản giả trong test.
