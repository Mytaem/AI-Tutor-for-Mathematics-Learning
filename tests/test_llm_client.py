"""Test tầng gọi model — chạy hoàn toàn offline.

Trọng tâm là chuỗi dự phòng: đây là cơ chế quyết định buổi bảo vệ có chạy được
hay không, nên phải kiểm tra được mà không cần dựng vLLM hay Ollama thật.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.config import LLMConfig  # noqa: E402
from src.llm.client import (  # noqa: E402
    CacheBackend,
    LLMClient,
    LLMError,
    LLMResponse,
    ResponseCache,
    StubBackend,
    fingerprint,
)

MESSAGES = [{"role": "user", "content": "Nguyên hàm của x^2 là gì?"}]


@pytest.fixture
def cache(tmp_path: Path) -> ResponseCache:
    return ResponseCache(tmp_path / "cache.sqlite")


@pytest.fixture
def config(tmp_path: Path) -> LLMConfig:
    return LLMConfig(cache_path=tmp_path / "cache.sqlite", max_retries=0)


class TestFingerprint:
    def test_cung_dau_vao_cho_cung_khoa(self) -> None:
        assert fingerprint(MESSAGES, "m", 0.3) == fingerprint(MESSAGES, "m", 0.3)

    def test_doi_model_thi_doi_khoa(self) -> None:
        """Đổi model là đổi câu trả lời, không được dùng lại cache của model cũ."""
        assert fingerprint(MESSAGES, "qwen-7b", 0.3) != fingerprint(MESSAGES, "qwen-1.5b", 0.3)

    def test_doi_nhiet_do_thi_doi_khoa(self) -> None:
        assert fingerprint(MESSAGES, "m", 0.0) != fingerprint(MESSAGES, "m", 0.9)

    def test_doi_model_ollama_thi_doi_khoa(self) -> None:
        """Hồi quy: khoá từng chỉ theo vllm_model, nên 3b và 7b qua Ollama dùng chung cache."""
        small = LLMConfig(vllm_url="", ollama_model="qwen2.5:3b-instruct")
        large = LLMConfig(vllm_url="", ollama_model="qwen2.5:7b-instruct")
        assert small.cache_model != large.cache_model


class TestResponseCache:
    def test_ghi_roi_doc_lai_duoc(self, cache: ResponseCache) -> None:
        cache.put("k1", LLMResponse(text="x**3/3 + C", backend="vllm", model="qwen"))
        hit = cache.get("k1")
        assert hit is not None
        assert hit.text == "x**3/3 + C"
        assert hit.cached is True
        assert hit.backend == "cache"

    def test_khoa_khong_co_thi_tra_none(self, cache: ResponseCache) -> None:
        assert cache.get("khong-ton-tai") is None

    def test_dem_duoc_so_ban_ghi(self, cache: ResponseCache) -> None:
        assert cache.count() == 0
        cache.put("a", LLMResponse(text="1", backend="stub"))
        cache.put("b", LLMResponse(text="2", backend="stub"))
        assert cache.count() == 2

    def test_ghi_de_cung_khoa_khong_nhan_doi(self, cache: ResponseCache) -> None:
        cache.put("a", LLMResponse(text="cũ", backend="stub"))
        cache.put("a", LLMResponse(text="mới", backend="stub"))
        assert cache.count() == 1
        assert cache.get("a").text == "mới"


class TestFallbackChain:
    def test_dung_backend_dau_tien_khi_no_song(self, cache: ResponseCache, config: LLMConfig) -> None:
        primary = StubBackend("vllm", reply="từ vllm")
        secondary = StubBackend("ollama", reply="từ ollama")

        response = LLMClient([primary, secondary], cache, config).chat(MESSAGES)

        assert response.text == "từ vllm"
        assert secondary.calls == [], "Backend dự phòng không được gọi khi lớp trên còn sống"

    def test_tunnel_chet_thi_tu_roi_xuong_ollama(self, cache: ResponseCache, config: LLMConfig) -> None:
        """Tình huống hay xảy ra nhất: tunnel Kaggle chết giữa chừng."""
        dead = StubBackend("vllm", is_up=False)
        alive = StubBackend("ollama", reply="từ ollama")

        client = LLMClient([dead, alive], cache, config)
        response = client.chat(MESSAGES)

        assert response.text == "từ ollama"
        assert client.last_backend == "ollama"

    def test_backend_nem_loi_cung_duoc_bo_qua(self, cache: ResponseCache, config: LLMConfig) -> None:
        """'Sống' theo health check nhưng gọi thì lỗi — vẫn phải chuyển lớp."""

        class Exploding(StubBackend):
            def chat(self, messages, **options):
                raise RuntimeError("500 Internal Server Error")

        client = LLMClient([Exploding("vllm"), StubBackend("ollama", reply="ok")], cache, config)
        assert client.chat(MESSAGES).text == "ok"

    def test_roi_xuong_cache_khi_moi_backend_deu_chet(
        self, cache: ResponseCache, config: LLMConfig
    ) -> None:
        cache.put(fingerprint(MESSAGES, config.cache_model, config.temperature),
                  LLMResponse(text="câu trả lời đã ghi sẵn", backend="vllm"))

        client = LLMClient(
            [StubBackend("vllm", is_up=False), StubBackend("ollama", is_up=False),
             CacheBackend(cache, model=config.cache_model)],
            cache, config,
        )
        assert client.chat(MESSAGES).text == "câu trả lời đã ghi sẵn"

    def test_bao_loi_ro_rang_khi_khong_con_duong_nao(
        self, cache: ResponseCache, config: LLMConfig
    ) -> None:
        client = LLMClient([StubBackend("vllm", is_up=False), StubBackend("ollama", is_up=False)],
                           cache, config)
        with pytest.raises(LLMError) as error:
            client.chat(MESSAGES)
        assert "vllm" in str(error.value) and "ollama" in str(error.value)


class TestCaching:
    def test_lan_goi_thu_hai_lay_tu_cache(self, cache: ResponseCache, config: LLMConfig) -> None:
        """Model nhỏ chạy CPU mất hàng chục giây — không được gọi lại cùng một prompt."""
        backend = StubBackend("vllm", reply="x**3/3 + C")
        client = LLMClient([backend], cache, config)

        first = client.chat(MESSAGES)
        second = client.chat(MESSAGES)

        assert first.text == second.text
        assert len(backend.calls) == 1, "Prompt giống hệt không được gọi model lần hai"
        assert second.cached is True

    def test_prompt_khac_thi_van_goi_model(self, cache: ResponseCache, config: LLMConfig) -> None:
        backend = StubBackend("vllm", reply="ok")
        client = LLMClient([backend], cache, config)

        client.chat(MESSAGES)
        client.chat([{"role": "user", "content": "Câu hỏi khác hẳn"}])

        assert len(backend.calls) == 2


class TestDemoMode:
    def test_demo_mode_khong_goi_model_that(self, tmp_path: Path) -> None:
        """Lúc bảo vệ phải trả lời tức thì và không phụ thuộc mạng."""
        config = LLMConfig(cache_path=tmp_path / "c.sqlite", demo_mode=True, vllm_url="http://x")
        cache = ResponseCache(config.cache_path)
        cache.put(fingerprint(MESSAGES, config.cache_model, config.temperature),
                  LLMResponse(text="đáp án đã chuẩn bị", backend="vllm"))

        client = LLMClient.from_config(config)
        assert client.chat(MESSAGES).text == "đáp án đã chuẩn bị"
        assert all(b.name == "cache" for b in client.backends), "Demo mode chỉ được dùng cache"

    def test_demo_mode_bao_loi_neu_chua_chuan_bi_cau_tra_loi(self, tmp_path: Path) -> None:
        config = LLMConfig(cache_path=tmp_path / "c.sqlite", demo_mode=True)
        with pytest.raises(LLMError):
            LLMClient.from_config(config).chat(MESSAGES)


class TestHealth:
    def test_bao_cao_backend_nao_dang_song(self, cache: ResponseCache, config: LLMConfig) -> None:
        client = LLMClient(
            [StubBackend("vllm", is_up=False), StubBackend("ollama", is_up=True)], cache, config
        )
        health = client.health()

        assert health["active"] == "ollama"
        assert health["backends"][0] == {"name": "vllm", "available": False}
        assert health["demo_mode"] is False

    def test_bao_active_none_khi_tat_ca_chet(self, cache: ResponseCache, config: LLMConfig) -> None:
        client = LLMClient([StubBackend("vllm", is_up=False)], cache, config)
        assert client.health()["active"] is None


class TestRetry:
    def test_thu_lai_truoc_khi_bo_cuoc(self, cache: ResponseCache, tmp_path: Path) -> None:
        """Lỗi mạng thoáng qua không nên làm rơi hẳn xuống lớp dưới."""
        config = LLMConfig(cache_path=tmp_path / "c.sqlite", max_retries=2)

        class FlakyBackend(StubBackend):
            attempts = 0

            def chat(self, messages, **options):
                FlakyBackend.attempts += 1
                if FlakyBackend.attempts < 3:
                    raise RuntimeError("timeout")
                return LLMResponse(text="thành công ở lần thứ ba", backend=self.name)

        client = LLMClient([FlakyBackend("vllm")], cache, config)
        assert client.chat(MESSAGES).text == "thành công ở lần thứ ba"
        assert FlakyBackend.attempts == 3
