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
    ollama_model: str = field(default_factory=lambda: _env("OLLAMA_MODEL", "qwen2.5:1.5b"))

    #: Bật lên thì CHỈ đọc cache, không gọi model. Dùng khi demo.
    demo_mode: bool = field(default_factory=lambda: _env_bool("DEMO_MODE"))
    cache_path: Path = field(default_factory=lambda: ROOT / "data" / "llm_cache.sqlite")

    timeout_seconds: float = field(default_factory=lambda: _env_float("LLM_TIMEOUT", 90.0))
    max_retries: int = 2
    temperature: float = field(default_factory=lambda: _env_float("LLM_TEMPERATURE", 0.3))
    max_tokens: int = 512


@dataclass
class AppConfig:
    llm: LLMConfig = field(default_factory=LLMConfig)
    database_url: str = field(default_factory=lambda: _env("DATABASE_URL", ""))
    subject_default: str = "MAE101"

    @property
    def database_path(self) -> Path:
        if self.database_url:
            return Path(self.database_url)
        return ROOT / "data" / "tutor.sqlite"


def load_config() -> AppConfig:
    return AppConfig()
