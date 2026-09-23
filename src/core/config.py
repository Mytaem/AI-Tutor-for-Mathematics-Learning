"""Cấu hình hệ thống, đọc từ biến môi trường.

Mọi thứ có thể thay đổi giữa máy phát triển, Colab/Kaggle và buổi bảo vệ đều
nằm ở đây. Không hardcode URL hay tên model trong code — tunnel của Kaggle đổi
địa chỉ mỗi lần khởi động lại, mà lúc bảo vệ thì không có thời gian sửa code.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _env_bool(name: str, default: bool = False) -> bool:
    value = _env(name).lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    try:
        return float(_env(name)) if _env(name) else default
    except ValueError:
        return default


@dataclass
class LLMConfig:
    """Cấu hình tầng model.

    Thứ tự ưu tiên backend là cố ý: vLLM cho chất lượng, Ollama để luôn có cái
    chạy, cache để buổi bảo vệ không phụ thuộc vào mạng.
    """

    #: URL endpoint tương thích OpenAI của vLLM (chạy trên Kaggle + tunnel).
    vllm_url: str = field(default_factory=lambda: _env("VLLM_URL"))
    vllm_model: str = field(default_factory=lambda: _env("VLLM_MODEL", "Qwen/Qwen2.5-Math-7B-Instruct"))

    #: Ollama chạy local — lớp dự phòng bắt buộc phải có.
    ollama_url: str = field(default_factory=lambda: _env("OLLAMA_URL", "http://localhost:11434/v1"))
    #: Máy phát triển đã có sẵn qwen2.5:3b-instruct và 7b-instruct trong Ollama. Mặc định
    #: 3b vì chạy CPU nhanh hơn đáng kể; đặt OLLAMA_MODEL=qwen2.5:7b-instruct khi cần chất lượng.
    ollama_model: str = field(default_factory=lambda: _env("OLLAMA_MODEL", "qwen2.5:3b-instruct"))

    #: Bật lên thì CHỈ đọc cache, không gọi model. Dùng khi demo.
    demo_mode: bool = field(default_factory=lambda: _env_bool("DEMO_MODE"))
    cache_path: Path = field(default_factory=lambda: ROOT / "data" / "llm_cache.sqlite")

    timeout_seconds: float = field(default_factory=lambda: _env_float("LLM_TIMEOUT", 90.0))
    max_retries: int = 2
    temperature: float = field(default_factory=lambda: _env_float("LLM_TEMPERATURE", 0.3))
    max_tokens: int = 512

    @property
    def cache_model(self) -> str:
        """Danh tính model dùng làm khoá cache.

        Trước đây khoá theo ``vllm_model`` cả khi vLLM không được cấu hình, nên
        câu trả lời của qwen2.5:3b và 7b (qua Ollama) dùng chung một khoá: đổi
        OLLAMA_MODEL để so hai model thì nhận lại nguyên câu trả lời của model cũ.
        """
        if self.vllm_url:
            return f"{self.vllm_model}+{self.ollama_model}"
        return self.ollama_model


@dataclass
class AppConfig:
    llm: LLMConfig = field(default_factory=LLMConfig)
    database_url: str = field(default_factory=lambda: _env("DATABASE_URL", ""))
    #: Bật LLM_HINTS=1 để gợi ý do model sinh (có guardrail); mặc định dùng câu
    #: template — tất định, không cần model, nên test và CI không phụ thuộc Ollama.
    llm_hints: bool = field(default_factory=lambda: _env_bool("LLM_HINTS"))
    subject_default: str = "MAE101"

    @property
    def database_path(self) -> Path:
        if self.database_url:
            return Path(self.database_url)
        return ROOT / "data" / "tutor.sqlite"


def load_config() -> AppConfig:
    return AppConfig()
