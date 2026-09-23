"""Guardrail trên đáp án có cấu trúc — ma trận, vector, nghiệm tham số, gradient.

Bản guardrail trước tự so khớp với đáp án chuẩn nên để lọt đúng những dạng này.
Bản hiện tại hỏi thẳng verifier, nên mọi dạng tương đương đều bị chặn.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.itembank import ItemBank, load_course_error_codes  # noqa: E402
from src.core.schema import Submission  # noqa: E402
from src.tutor.guardrail import check_leak, extract_candidates  # noqa: E402
from src.tutor.hint_policy import HintLevel  # noqa: E402
from src.tutor.hints import HintGenerator, TutorEngine  # noqa: E402
from src.verify.registry import verifier_for  # noqa: E402

LOW = HintLevel.PITFALL  # mức chưa được phép nói đáp án


class _Banks:
    """Tra bài theo mã ở cả hai môn — tiền tố mã bài cho biết bài thuộc môn nào."""

    def __init__(self) -> None:
        self.banks = {s: ItemBank.load(s) for s in ("MAE101", "MAI391")}

    def get(self, item_id: str):
        return self.banks[item_id.split("-", 1)[0]].get(item_id)


@pytest.fixture(scope="module")
def bank() -> _Banks:
    return _Banks()


def leaked(bank, item_id: str, text: str) -> bool:
    return check_leak(text, bank.get(item_id), LOW).leaked


class TestCatchesMAI391Leaks:
    @pytest.mark.parametrize("text", [
        "Em thử v = [1, 1] xem sao",
        "Vector [2, 2] thoả mãn đấy",          # bội vô hướng khác
        "Đáp án là (-5, -5)",                   # ngoặc tròn, bội âm
    ])
    def test_vector_rieng(self, bank, text: str) -> None:
        assert leaked(bank, "MAE101-LA-VEC-001", text)

    def test_ma_tran_nghich_dao(self, bank) -> None:
        assert leaked(bank, "MAE101-LA-INV-001", "Kết quả: [[3/5, -7/10], [-1/5, 2/5]]")
        assert leaked(bank, "MAE101-LA-INV-001", "Nghịch đảo là [[0.6, -0.7], [-0.2, 0.4]] nhé")

    @pytest.mark.parametrize("text", [
        "Nghiệm là [1 - s - t, s, t]",
        "Họ nghiệm [u, v, 1 - u - v]",          # tham số hoá khác hẳn
    ])
    def test_nghiem_tham_so(self, bank, text: str) -> None:
        assert leaked(bank, "MAE101-LA-SYS-003", text)

    def test_gradient_viet_dang_khac(self, bank) -> None:
        """∇f = [2xy, x² + 3] viết thành [2*y*x, 3 + x**2] vẫn là lộ đáp án."""
        assert leaked(bank, "MAI391-GRAD-001", "Thử ∇f = [2*y*x, 3 + x**2] xem")

    def test_diem_dung(self, bank) -> None:
        assert leaked(bank, "MAI391-CRIT-001", "Điểm dừng là (1, -2) đấy")

    def test_dap_an_bang_loi(self, bank) -> None:
        assert leaked(bank, "MAE101-LA-SYS-005", "Để ý là hệ này vô nghiệm đấy")
        assert leaked(bank, "MAE101-LA-INV-003", "Ma trận này không khả nghịch")

    def test_dap_an_la_mot_con_so(self, bank) -> None:
        assert leaked(bank, "MAE101-LA-DET-003", "Định thức bằng 10")


class TestDoesNotBlockLegitimateHints:
    def test_goi_y_phuong_phap(self, bank) -> None:
        assert not leaked(bank, "MAE101-LA-VEC-001", "Em thử giải hệ (A - 3I)v = 0 xem")

    def test_nhac_lai_ma_tran_de_bai(self, bank) -> None:
        """Nhắc lại ma trận A của đề không phải là lộ ma trận nghịch đảo."""
        assert not leaked(bank, "MAE101-LA-INV-001", "Với A = [[4, 7], [2, 6]], em tính det(A) trước")

    def test_so_thu_tu_buoc_khong_bi_coi_la_dap_an(self, bank) -> None:
        """Đáp án bằng 1, nhưng "bước 1" là số thứ tự — không được chặn oan."""
        assert not leaked(bank, "MAE101-LA-DET-002", "Em xem lại bước 1 và hàng 1 nhé")

    def test_ket_luan_sai_khong_phai_lo(self, bank) -> None:
        """Nói 'vô nghiệm' ở một hệ CÓ nghiệm không làm lộ gì cả."""
        assert not leaked(bank, "MAE101-LA-SYS-001", "Nhiều bạn kết luận vô nghiệm ở bài này")

    def test_muc_cao_duoc_phep(self, bank) -> None:
        assert not check_leak("Đáp án là [1, 1]", bank.get("MAE101-LA-VEC-001"), HintLevel.FULL).leaked


class TestExtraction:
    def test_trich_duoc_ma_tran_long(self) -> None:
        assert "[[3/5, -7/10], [-1/5, 2/5]]" in extract_candidates("Kết quả: [[3/5, -7/10], [-1/5, 2/5]]")

    def test_khong_nham_loi_goi_ham_la_vector(self) -> None:
        assert "(1, 2)" not in extract_candidates("Xét f(1, 2) trước đã")

    def test_go_dau_cau_dinh_vao_bieu_thuc(self) -> None:
        """Ca thật từ EXP-8: Qwen viết "... là tan(x) + C." và lọt guardrail.

        Dấu chấm cuối câu dính vào token cuối nên ứng viên là ``C.``, parse hỏng.
        """
        assert "tan(x) + C" in extract_candidates("Nguyên hàm là tan(x) + C. Em kiểm tra lại nhé")


class TestPunctuationLeak:
    def test_dap_an_cuoi_cau_van_bi_chan(self, bank) -> None:
        assert leaked(bank, "MAE101-INT-009", "Nguyên hàm của 1/cos²(x) là tan(x) + C. Em thử đạo hàm lại xem?")

    def test_goi_y_hop_le_khong_bi_chan_oan(self, bank) -> None:
        assert not leaked(bank, "MAE101-INT-009", "Em thử nhớ lại đạo hàm của hàm nào cho ra 1/cos²(x) nhé.")


class TestTemplateHintsNeverLeak:
    """Chạy cả thang gợi ý trên MỌI bài có đáp án cấu trúc — gợi ý template không được tự làm lộ đáp án."""

    @pytest.mark.parametrize("subject", ["MAE101", "MAI391"])
    def test_khong_muc_nao_duoi_4_lo_dap_an(self, bank, subject: str) -> None:
        subject_bank = bank.banks[subject]
        engine = TutorEngine(
            verifier_for(subject),
            HintGenerator(load_course_error_codes(subject), subject_bank.skills, seed=1),
        )
        blocked = []
        for item in subject_bank.items.values():
            if item.answer_type.value == "antiderivative":
                continue  # nguyên hàm đã có bộ test riêng trong test_tutor.py
            response = engine.submit(item, Submission(item_id=item.item_id, final_answer="[0, 0, 0, 0]"))
            if response.hint is None:
                continue
            for _ in range(5):
                if response.hint.was_blocked:
                    blocked.append(f"{item.item_id} mức {int(response.hint.level)}: {response.hint.blocked_original}")
                response = engine.request_hint(item, response.verification)
        assert blocked == [], "\n".join(blocked)
