# API FastAPI. Chỉ chứa mã nguồn và dữ liệu ĐƯỢC PHÉP giao: ngân hàng đề, kỹ năng,
# mã lỗi. Kho giáo trình (rag_index) KHÔNG đóng vào ảnh — nó chứa đoạn trích tài
# liệu có bản quyền; mỗi khách tự dựng từ tài liệu mình có quyền dùng (xem
# docs/trien-khai.md).
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
# torch bản CPU (~200 MB) thay vì bản CUDA mặc định (~2,5 GB): API chỉ cần torch
# cho DKT, chạy CPU là đủ. Bỏ pytest khỏi ảnh chạy.
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch \
 && grep -vE '^(torch|pytest|pytest-cov)\b' requirements.txt > /tmp/requirements.txt \
 && pip install -r /tmp/requirements.txt

COPY src ./src
COPY scripts ./scripts
COPY data/items ./data/items
COPY data/skills ./data/skills
COPY data/errors ./data/errors
COPY data/sources.json ./data/sources.json

RUN useradd --create-home --uid 10001 app \
 && mkdir -p /app/state /app/data/rag_index \
 && chown -R app /app/state /app/data

USER app

ENV DATABASE_URL=/app/state/tutor.sqlite \
    OLLAMA_URL=http://ollama:11434/v1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"

CMD ["uvicorn", "src.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
