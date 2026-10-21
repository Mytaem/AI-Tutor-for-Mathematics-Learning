import os

# Test phải tất định, không phụ thuộc Ollama có đang chạy trên máy hay không.
os.environ.setdefault("LLM_ASK", "0")
