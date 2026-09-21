"""Guardrail trên các dạng đáp án MAI391 — ma trận, vector, nghiệm tham số, ODE.

Bản guardrail trước tự so khớp với đáp án chuẩn nên để lọt đúng những dạng này.
Bản hiện tại hỏi thẳng verifier, nên mọi dạng tương đương đều bị chặn.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.itembank import ERRORS_DIR, ItemBank, load_error_codes  # noqa: E402
from src.core.schema import Submission  # noqa: E402
from src.tutor.guardrail import check_leak, extract_candidates  # noqa: E402
from src.tutor.hint_policy import HintLevel  # noqa: E402
from src.tutor.hints import HintGenerator, TutorEngine  # noqa: E402
from src.verify.registry import verifier_for  # noqa: E402

LOW = HintLevel.PITFALL  # mức chưa được phép nói đáp án


@pytest.fixture(scope="module")
def bank() -> ItemBank:
    return ItemBank.load("MAI391")


def leaked(bank: ItemBank, item_id: str, text: str) -> bool:
    return check_leak(text, bank.get(item_id), LOW).leaked


class TestCatchesMAI391Leaks:
    @pytest.mark.parametrize("text", [
        "Em thử v = [1, 1] xem sao",
        "Vector [2, 2] thoả mãn đấy",          # bội vô hướng khác
        "Đáp án là (-5, -5)",                   # ngoặc tròn, bội âm
    ])
    def test_vector_rieng(self, bank: ItemBank, text: str) -> None:
        assert leaked(bank, "MAI391-VEC-001", text)

    def test_ma_tran_nghich_dao(self, bank: ItemBank) -> None:
        assert leaked(bank, "MAI391-INV-001", "Kết quả: [[3/5, -7/10], [-1/5, 2/5]]")
        assert leaked(bank, "MAI391-INV-001", "Nghịch đảo là [[0.6, -0.7], [-0.2, 0.4]] nhé")

    @pytest.mark.parametrize("text", [
        "Nghiệm là [1 - s - t, s, t]",
        "Họ nghiệm [u, v, 1 - u - v]",          # tham số hoá khác hẳn
    ])
    def test_nghiem_tham_so(self, bank: ItemBank, text: str) -> None:
        assert leaked(bank, "MAI391-SYS-003", text)

    def test_nghiem_ode_dat_ten_hang_so_khac(self, bank: ItemBank) -> None:
        assert leaked(bank, "MAI391-ODE-002", "Thử y = A*exp(2*x) + B*exp(x) xem")

    def test_dap_an_bang_loi(self, bank: ItemBank) -> None:
        assert leaked(bank, "MAI391-SYS-005", "Để ý là hệ này vô nghiệm đấy")
        assert leaked(bank, "MAI391-INV-003", "Ma trận này không khả nghịch")

    def test_dap_an_la_mot_con_so(self, bank: ItemBank) -> None:
        assert leaked(bank, "MAI391-DET-003", "Định thức bằng 10")


class TestDoesNotBlockLegitimateHints:
    def test_goi_y_phuong_phap(self, bank: ItemBank) -> None:
        assert not leaked(bank, "MAI391-VEC-001", "Em thử giải hệ (A - 3I)v = 0 xem")

    def test_nhac_lai_ma_tran_de_bai(self, bank: ItemBank) -> None:
        """Nhắc lại ma trận A của đề không phải là lộ ma trận nghịch đảo."""
        assert not leaked(bank, "MAI391-INV-001", "Với A = [[4, 7], [2, 6]], em tính det(A) trước")

    def test_so_thu_tu_buoc_khong_bi_coi_la_dap_an(self, bank: ItemBank) -> None:
        """Đáp án bằng 1, nhưng "bước 1" là số thứ tự — không được chặn oan."""
        assert not leaked(bank, "MAI391-DET-002", "Em xem lại bước 1 và hàng 1 nhé")

    def test_ket_luan_sai_khong_phai_lo(self, bank: ItemBank) -> None:
        """Nói 'vô nghiệm' ở một hệ CÓ nghiệm không làm lộ gì cả."""
        assert not leaked(bank, "MAI391-SYS-001", "Nhiều bạn kết luận vô nghiệm ở bài này")

    def test_muc_cao_duoc_phep(self, bank: ItemBank) -> None:
        assert not check_leak("Đáp án là [1, 1]", bank.get("MAI391-VEC-001"), HintLevel.FULL).leaked


class TestExtraction:
    def test_trich_duoc_ma_tran_long(self) -> None:
        assert "[[3/5, -7/10], [-1/5, 2/5]]" in extract_candidates("Kết quả: [[3/5, -7/10], [-1/5, 2/5]]")

    def test_khong_nham_loi_goi_ham_la_vector(self) -> None:
        assert "(1, 2)" not in extract_candidates("Xét f(1, 2) trước đã")


class TestTemplateHintsOnMAI391:
    """Chạy cả thang gợi ý trên MỌI bài MAI391 — gợi ý template không được tự làm lộ đáp án."""

    def test_khong_muc_nao_duoi_4_lo_dap_an(self, bank: ItemBank) -> None:
        engine = TutorEngine(
            verifier_for("MAI391"),
            HintGenerator(load_error_codes(ERRORS_DIR / "mai391.json"), bank.skills, seed=1),
        )
        blocked = []
        for item in bank.items.values():
            response = engine.submit(item, Submission(item_id=item.item_id, final_answer="[0, 0, 0, 0]"))
            if response.hint is None:
                continue
            for _ in range(5):
                if response.hint.was_blocked:
                    blocked.append(f"{item.item_id} mức {int(response.hint.level)}: {response.hint.blocked_original}")
                response = engine.request_hint(item, response.verification)
        assert blocked == [], "\n".join(blocked)
