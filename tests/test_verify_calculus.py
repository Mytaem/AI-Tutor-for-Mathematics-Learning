"""Test verifier MAE101.

Hai nhóm test quan trọng nhất:
- Lời giải đúng (mọi dạng viết tương đương) phải LUÔN được chấp nhận.
- Lời giải sai phải bị bắt ĐÚNG mã lỗi, không chỉ báo "sai".
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.schema import AnswerType, Item, Subject, Submission  # noqa: E402
from src.verify.calculus import (  # noqa: E402
    ERR_CONST_FACTOR,
    ERR_DEF_NOT_EVALUATED,
    ERR_NO_CONSTANT,
    ERR_SIGN,
    CalculusVerifier,
)


@pytest.fixture
def verifier() -> CalculusVerifier:
    return CalculusVerifier()


def antiderivative_item(integrand: str, item_id: str = "TEST-INT-001") -> Item:
    return Item(
        item_id=item_id,
        subject=Subject.MAE101,
        skills=["MAE.INT.BASIC"],
        statement_vi=f"Tính nguyên hàm của {integrand}",
        answer_type=AnswerType.ANTIDERIVATIVE,
        integrand=integrand,
        variable="x",
    )


class TestAntiderivativeAccepted:
    @pytest.mark.parametrize(
        "answer",
        ["x**3/3 + C", "x**3/3", "(x**3 + 3)/3", "x*x**2/3 + C"],
    )
    def test_moi_dang_viet_dung_deu_duoc_chap_nhan(self, verifier: CalculusVerifier, answer: str) -> None:
        item = antiderivative_item("x**2")
        result = verifier.verify(item, Submission(item_id=item.item_id, final_answer=answer))
        assert result.final_answer_correct is True, result.notes

    def test_ba_dang_khac_han_nhau_cua_cung_mot_nguyen_ham(self, verifier: CalculusVerifier) -> None:
        """Đây là lý do phải chấm bằng đạo hàm ngược thay vì so khớp dạng chuẩn."""
        item = antiderivative_item("sin(x)*cos(x)")
        for answer in ["sin(x)**2/2 + C", "-cos(x)**2/2 + C", "-cos(2*x)/4 + C"]:
            result = verifier.verify(item, Submission(item_id=item.item_id, final_answer=answer))
            assert result.final_answer_correct is True, f"{answer}: {result.notes}"

    def test_tich_phan_tung_phan(self, verifier: CalculusVerifier) -> None:
        item = antiderivative_item("log(x)")
        result = verifier.verify(item, Submission(item_id=item.item_id, final_answer="x*log(x) - x + C"))
        assert result.final_answer_correct is True


class TestErrorDiagnosis:
    def test_quen_hang_so_tich_phan_van_dung_nhung_bi_nhac(self, verifier: CalculusVerifier) -> None:
        """Thiếu '+ C' là lỗi hình thức: không đánh trượt, chỉ gắn mã lỗi."""
        item = antiderivative_item("x**2")
        result = verifier.verify(item, Submission(item_id=item.item_id, final_answer="x**3/3"))
        assert result.final_answer_correct is True
        assert ERR_NO_CONSTANT in result.candidate_error_codes

    def test_co_hang_so_thi_khong_gan_ma_loi(self, verifier: CalculusVerifier) -> None:
        item = antiderivative_item("x**2")
        result = verifier.verify(item, Submission(item_id=item.item_id, final_answer="x**3/3 + C"))
        assert ERR_NO_CONSTANT not in result.candidate_error_codes

    @pytest.mark.parametrize(
        "integrand, wrong_answer",
        [
            ("x**2", "x**3"),                       # quên chia 3
            ("exp(2*x)", "exp(2*x)"),               # quên chia 2 khi đổi biến
            ("x*(x**2+1)**3", "(x**2+1)**4"),       # quên hệ số 1/8 khi đổi biến
        ],
    )
    def test_sai_dung_mot_he_so_hang(self, verifier: CalculusVerifier, integrand: str, wrong_answer: str) -> None:
        """Lỗi kinh điển nhất khi đổi biến — phải nhận diện được, không chỉ báo 'sai'."""
        item = antiderivative_item(integrand)
        result = verifier.verify(item, Submission(item_id=item.item_id, final_answer=wrong_answer + " + C"))
        assert result.final_answer_correct is False
        assert ERR_CONST_FACTOR in result.candidate_error_codes, result.candidate_error_codes

    def test_sai_dau_toan_cuc(self, verifier: CalculusVerifier) -> None:
        item = antiderivative_item("sin(x)")
        result = verifier.verify(item, Submission(item_id=item.item_id, final_answer="cos(x) + C"))
        assert result.final_answer_correct is False
        assert ERR_SIGN in result.candidate_error_codes
        assert ERR_CONST_FACTOR in result.candidate_error_codes

    def test_sai_ve_ban_chat_thi_khong_gan_ma_he_so(self, verifier: CalculusVerifier) -> None:
        """Đáp án sai hẳn dạng thì không được quy về 'sai hệ số'."""
        item = antiderivative_item("x**2")
        result = verifier.verify(item, Submission(item_id=item.item_id, final_answer="sin(x) + C"))
        assert result.final_answer_correct is False
        assert ERR_CONST_FACTOR not in result.candidate_error_codes


class TestDefiniteIntegral:
    def definite_item(self) -> Item:
        return Item(
            item_id="TEST-DEF-001",
            subject=Subject.MAE101,
            statement_vi="Tính tích phân xác định của x^2 từ 0 đến 1",
            answer_type=AnswerType.NUMBER,
            answer="1/3",
            integrand="x**2",
            variable="x",
            bounds=("0", "1"),
        )

    def test_dap_an_dung(self, verifier: CalculusVerifier) -> None:
        item = self.definite_item()
        result = verifier.verify(item, Submission(item_id=item.item_id, final_answer="1/3"))
        assert result.final_answer_correct is True

    def test_chap_nhan_dang_thap_phan(self, verifier: CalculusVerifier) -> None:
        item = self.definite_item()
        result = verifier.verify(item, Submission(item_id=item.item_id, final_answer="0.3333333"))
        assert result.final_answer_correct is True

    def test_quen_the_can(self, verifier: CalculusVerifier) -> None:
        """Tích phân xác định phải ra số; còn chứa x nghĩa là chưa thế cận."""
        item = self.definite_item()
        result = verifier.verify(item, Submission(item_id=item.item_id, final_answer="x**3/3"))
        assert result.final_answer_correct is False
        assert ERR_DEF_NOT_EVALUATED in result.candidate_error_codes


class TestStepChecking:
    def test_chuoi_bien_doi_dung(self, verifier: CalculusVerifier) -> None:
        item = antiderivative_item("x**2")
        submission = Submission(
            item_id=item.item_id,
            steps=["Integral(x**2, x)", "x**3/3"],
            final_answer="x**3/3 + C",
        )
        result = verifier.verify(item, submission)
        assert result.first_wrong_step is None
        assert result.is_correct is True

    def test_bat_dung_buoc_sai_dau_tien(self, verifier: CalculusVerifier) -> None:
        item = antiderivative_item("x**2")
        submission = Submission(
            item_id=item.item_id,
            steps=["(x+1)**2", "x**2 + 2*x + 1", "x**2 + 1"],
            final_answer="x**3/3 + C",
        )
        result = verifier.verify(item, submission)
        assert result.first_wrong_step == 3, [s.model_dump() for s in result.step_results]

    def test_buoc_doi_bien_bao_khong_kiem_chung_duoc_chu_khong_bao_sai(
        self, verifier: CalculusVerifier
    ) -> None:
        """Quy tắc sống còn: không đủ cơ sở thì im lặng, tuyệt đối không kết tội."""
        item = antiderivative_item("x*(x**2+1)**3")
        submission = Submission(
            item_id=item.item_id,
            steps=["Integral(x*(x**2+1)**3, x)", "Integral(u**3/2, u)"],
            final_answer="(x**2+1)**4/8 + C",
        )
        result = verifier.verify(item, submission)
        assert result.first_wrong_step is None, "Không được coi bước đổi biến là bước sai"
        assert result.has_unverifiable_steps

class TestSubstitutionSteps:
    """Kiểm chứng chuỗi bước có đổi biến — phần toán khó nhất của việc chấm bước."""

    def item(self) -> Item:
        return antiderivative_item("x*(x**2+1)**3", item_id="TEST-SUBST-001")

    def test_chuoi_doi_bien_dung_hoan_chinh(self, verifier: CalculusVerifier) -> None:
        item = self.item()
        submission = Submission(
            item_id=item.item_id,
            steps=[
                "Integral(x*(x**2+1)**3, x)",
                "u = x**2 + 1",           # khai báo phép thế
                "Integral(u**3/2, u)",    # du = 2x dx nên x dx = du/2
                "u**4/8",
                "(x**2+1)**4/8",
            ],
            final_answer="(x**2+1)**4/8 + C",
        )
        result = verifier.verify(item, submission)
        assert result.first_wrong_step is None, [s.model_dump() for s in result.step_results]
        assert not result.has_unverifiable_steps, "Đã khai báo phép thế thì phải kiểm chứng được hết"
        assert result.is_correct is True

    def test_bat_duoc_loi_quen_he_so_du_ngay_tai_buoc_doi_bien(
        self, verifier: CalculusVerifier
    ) -> None:
        """Lỗi kinh điển: đặt u = x²+1 nhưng quên du = 2x dx, viết thành ∫u³ du.

        Phải bắt được ĐÚNG tại bước đổi biến, chứ không đợi tới đáp án cuối —
        đó mới là chỗ gợi ý có giá trị sư phạm.
        """
        item = self.item()
        submission = Submission(
            item_id=item.item_id,
            steps=[
                "Integral(x*(x**2+1)**3, x)",
                "u = x**2 + 1",
                "Integral(u**3, u)",      # sai: thiếu hệ số 1/2
            ],
            final_answer="(x**2+1)**4/4 + C",
        )
        result = verifier.verify(item, submission)
        assert result.first_wrong_step == 3, [s.model_dump() for s in result.step_results]

    def test_khong_khai_bao_phep_the_thi_van_im_lang(self, verifier: CalculusVerifier) -> None:
        """Không có khai báo thì không đủ cơ sở — báo chưa kiểm chứng được, không báo sai."""
        item = self.item()
        submission = Submission(
            item_id=item.item_id,
            steps=["Integral(x*(x**2+1)**3, x)", "Integral(u**3/2, u)"],
            final_answer="(x**2+1)**4/8 + C",
        )
        result = verifier.verify(item, submission)
        assert result.first_wrong_step is None
        assert result.has_unverifiable_steps

    def test_khong_nham_dong_dat_ten_ket_qua_la_phep_the(self, verifier: CalculusVerifier) -> None:
        """Dòng 'I = ...' là đặt tên cho kết quả, không phải đổi biến."""
        item = antiderivative_item("x**2")
        submission = Submission(
            item_id=item.item_id,
            steps=["Integral(x**2, x)", "I = x**3/3"],
            final_answer="x**3/3 + C",
        )
        result = verifier.verify(item, submission)
        # Vế phải chứa biến gốc x nên vẫn bị coi là phép thế — chấp nhận được,
        # miễn là không sinh ra kết luận SAI.
        assert result.first_wrong_step is None


class TestStepCheckingContinued:
    def test_dap_an_dung_nhung_buoc_sai_thi_chua_dat(self, verifier: CalculusVerifier) -> None:
        item = antiderivative_item("x**2")
        submission = Submission(
            item_id=item.item_id,
            steps=["(x+1)**2", "x**2 + 1"],
            final_answer="x**3/3 + C",
        )
        result = verifier.verify(item, submission)
        assert result.final_answer_correct is True
        assert result.is_correct is False, "Sai bù trừ vẫn phải bị phát hiện"


class TestInputRobustness:
    def test_khong_doc_duoc_thi_hoi_lai_chu_khong_cham_sai(self, verifier: CalculusVerifier) -> None:
        """Lỗi nhập liệu KHÁC lỗi toán học — không được kết luận sinh viên sai."""
        item = antiderivative_item("x**2")
        result = verifier.verify(item, Submission(item_id=item.item_id, final_answer="x**3/3 +++"))
        assert result.final_answer_correct is None
        assert result.is_correct is False

    def test_cach_viet_tu_nhien(self, verifier: CalculusVerifier) -> None:
        item = antiderivative_item("x**2")
        result = verifier.verify(item, Submission(item_id=item.item_id, final_answer="x^3/3 + C"))
        assert result.final_answer_correct is True

    def test_dap_an_rong(self, verifier: CalculusVerifier) -> None:
        item = antiderivative_item("x**2")
        result = verifier.verify(item, Submission(item_id=item.item_id, final_answer="   "))
        assert result.final_answer_correct is False
