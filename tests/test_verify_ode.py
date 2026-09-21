"""Test bộ chấm phương trình vi phân — thành phần tuỳ chọn, không gắn với môn nào.

Bài ODE đã rút khỏi ngân hàng đề (MAI391 thật không dạy ODE), nên test dùng dữ
liệu mẫu trong tests/fixtures/.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.itembank import load_items  # noqa: E402
from src.core.schema import Submission  # noqa: E402
from src.verify import ode as L  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(scope="module")
def items() -> dict:
    return {item.item_id: item for item in load_items(FIXTURES / "ode_items.jsonl")}


@pytest.fixture(scope="module")
def verifier() -> L.ODEVerifier:
    return L.ODEVerifier()


def check(verifier, items, item_id: str, answer: str):
    return verifier.verify(items[item_id], Submission(item_id=item_id, final_answer=answer))


def test_moi_dap_an_mau_deu_dung(verifier, items) -> None:
    for item in items.values():
        assert check(verifier, items, item.item_id, item.answer_text).is_correct, item.item_id


# ==========================================================================
# Phương trình vi phân
# ==========================================================================

class TestODE:
    @pytest.mark.parametrize("answer", [
        "C1*exp(x) + C2*exp(2*x)",
        "y = C1 e^x + C2 e^(2x)",          # cách viết tự nhiên của sinh viên
        "y(x) = A*exp(2*x) + B*exp(x)",    # tên hằng số khác, thứ tự khác
    ])
    def test_nghiem_tong_quat_moi_cach_viet(self, verifier, items, answer: str) -> None:
        result = check(verifier, items, "MAI391-ODE-002", answer)
        assert result.is_correct, f"{answer}: {result.notes}"

    def test_thieu_hang_so(self, verifier, items) -> None:
        result = check(verifier, items, "MAI391-ODE-002", "C1*exp(x)")
        assert L.ERR_ODE_INCOMPLETE in result.candidate_error_codes

    def test_nghiem_kep_hai_hang_so_phu_thuoc(self, verifier, items) -> None:
        """Lỗi kinh điển nhất: nghiệm kép r = 1 mà viết C1·eˣ + C2·eˣ.

        Có hai ký hiệu hằng số nhưng chúng gộp lại được thành một — đếm ký hiệu
        sẽ chấm bài này là đúng. Phải đếm số hằng số ĐỘC LẬP.
        """
        result = check(verifier, items, "MAI391-ODE-004", "C1*exp(x) + C2*exp(x)")
        assert result.final_answer_correct is False
        assert L.ERR_ODE_INCOMPLETE in result.candidate_error_codes

    def test_nghiem_kep_dung(self, verifier, items) -> None:
        assert check(verifier, items, "MAI391-ODE-004", "(C1 + C2*x)*exp(x)").is_correct
        assert check(verifier, items, "MAI391-ODE-004", "C1*exp(x) + C2*x*exp(x)").is_correct

    def test_nghiem_luong_giac(self, verifier, items) -> None:
        assert check(verifier, items, "MAI391-ODE-003", "C1*cos(2x) + C2*sin(2x)").is_correct

    def test_khong_phai_nghiem(self, verifier, items) -> None:
        result = check(verifier, items, "MAI391-ODE-002", "C1*exp(-x) + C2*exp(2*x)")
        assert L.ERR_ODE_NOTSOLUTION in result.candidate_error_codes

    def test_chi_co_nghiem_rieng(self, verifier, items) -> None:
        """y' − y = x: −x − 1 thoả phương trình nhưng thiếu phần C·eˣ."""
        result = check(verifier, items, "MAI391-ODE-005", "-x - 1")
        assert L.ERR_ODE_NOHOMO in result.candidate_error_codes

    def test_khong_thuan_nhat_dung(self, verifier, items) -> None:
        assert check(verifier, items, "MAI391-ODE-005", "C*exp(x) - x - 1").is_correct

    def test_bai_toan_gia_tri_dau(self, verifier, items) -> None:
        assert check(verifier, items, "MAI391-ODE-006", "3*exp(-x)").is_correct
        assert check(verifier, items, "MAI391-ODE-007", "2*sin(x)").is_correct

    def test_chua_dung_dieu_kien_dau(self, verifier, items) -> None:
        result = check(verifier, items, "MAI391-ODE-006", "C1*exp(-x)")
        assert L.ERR_ODE_IC_UNSOLVED in result.candidate_error_codes

    def test_sai_dieu_kien_dau(self, verifier, items) -> None:
        assert L.ERR_ODE_IC in check(verifier, items, "MAI391-ODE-006", "2*exp(-x)").candidate_error_codes

    def test_sai_dieu_kien_dau_cua_dao_ham(self, verifier, items) -> None:
        """sin(x) thoả y(0) = 0 nhưng y'(0) = 1 chứ không phải 2."""
        result = check(verifier, items, "MAI391-ODE-007", "sin(x)")
        assert L.ERR_ODE_IC in result.candidate_error_codes
        assert "y'(0)" in result.notes[0]


