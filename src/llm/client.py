"""Tầng gọi model, có chuỗi dự phòng ba lớp.

Đây là chỗ dễ vỡ nhất của đồ án: model chạy trên Kaggle qua tunnel, mà tunnel
miễn phí thì hay chết, phiên Kaggle thì hay bị ngắt. Nếu buổi bảo vệ rơi đúng
lúc đó mà hệ thống không trả lời được thì mọi thứ còn lại thành vô nghĩa.

Chuỗi dự phòng::

    vLLM (Kaggle + tunnel)  ->  Ollama (local)  ->  Cache (đã ghi sẵn)

Cả vLLM lẫn Ollama đều expose API tương thích OpenAI, nên một lớp backend dùng
chung được cho cả hai — chỉ khác URL và tên model.

Mọi phản hồi đều được ghi vào cache SQLite trong lúc phát triển. Bật ``DEMO_MODE``
thì client chỉ đọc cache, trả lời tức thì và không cần mạng. Việc dùng cache
phải được ghi rõ trong báo cáo, không giấu.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, Sequence

from src.core.config import LLMConfig

Message = dict[str, str]


class LLMError(RuntimeError):
    """Không backend nào trả lời được."""


@dataclass
class LLMResponse:
    text: str
    backend: str
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0
    cached: bool = False


# --------------------------------------------------------------------------
# Cache
# --------------------------------------------------------------------------

def fingerprint(messages: Sequence[Message], model: str, temperature: float) -> str:
    """Khoá cache. Gồm cả model và nhiệt độ vì đổi hai thứ đó là đổi câu trả lời."""
    payload = json.dumps(
        {"messages": list(messages), "model": model, "temperature": round(temperature, 3)},
        ensure_ascii=False, sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ResponseCache:
    """Lưu phản hồi của model vào SQLite.

    Hai công dụng: tiết kiệm thời gian khi phát triển (model nhỏ chạy CPU rất
    chậm), và làm nguồn trả lời cho DEMO_MODE.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def _init_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS responses (
                    key TEXT PRIMARY KEY,
                    model TEXT,
                    backend TEXT,
                    text TEXT NOT NULL,
                    prompt_tokens INTEGER DEFAULT 0,
                    completion_tokens INTEGER DEFAULT 0,
                    created_at REAL
                )
                """
            )

    def get(self, key: str) -> LLMResponse | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT text, model, backend, prompt_tokens, completion_tokens "
                "FROM responses WHERE key = ?",
                (key,),
            ).fetchone()
        if row is None:
            return None
        return LLMResponse(
            text=row[0], backend="cache", model=row[1] or "",
            prompt_tokens=row[3] or 0, completion_tokens=row[4] or 0, cached=True,
        )

    def put(self, key: str, response: LLMResponse) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO responses "
                "(key, model, backend, text, prompt_tokens, completion_tokens, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (key, response.model, response.backend, response.text,
                 response.prompt_tokens, response.completion_tokens, time.time()),
            )

    def count(self) -> int:
        with self._connect() as connection:
            return connection.execute("SELECT COUNT(*) FROM responses").fetchone()[0]


# --------------------------------------------------------------------------
# Backend
# --------------------------------------------------------------------------

class Backend(Protocol):
    name: str

    def available(self) -> bool: ...
    def chat(self, messages: Sequence[Message], **options) -> LLMResponse: ...


@dataclass
class OpenAICompatibleBackend:
    """Dùng chung cho vLLM và Ollama — cả hai đều nói giao thức OpenAI."""

    name: str
    base_url: str
    model: str
    timeout: float = 90.0
    api_key: str = "EMPTY"

    def available(self) -> bool:
        if not self.base_url:
            return False
        try:
            import httpx
        except ImportError:
            return False
        try:
            response = httpx.get(f"{self.base_url.rstrip('/')}/models", timeout=5.0)
            return response.status_code < 500
        except Exception:
            # Tunnel chết, Ollama chưa bật, mất mạng — đều rơi vào đây và đều
            # có nghĩa là "chuyển sang lớp dự phòng", không phải lỗi cần ném ra.
            return False

    def chat(self, messages: Sequence[Message], **options) -> LLMResponse:
        import httpx

        started = time.perf_counter()
        payload = {
            "model": self.model,
            "messages": list(messages),
            "temperature": options.get("temperature", 0.3),
            "max_tokens": options.get("max_tokens", 512),
        }
        response = httpx.post(
            f"{self.base_url.rstrip('/')}/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()

        usage = data.get("usage", {})
        return LLMResponse(
            text=data["choices"][0]["message"]["content"],
            backend=self.name,
            model=self.model,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            latency_ms=(time.perf_counter() - started) * 1000,
        )


@dataclass
class CacheBackend:
    """Lớp cuối: chỉ trả lời những gì đã ghi sẵn."""

    cache: ResponseCache
    name: str = "cache"
    model: str = ""
    temperature: float = 0.3

    def available(self) -> bool:
        return True

    def chat(self, messages: Sequence[Message], **options) -> LLMResponse:
        key = fingerprint(messages, self.model or options.get("model", ""),
                          options.get("temperature", self.temperature))
        hit = self.cache.get(key)
        if hit is None:
            raise LLMError("Không có phản hồi nào trong cache cho yêu cầu này")
        return hit


@dataclass
class StubBackend:
    """Backend tất định cho test — không mạng, không model."""

    name: str = "stub"
    reply: str = "OK"
    is_up: bool = True
    calls: list[list[Message]] = field(default_factory=list)

    def available(self) -> bool:
        return self.is_up

    def chat(self, messages: Sequence[Message], **options) -> LLMResponse:
        if not self.is_up:
            raise LLMError(f"{self.name} đang không hoạt động")
        self.calls.append(list(messages))
        return LLMResponse(text=self.reply, backend=self.name, model="stub")


# --------------------------------------------------------------------------
# Client
# --------------------------------------------------------------------------

class LLMClient:
    """Gọi model qua chuỗi backend, tự chuyển lớp khi lớp trên hỏng."""

    def __init__(
        self,
        backends: Sequence[Backend],
        cache: ResponseCache | None = None,
        config: LLMConfig | None = None,
    ) -> None:
        self.backends = list(backends)
        self.cache = cache
        self.config = config or LLMConfig()
        self.last_backend: str | None = None

    # ------------------------------------------------------------------

    @classmethod
    def from_config(cls, config: LLMConfig | None = None) -> LLMClient:
        """Dựng client theo cấu hình môi trường."""
        config = config or LLMConfig()
        cache = ResponseCache(config.cache_path)

        if config.demo_mode:
            # Chế độ demo: khoá hẳn vào cache, không gọi mạng dù model có sống.
            return cls([CacheBackend(cache, model=config.vllm_model)], cache, config)

        backends: list[Backend] = []
        if config.vllm_url:
            backends.append(OpenAICompatibleBackend(
                "vllm", config.vllm_url, config.vllm_model, config.timeout_seconds))
        if config.ollama_url:
            backends.append(OpenAICompatibleBackend(
                "ollama", config.ollama_url, config.ollama_model, config.timeout_seconds))
        backends.append(CacheBackend(cache, model=config.vllm_model))

        return cls(backends, cache, config)

    # ------------------------------------------------------------------

    def chat(self, messages: Sequence[Message], **options) -> LLMResponse:
        """Gọi model. Thử lần lượt từng backend cho tới khi có cái trả lời được."""
        temperature = options.setdefault("temperature", self.config.temperature)
        options.setdefault("max_tokens", self.config.max_tokens)

        # Cache đọc trước: model nhỏ chạy CPU mất hàng chục giây cho một câu,
        # mà trong lúc phát triển ta gọi đi gọi lại cùng một prompt.
        key = fingerprint(messages, self.config.vllm_model, temperature)
        if self.cache is not None and not self.config.demo_mode:
            hit = self.cache.get(key)
            if hit is not None:
                self.last_backend = "cache"
                return hit

        failures: list[str] = []
        for backend in self.backends:
            if not backend.available():
                failures.append(f"{backend.name}: không phản hồi")
                continue
            try:
                response = self._call_with_retry(backend, messages, options)
            except Exception as exc:
                failures.append(f"{backend.name}: {type(exc).__name__}")
                continue

            self.last_backend = backend.name
            if self.cache is not None and not response.cached:
                self.cache.put(key, response)
            return response

        raise LLMError("Không backend nào trả lời được — " + "; ".join(failures))

    def _call_with_retry(self, backend: Backend, messages, options) -> LLMResponse:
        last: Exception | None = None
        for attempt in range(self.config.max_retries + 1):
            try:
                return backend.chat(messages, **options)
            except Exception as exc:
                last = exc
                if attempt < self.config.max_retries:
                    time.sleep(0.5 * (attempt + 1))
        raise last if last is not None else LLMError("lỗi không xác định")

    # ------------------------------------------------------------------

    def health(self) -> dict[str, object]:
        """Backend nào đang sống — dùng cho endpoint /health và cho slide bảo vệ."""
        statuses = [
            {"name": backend.name, "available": backend.available()}
            for backend in self.backends
        ]
        active = next((s["name"] for s in statuses if s["available"]), None)
        return {
            "backends": statuses,
            "active": active,
            "demo_mode": self.config.demo_mode,
            "cached_responses": self.cache.count() if self.cache else 0,
        }
