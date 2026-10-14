"""Test bộ sinh đề giới hạn và đạo hàm, cùng các luật chẩn đoán mới.

File này sinh ra để bịt một lỗ mà cây nội dung phơi ra: hai chương ĐẦU TIÊN của
MAE101 có 0 đề, nên sinh viên chọn chương "Giới hạn và liên tục" thì không luyện
được gì.

Thứ đáng canh nhất không phải "có sinh được đề không" mà là **đề có bắt đúng kỹ
năng nó khai báo không**. Một bài dán nhãn "quy tắc hàm hợp" mà giải được bằng
công thức lũy thừa đơn thuần sẽ làm mô hình năng lực ghi nhận một kỹ năng mà
sinh viên chưa hề dùng tới — sai lặng lẽ, và sai ở đúng chỗ khó phát hiện nhất.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import sympy as sp

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.itembank import ItemBank  # noqa: E402
from src.core.schema import Submission  # noqa: E402
from src.data_gen.calculus_items import generate, template_ids  # noqa: E402
from src.verify.calculus import (  # noqa: E402
    ERR_DER_CHAIN_NOINNER,
    ERR_DER_POWER_NODEC,
    ERR_DER_POWER_NOMULT,
    ERR_DER_PRODUCT_SEPARATE,
    ERR_DER_QUOTIENT_SIGN,
    ERR_LIM_INDET_ZERO,
    ERR_LIM_INF_CONSTTERM,
    ERR_LIM_SIGN,
)
from src.verify.registry import verifier_for  # noqa: E402

X = sp.Symbol("x")


@pytest.fixture(scope="module")
def items():
    return generate(len(template_ids()) * 4, validate=True)


@pytest.fixture(scope="module")
def verifier():
    return verifier_for("MAE101")


def by_template(items, name: str):
    return [item for item in items if item.meta.get("template") == name]


class TestSinhDe:
    def test_moi_dang_bai_sinh_duoc(self, items) -> None:
        produced = {item.meta.get("template") for item in items}
        missing = [name for name in template_ids() if name not in produced]
        assert missing == [], f"dạng bài không sinh được: {missing}"

    def test_de_sinh_ra_tu_cham_dung(self, items, verifier) -> None:
        """Hàng rào duy nhất của bộ sinh đề: verifier phải chấm lại được."""
        for item in items:
            result = verifier.verify(item, Submission(
                item_id=item.item_id, final_answer=item.answer_text))
            assert result.final_answer_correct is True, f"{item.item_id}: {item.statement_vi}"

    def test_ky_nang_thuoc_dung_mon(self, items) -> None:
        bank = ItemBank.load("MAE101")
        for item in items:
            for skill in item.skills:
                assert skill in bank.skills, f"{item.item_id} gắn kỹ năng lạ: {skill}"

    def test_phu_dung_nam_ky_nang_con_thieu(self, items) -> None:
        """Năm kỹ năng này trước đây không có một bài nào."""
        covered = {skill for item in items for skill in item.skills}
        assert {"MAE.LIM.BASIC", "MAE.LIM.INDET",
                "MAE.DER.BASIC", "MAE.DER.PRODUCT", "MAE.DER.CHAIN"} <= covered

    def test_cung_seed_ra_cung_de(self) -> None:
        first = generate(8, seed=99, validate=False)
        second = generate(8, seed=99, validate=False)
        assert [i.statement_vi for i in first] == [i.statement_vi for i in second]
        assert [i.answer_text for i in first] == [i.answer_text for i in second]


class TestDeDungVoiKyNang:
    """Đề phải thật sự cần đúng quy tắc mà kỹ năng của nó khai báo."""

    def test_bai_quy_tac_tich_co_hai_thua_so_phu_thuoc_x(self, items) -> None:
        """Một thừa số là hằng thì bài giải được bằng công thức lũy thừa."""
        for item in by_template(items, "derivative_product"):
            expr = sp.sympify(item.meta["expr"])
            varying = [f for f in sp.Mul.make_args(expr) if f.has(X)]
            assert len(varying) >= 2, item.statement_vi

    def test_bai_ham_hop_co_ham_trong_khong_tam_thuong(self, items) -> None:
        """Hàm trong có đạo hàm bằng 1 thì quy tắc hàm hợp không cần dùng."""
        for item in by_template(items, "derivative_chain"):
            expr = sp.sympify(item.meta["expr"])
            inner = expr.base if isinstance(expr, sp.Pow) else expr.args[0]
            assert sp.simplify(sp.diff(inner, X) - 1) != 0, item.statement_vi

    def test_bai_dang_vo_dinh_that_su_vo_dinh(self, items) -> None:
        """Mẫu phải triệt tiêu tại điểm lấy giới hạn, nếu không thì thay thẳng được."""
        for item in by_template(items, "limit_factor"):
            expr = sp.sympify(item.meta["expr"])
            _, denominator = sp.fraction(expr)
            assert denominator.subs(X, item.meta["point"]) == 0, item.statement_vi

    def test_bai_thay_thang_khong_bi_vo_dinh(self, items) -> None:
        """Ngược lại: bài «thay trực tiếp» không được là dạng vô định."""
        for item in by_template(items, "limit_rational"):
            expr = sp.sympify(item.meta["expr"])
            _, denominator = sp.fraction(expr)
            assert denominator.subs(X, item.meta["point"]) != 0, item.statement_vi


class TestChanDoanGioiHan:
    def test_tra_0_cho_dang_vo_dinh(self, items, verifier) -> None:
        item = by_template(items, "limit_factor")[0]
        result = verifier.verify(item, Submission(item_id=item.item_id, final_answer="0"))
        assert ERR_LIM_INDET_ZERO in result.candidate_error_codes

    def test_lay_ti_so_hang_tu_do_khi_x_ra_vo_cuc(self, items, verifier) -> None:
        for item in by_template(items, "limit_infinity"):
            expr = sp.sympify(item.meta["expr"])
            numerator, denominator = sp.fraction(expr)
            top = sp.Poly(numerator, X).coeff_monomial(1)
            bottom = sp.Poly(denominator, X).coeff_monomial(1)
            if not bottom:
                continue
            wrong = sp.nsimplify(sp.Rational(int(top), int(bottom)))
            if sp.simplify(wrong - sp.sympify(item.answer)) == 0:
                continue          # lỗi này trùng đáp án đúng, không kiểm được ở đây
            result = verifier.verify(item, Submission(
                item_id=item.item_id, final_answer=str(wrong)))
            assert ERR_LIM_INF_CONSTTERM in result.candidate_error_codes
            return
        pytest.skip("không có bài nào tách được lỗi này khỏi đáp án đúng")

    def test_sai_dau(self, items, verifier) -> None:
        for item in by_template(items, "limit_polynomial"):
            correct = sp.sympify(item.answer)
            if correct == 0:
                continue
            result = verifier.verify(item, Submission(
                item_id=item.item_id, final_answer=str(-correct)))
            assert ERR_LIM_SIGN in result.candidate_error_codes
            return

    def test_dap_an_dung_thi_khong_gan_ma_loi_nao(self, items, verifier) -> None:
        """Gắn mã lỗi cho một bài làm ĐÚNG là kiểu sai tệ nhất của tầng chẩn đoán."""
        for item in items:
            result = verifier.verify(item, Submission(
                item_id=item.item_id, final_answer=item.answer_text))
            assert result.candidate_error_codes == [], f"{item.item_id}: {result.candidate_error_codes}"


class TestChanDoanDaoHam:
    def test_quen_giam_bac(self, items, verifier) -> None:
        item = by_template(items, "derivative_power")[0]
        expr = sp.sympify(item.meta["expr"])
        wrong = sum(
            coefficient * exponent * X**exponent
            for coefficient, exponent in
            (t.as_coeff_exponent(X) for t in sp.Add.make_args(sp.expand(expr)))
        )
        result = verifier.verify(item, Submission(
            item_id=item.item_id, final_answer=str(sp.simplify(wrong))))
        assert ERR_DER_POWER_NODEC in result.candidate_error_codes

    def test_quen_nhan_so_mu(self, items, verifier) -> None:
        item = by_template(items, "derivative_power")[0]
        expr = sp.sympify(item.meta["expr"])
        wrong = sum(
            coefficient * X ** (exponent - 1)
            for coefficient, exponent in
            (t.as_coeff_exponent(X) for t in sp.Add.make_args(sp.expand(expr)))
        )
        result = verifier.verify(item, Submission(
            item_id=item.item_id, final_answer=str(sp.simplify(wrong))))
        assert ERR_DER_POWER_NOMULT in result.candidate_error_codes

    def test_dao_ham_tich_bang_tich_hai_dao_ham(self, items, verifier) -> None:
        item = by_template(items, "derivative_product")[0]
        expr = sp.sympify(item.meta["expr"])
        wrong = sp.Mul(*[sp.diff(f, X) for f in sp.Mul.make_args(expr)])
        result = verifier.verify(item, Submission(
            item_id=item.item_id, final_answer=str(sp.simplify(wrong))))
        assert ERR_DER_PRODUCT_SEPARATE in result.candidate_error_codes

    def test_sai_dau_quy_tac_thuong(self, items, verifier) -> None:
        item = by_template(items, "derivative_quotient")[0]
        u, v = sp.fraction(sp.sympify(item.meta["expr"]))
        wrong = (sp.diff(u, X) * v + u * sp.diff(v, X)) / v**2
        result = verifier.verify(item, Submission(
            item_id=item.item_id, final_answer=str(sp.simplify(wrong))))
        assert ERR_DER_QUOTIENT_SIGN in result.candidate_error_codes

    def test_quen_nhan_dao_ham_ham_trong(self, items, verifier) -> None:
        for item in by_template(items, "derivative_chain"):
            expr = sp.sympify(item.meta["expr"])
            if isinstance(expr, sp.Pow) and expr.exp.is_Integer:
                wrong = expr.exp * expr.base ** (expr.exp - 1)
            elif isinstance(expr, sp.Function) and len(expr.args) == 1:
                wrong = sp.diff(expr.func(X), X).subs(X, expr.args[0])
            else:
                continue
            result = verifier.verify(item, Submission(
                item_id=item.item_id, final_answer=str(sp.simplify(wrong))))
            assert ERR_DER_CHAIN_NOINNER in result.candidate_error_codes
            return
