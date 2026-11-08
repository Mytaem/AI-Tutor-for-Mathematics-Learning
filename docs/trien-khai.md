# Triển khai cho khách hàng

Viết cho **người cài đặt phía khách** (IT của trường, trung tâm). Cần biết dùng dòng
lệnh và Docker; không cần biết Python.

## Máy chủ cần gì

| | Tối thiểu | Nên có |
|---|---|---|
| CPU / RAM | 4 nhân, 16 GB | 8 nhân, 32 GB |
| GPU | không bắt buộc | NVIDIA ≥ 8 GB VRAM: hỏi đáp nhanh hơn 5–10 lần |
| Ổ đĩa | 20 GB | 50 GB |
| Phần mềm | Docker 24+ với Docker Compose | |

Không có GPU, phần **Hỏi đáp** mất 20–60 giây mỗi câu. **Luyện tập và gợi ý không cần
mô hình**: chúng phản hồi tức thì trên mọi máy.

## Cài đặt (khoảng 30 phút, phần lớn là tải mô hình)

```bash
# 1. Lấy mã nguồn, tạo file cấu hình
cp deploy/.env.example .env
#    Mở .env: đặt ADMIN_TOKEN (chuỗi ngẫu nhiên dài), SITE_ADDRESS và APP_URL (tên miền),
#    và cấu hình SMTP để gửi email xác thực / đặt lại mật khẩu

# 2. Dựng và chạy
docker compose up -d --build

# 3. Tải mô hình về (một lần, khoảng 6 GB)
docker compose --profile setup run --rm models

# 4. Kiểm tra
curl http://localhost/api/health      # "email_configured": true thì email đã sẵn sàng
```

Mở trình duyệt vào địa chỉ máy chủ (hoặc tên miền). Trang quản trị: chọn **Quản trị**
rồi nhập `ADMIN_TOKEN`.

Đặt `SITE_ADDRESS=tutor.ten-truong.edu.vn` và trỏ tên miền về máy chủ: Caddy tự xin và
gia hạn chứng chỉ HTTPS (cần mở cổng 80 và 443).

## Kho giáo trình cho phần Hỏi đáp

Bộ cài **không kèm giáo trình**: nội dung sách và slide thuộc bản quyền của người viết.
Mỗi đơn vị dựng kho từ tài liệu **mình có quyền dùng** (slide của chính giảng viên,
sách có giấy phép phù hợp):

```bash
# Đặt tài liệu (.pdf, .docx, .pptx) vào data/raw/<MÃ MÔN>/..., ghi nguồn vào data/sources.json
docker compose run --rm -v "$PWD/data/raw:/app/data/raw:ro" api \
  python scripts/build_rag_index.py --dense
docker compose restart api
```

Chưa có kho thì trang Hỏi đáp báo rõ là chưa có tài liệu. Các phần khác vẫn chạy bình
thường.

## Sao lưu

Dữ liệu của người học (bài làm, tiến độ) nằm trong volume `state`. **Sao lưu hằng ngày:**

```bash
docker compose exec api python -c "import sqlite3; s=sqlite3.connect('/app/state/tutor.sqlite'); s.backup(sqlite3.connect('/app/state/backup.sqlite'))"
docker compose cp api:/app/state/backup.sqlite ./backup-$(date +%F).sqlite
```

Dùng lệnh `backup` của SQLite, không chép file khi đang chạy: cơ sở dữ liệu ở chế độ WAL,
chép thẳng có thể ra bản hỏng.

## Cập nhật phiên bản

```bash
git pull
docker compose up -d --build
```

Volume `state`, `rag_index`, `ollama` giữ nguyên qua các lần cập nhật.

## Xử lý sự cố

| Hiện tượng | Nguyên nhân thường gặp | Cách xử lý |
|---|---|---|
| Hỏi đáp luôn trả về đoạn sách tiếng Anh | chưa tải mô hình, hoặc máy quá yếu (quá 100 giây) | chạy bước 3; xem `docker compose logs ollama` |
| Hỏi đáp báo chưa có tài liệu | chưa dựng kho giáo trình | xem mục Kho giáo trình |
| Trang quản trị không vào được | sai hoặc chưa đặt `ADMIN_TOKEN` | sửa `.env`, `docker compose up -d` |
| HTTPS không lên | tên miền chưa trỏ về máy, cổng 80/443 bị chặn | kiểm tra DNS và tường lửa; `docker compose logs caddy` |
