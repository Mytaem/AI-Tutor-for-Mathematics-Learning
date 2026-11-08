import os

# Test phải tất định, không phụ thuộc Ollama có đang chạy trên máy hay không.
os.environ.setdefault("LLM_ASK", "0")

# Test cũ gọi API thay người dùng bằng user_id tự đặt — đúng vai của dịch vụ tin cậy
# (như bot). Phải đặt TRƯỚC khi import src.api.app: khoá được đọc lúc nạp module.
SERVICE_TOKEN = "test-service-token"
os.environ.setdefault("SERVICE_TOKEN", SERVICE_TOKEN)
SERVICE_HEADERS = {"X-Service-Token": SERVICE_TOKEN}
