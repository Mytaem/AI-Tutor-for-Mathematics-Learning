"""Test bộ sinh gợi ý bằng LLM — chạy offline với backend giả theo kịch bản.

Test quan trọng nhất là ``test_prompt_duoi_muc_4_khong_bao_gio_chua_dap_an``:
một bất biến kiểm trên TOÀN BỘ ngân hàng đề 4 môn. Lớp phòng vệ thứ nhất (model
không biết đáp án thì không nói ra được) chỉ có nghĩa nếu bất biến này đúng.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.config import LLMConfig  # noqa: E402
from src.core.itembank import ItemBank, load_course_error_codes  # noqa: E402
from src.core.schema import Submission  # noqa: E402
from src.llm.client import LLMClient, LLMError, LLMResponse, ResponseCache, StubBackend  # noqa: E402
from src.tutor.hint_policy import HintLevel  # noqa: E402
from src.tutor.hints import TutorEngine  # noqa: E402
from src.tutor.llm_hints import LLMHintGenerator  # noqa: E402
from src.verify.registry import verifier_for  # noqa: E402

LEAK = "Đáp án là (x**2+1)**4/8 + C nhé"
CLEAN = "Em thử kiểm tra lại hệ số khi đổi biến u = x² + 1 xem, du bằng bao nhiêu?"


@dataclass
class ScriptedBackend:
    """Trả lời lần lượt theo kịch bản — để kiểm vòng viết lại."""

    replies: list[str]
    name: str = "scripted"
    calls: list[list[dict]] = field(default_factory=list)

    def available(self) -> bool:
        return True

    def chat(self, messages, **options) -> LLMResponse:
        self.calls.append(list(messages))
        if not self.replies:
            raise LLMError("hết kịch bản")
        return LLMResponse(text=self.replies.pop(0), backend=self.name)


def make_client(backend, tmp_path: Path) -> LLMClient:
    config = LLMConfig(cache_path=tmp_path / "cache.sqlite", max_retries=0)
    return LLMClient([backend], ResponseCache(config.cache_path), config)


@pytest.fixture(scope="module")
def mae() -> ItemBank:
    return ItemBank.load("MAE101")


@pytest.fixture(scope="module")
def item(mae):
    return mae.get("MAE101-INT-010")  # ∫ x(x²+1)³ dx


@pytest.fixture(scope="module")
def wrong(item):
    return verifier_for("MAE101").verify(item, Submission(item_id=item.item_id, final_answer="(x**2+1)**4 + C"))


def generator(backend, tmp_path, mae, **kwargs) -> LLMHintGenerator:
    return LLMHintGenerator(make_client(backend, tmp_path), load_course_error_codes("MAE101"), mae.skills, **kwargs)


class TestRewriteLoop:
    def test_cau_sach_duoc_dung_ngay(self, tmp_path, mae, item, wrong) -> None:
        gen = generator(ScriptedBackend([CLEAN]), tmp_path, mae)
        hint = gen.generate(item, wrong, HintLevel.PITFALL)
        assert hint.source == "llm" and hint.text == CLEAN
        assert gen.last_trace.attempts == 1 and not gen.last_trace.fell_back

    def test_cau_lo_dap_an_thi_viet_lai(self, tmp_path, mae, item, wrong) -> None:
        backend = ScriptedBackend([LEAK, CLEAN])
        gen = generator(backend, tmp_path, mae)
        hint = gen.generate(item, wrong, HintLevel.PITFALL)
        assert hint.text == CLEAN
        assert gen.last_trace.attempts == 2 and gen.last_trace.rejected == [LEAK]
        assert "lộ đáp án" in backend.calls[1][-1]["content"], "Lần viết lại phải nói rõ lý do bị từ chối"

    def test_viet_lai_het_luot_van_lo_thi_dung_template(self, tmp_path, mae, item, wrong) -> None:
        gen = generator(ScriptedBackend([LEAK, LEAK, LEAK]), tmp_path, mae, max_rewrites=2)
        hint = gen.generate(item, wrong, HintLevel.PITFALL)
        assert hint.source != "llm"
        assert gen.last_trace.fell_back and len(gen.last_trace.rejected) == 3

    def test_llm_chet_thi_dung_template(self, tmp_path, mae, item, wrong) -> None:
        gen = generator(StubBackend("ollama", is_up=False), tmp_path, mae)
        hint = gen.generate(item, wrong, HintLevel.PITFALL)
        assert hint.source != "llm" and hint.text
        assert gen.last_trace.fell_back

    def test_tat_guardrail_thi_de_lot(self, tmp_path, mae, item, wrong) -> None:
        """Cờ ablation cho EXP-8: không guardrail thì câu lộ đáp án đi thẳng ra ngoài."""
        gen = generator(ScriptedBackend([LEAK]), tmp_path, mae, use_guardrail=False)
        assert gen.generate(item, wrong, HintLevel.PITFALL).text == LEAK

    def test_loi_giai_day_du_khong_can_llm(self, tmp_path, mae, item, wrong) -> None:
        backend = ScriptedBackend([])
        hint = generator(backend, tmp_path, mae).generate(item, wrong, HintLevel.FULL)
        assert hint.level is HintLevel.FULL and backend.calls == []


class TestPrompt:
    def test_prompt_neo_vao_chan_doan(self, tmp_path, mae, item, wrong) -> None:
        gen = generator(ScriptedBackend([]), tmp_path, mae)
        low = gen.build_messages(item, wrong, HintLevel.PITFALL)[1]["content"]
        high = gen.build_messages(item, wrong, HintLevel.CORRECT)[1]["content"]
        assert "đạo hàm ngược lại" in low, "Mức < 4: đưa câu gợi ý của mã lỗi"
        assert "Sai một hệ số hằng" not in low
        assert "Sai một hệ số hằng" in high, "Mức 4: được đưa tên và mô tả lỗi đầy đủ"

    def test_ten_ma_loi_khong_duoc_lam_lo_dap_an(self, tmp_path) -> None:
        """Hồi quy: chẩn đoán "Đưa nghiệm cho hệ vô nghiệm" từng nói luôn đáp án cho model."""
        bank = ItemBank.load("MAE101")
        it = bank.get("MAE101-LA-SYS-005")  # đáp án: vô nghiệm
        result = verifier_for("MAE101").verify(it, Submission(item_id=it.item_id, final_answer="[1, 0]"))
        assert "LA.SYS.INCONSISTENT" in result.candidate_error_codes
        gen = LLMHintGenerator(make_client(ScriptedBackend([]), tmp_path), load_course_error_codes("MAE101"), bank.skills)
        prompt = gen.build_messages(it, result, HintLevel.PITFALL)[1]["content"]
        assert "vô nghiệm" not in prompt.split("\n", 1)[1]

    def test_prompt_duoi_muc_4_khong_bao_gio_chua_dap_an(self, tmp_path) -> None:
        """Bất biến trên toàn bộ ngân hàng đề của cả 4 môn."""
        leaks = []
        for subject in ("MAE101", "MAI391", "MAS291", "MAD101"):
            bank = ItemBank.load(subject)
            verifier = verifier_for(subject)
            gen = LLMHintGenerator(make_client(ScriptedBackend([]), tmp_path), load_course_error_codes(subject), bank.skills)
            for it in bank.items.values():
                result = verifier.verify(it, Submission(item_id=it.item_id, final_answer="0"))
                for level in (HintLevel.PROBE, HintLevel.CONCEPT, HintLevel.PITFALL, HintLevel.LOCATE):
                    prompt = gen.build_messages(it, result, level)[1]["content"]
                    # Bỏ dòng đề bài: đáp án có thể tình cờ trùng một phần của đề
                    # (vector riêng [2, 1] nằm ngay trong ma trận [[4, 2], [2, 1]]).
                    beyond_statement = prompt.split("\n", 1)[1].lower()
                    answer = it.answer_text.lower()
                    trivial = answer in ("có", "không") or len(answer) < 4
                    if not trivial and answer in beyond_statement:
                        leaks.append(f"{it.item_id} mức {int(level)}: «{it.answer_text}» nằm trong prompt")
                    if "LỜI GIẢI MẪU" in prompt or "ĐÁP ÁN ĐÚNG" in prompt:
                        leaks.append(f"{it.item_id} mức {int(level)} (có mục đáp án)")
        assert leaks == [], "\n".join(leaks[:10])

    def test_muc_4_moi_duoc_co_dap_an(self, tmp_path, mae, item, wrong) -> None:
        prompt = generator(ScriptedBackend([]), tmp_path, mae).build_messages(item, wrong, HintLevel.CORRECT)[1]["content"]
        assert item.answer_text in prompt

    def test_tai_lieu_chi_dua_vao_muc_1_va_2(self, tmp_path, mae, item, wrong) -> None:
        seen = []

        def retriever(it, level):
            seen.append(level)
            return [("Integration by substitution: if u = g(x) then du = g'(x) dx.", "05_integration.pdf — tr.12")]

        gen = generator(ScriptedBackend([]), tmp_path, mae, retriever=retriever)
        concept = gen.build_messages(item, wrong, HintLevel.CONCEPT)[1]["content"]
        locate = gen.build_messages(item, wrong, HintLevel.LOCATE)[1]["content"]
        assert "05_integration.pdf" in concept and "05_integration.pdf" not in locate
        assert seen == [HintLevel.CONCEPT]


class TestEngineIntegration:
    def test_engine_dung_duoc_bo_sinh_llm(self, tmp_path, mae, item) -> None:
        gen = generator(ScriptedBackend([CLEAN, CLEAN, CLEAN]), tmp_path, mae)
        engine = TutorEngine(verifier_for("MAE101"), gen)
        response = engine.submit(item, Submission(item_id=item.item_id, final_answer="(x**2+1)**4 + C"))
        assert response.hint.source == "llm" and not response.hint.was_blocked
