"""Test cho lõi so sánh tương đương (Phần D0).

Đây là bộ test quan trọng nhất dự án: mọi verifier của 4 môn đều dựng trên file
này, nên một lỗi ở đây sẽ lan ra toàn hệ thống.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import sympy as sp

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.verify.equivalence import (  # noqa: E402
    ParseError,
    equal_up_to_constant,
    expr_equal,
    is_antiderivative_of,
    matrix_equal,
    number_equal,
    numeric_equal,
    parallel_vectors,
    parse_math,
    set_equal,
)


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------

class TestParsing:
    @pytest.mark.parametrize(
        "text, expected",
        [
            ("x^2", "x**2"),
            ("2x", "2*x"),
            ("2x^2 + 3x", "2*x**2 + 3*x"),
            ("sqrt(x)", "sqrt(x)"),
            ("sin(x)^2", "sin(x)**2"),
        ],
    )
    def test_cach_viet_tu_nhien_cua_sinh_vien(self, text: str, expected: str) -> None:
        assert parse_math(text) == parse_math(expected)

    def test_ky_tu_unicode_khi_copy_tu_word(self) -> None:
        # Dấu trừ Unicode và ký hiệu pi/căn hay dính vào khi copy từ PDF.
        assert parse_math("x − 1") == parse_math("x - 1")
        assert parse_math("√x") == parse_math("sqrt(x)")
        assert parse_math("2π") == parse_math("2*pi")

    def test_tu_choi_bieu_thuc_rong(self) -> None:
        with pytest.raises(ParseError):
            parse_math("   ")

    def test_chan_code_injection(self) -> None:
        """Namespace liệt kê trắng phải chặn được truy cập hàm nguy hiểm."""
        for payload in ["__import__('os')", "open('x')", "eval('1')"]:
            with pytest.raises(ParseError):
                parse_math(payload)


# --------------------------------------------------------------------------
# Tương đương cơ bản
# --------------------------------------------------------------------------

class TestExprEqual:
    @pytest.mark.parametrize(
        "lhs, rhs",
        [
            ("(x+1)**2", "x**2 + 2*x + 1"),
            ("sin(x)**2 + cos(x)**2", "1"),
            ("(x**2 - 1)/(x - 1)", "x + 1"),
            ("exp(log(x))", "x"),
            ("log(x**2)", "2*log(x)"),          # đúng trên miền dương
            ("sin(2*x)", "2*sin(x)*cos(x)"),
            ("x/2 + x/2", "x"),
        ],
    )
    def test_tuong_duong(self, lhs: str, rhs: str) -> None:
        result = expr_equal(lhs, rhs)
        assert result.equal, f"{lhs} phải tương đương {rhs}: {result.detail}"

    @pytest.mark.parametrize(
        "lhs, rhs",
        [
            ("x**2", "x**3"),
            ("sin(x)", "cos(x)"),
            ("(x+1)**2", "x**2 + 1"),           # lỗi khai triển kinh điển
            ("1/(x+1)", "1/x + 1"),             # lỗi tách phân thức kinh điển
            ("sqrt(x+1)", "sqrt(x) + 1"),       # lỗi căn kinh điển
            ("2*x", "x**2"),
        ],
    )
    def test_khong_tuong_duong(self, lhs: str, rhs: str) -> None:
        result = expr_equal(lhs, rhs)
        assert not result.equal, f"{lhs} KHÔNG được coi là tương đương {rhs}"
        assert result.counterexample is not None, "Phải đưa ra được phản ví dụ"

    def test_phu_dinh_phai_nhanh_va_chac_chan(self) -> None:
        """Lấy mẫu số học phủ định thì độ tin cậy phải là tuyệt đối."""
        result = expr_equal("x**2 + 1", "x**2 + 2")
        assert not result.equal
        assert result.confidence == 1.0
        assert result.method == "numeric"

    def test_hang_so_thuan(self) -> None:
        assert expr_equal("2 + 2", "4").equal
        assert not expr_equal("2 + 2", "5").equal


class TestNumericEqual:
    def test_phan_biet_tren_mien_thuc(self) -> None:
        """sqrt(x**2) và x chỉ khác nhau khi x âm — phải chọn miền phù hợp."""
        assert numeric_equal(parse_math("sqrt(x**2)"), parse_math("x"), domain="positive").equal
        assert not numeric_equal(parse_math("sqrt(x**2)"), parse_math("x"), domain="real").equal

    def test_bo_qua_diem_ngoai_mien_xac_dinh(self) -> None:
        """1/(x-1) không xác định tại x=1, nhưng vẫn so sánh được ở nơi khác."""
        result = expr_equal("1/(x-1)", "1/(x-1)")
        assert result.equal


# --------------------------------------------------------------------------
# Nguyên hàm — lõi chấm bài MAE101
# --------------------------------------------------------------------------

class TestAntiderivative:
    @pytest.mark.parametrize(
        "answer, integrand",
        [
            ("x**3/3", "x**2"),
            ("log(x)", "1/x"),
            ("sin(x)", "cos(x)"),
            ("-cos(x)", "sin(x)"),
            ("exp(2*x)/2", "exp(2*x)"),
            ("x*log(x) - x", "log(x)"),                 # tích phân từng phần
            ("(x**2+1)**4/8", "x*(x**2+1)**3"),         # đổi biến
            ("tan(x)", "1/cos(x)**2"),
        ],
    )
    def test_nguyen_ham_dung(self, answer: str, integrand: str) -> None:
        result = is_antiderivative_of(answer, integrand, "x")
        assert result.equal, f"{answer} phải là nguyên hàm của {integrand}: {result.detail}"

    @pytest.mark.parametrize(
        "answer, integrand",
        [
            ("x**3", "x**2"),                   # quên chia cho 3
            ("x**2/2", "x**2"),                 # sai luỹ thừa
            ("exp(2*x)", "exp(2*x)"),           # quên chia cho 2 khi đổi biến
            ("(x**2+1)**4", "x*(x**2+1)**3"),   # quên hệ số khi đổi biến
            ("log(x)", "1/x**2"),
        ],
    )
    def test_nguyen_ham_sai(self, answer: str, integrand: str) -> None:
        assert not is_antiderivative_of(answer, integrand, "x").equal

    def test_chap_nhan_moi_dang_tuong_duong(self) -> None:
        """Điểm mạnh của phương pháp đạo hàm ngược: không cần liệt kê dạng đúng."""
        # Ba cách viết khác hẳn nhau của cùng một nguyên hàm của sin(x)*cos(x).
        for answer in ["sin(x)**2/2", "-cos(x)**2/2", "-cos(2*x)/4"]:
            result = is_antiderivative_of(answer, "sin(x)*cos(x)", "x")
            assert result.equal, f"{answer} phải được chấp nhận: {result.detail}"

    def test_hang_so_tich_phan_khong_anh_huong(self) -> None:
        assert is_antiderivative_of("x**3/3 + 7", "x**2", "x").equal


class TestEqualUpToConstant:
    def test_lech_hang_so_thi_van_bang(self) -> None:
        assert equal_up_to_constant("tan(x)", "tan(x) + 5", "x").equal
        assert equal_up_to_constant("sin(x)**2", "-cos(x)**2", "x").equal

    def test_lech_nhieu_hon_hang_so_thi_khac(self) -> None:
        assert not equal_up_to_constant("x**2", "x**3", "x").equal
        assert not equal_up_to_constant("sin(x)", "sin(x)*2", "x").equal


# --------------------------------------------------------------------------
# So sánh theo loại đáp án
# --------------------------------------------------------------------------

class TestAnswerTypes:
    def test_tap_nghiem_khong_quan_tam_thu_tu(self) -> None:
        assert set_equal([1, 3], [3, 1]).equal
        assert set_equal(["1", "3"], ["3", "1"]).equal
        assert not set_equal([1, 3], [1, 4]).equal
        assert not set_equal([1, 3], [1, 3, 5]).equal

    def test_so_hoc_co_dung_sai_cho_viec_tra_bang(self) -> None:
        # Sinh viên tra bảng z và làm tròn — không được chấm sai vì chuyện đó.
        assert number_equal(1.96, 1.959964, rel_tol=1e-3).equal
        assert not number_equal(1.96, 2.58, rel_tol=1e-3).equal

    def test_ma_tran(self) -> None:
        assert matrix_equal([[1, 2], [3, 4]], [[1, 2], [3, 4]]).equal
        assert not matrix_equal([[1, 2], [3, 4]], [[1, 2], [3, 5]]).equal
        assert not matrix_equal([[1, 2]], [[1, 2], [3, 4]]).equal

    def test_vector_rieng_chap_nhan_moi_boi_vo_huong(self) -> None:
        """Vector riêng xác định sai khác một bội vô hướng — phải chấm đúng."""
        assert parallel_vectors([[1], [-1]], [[2], [-2]]).equal
        assert parallel_vectors([[1], [-1]], [[-1], [1]]).equal
        assert not parallel_vectors([[1], [-1]], [[1], [1]]).equal

    def test_vector_khong_khong_phai_vector_rieng(self) -> None:
        assert not parallel_vectors([[0], [0]], [[1], [1]]).equal


class TestSubscriptedSymbols:
    """Hồi quy: tên có chữ số từng không parse được, rồi suýt bị tách thành tích.

    Bộ tách ký hiệu mặc định của SymPy biến ``C1`` thành ``C*1``. Nếu vậy thì hai
    hằng số độc lập ``C1``, ``C2`` của nghiệm tổng quát ODE sập thành một, và lời
    giải đúng bị chấm là thiếu hằng số.
    """

    def test_giu_nguyen_ten_co_chu_so(self) -> None:
        expression = parse_math("C1*exp(x) + C2*exp(2*x)")
        assert {str(s) for s in expression.free_symbols} == {"C1", "C2", "x"}

    def test_hai_hang_so_khong_bi_gop(self) -> None:
        assert parse_math("C1") != parse_math("C2")

    def test_van_tach_tich_khi_khong_co_chu_so(self) -> None:
        assert parse_math("2xy") == parse_math("2*x*y")

    def test_e_mu_x_theo_cach_viet_cua_sinh_vien(self) -> None:
        assert parse_math("e^(2x)") == parse_math("exp(2*x)")


class TestImplicitMultiplicationBeforeParenthesis:
    """Hồi quy: ``n(n+1)`` từng bị hiểu là hàm n áp dụng lên n+1."""

    @pytest.mark.parametrize("text, expected", [
        ("n(n+1)/2", "n*(n+1)/2"),
        ("x(x^2+1)^3", "x*(x**2+1)**3"),
        ("2x(x-1)", "2*x*(x-1)"),
        ("C1(1 + x)", "C1*(1 + x)"),
    ])
    def test_ten_truoc_ngoac_la_phep_nhan(self, text: str, expected: str) -> None:
        assert parse_math(text) == parse_math(expected)

    def test_ham_that_van_la_ham(self) -> None:
        assert parse_math("sin(x)") == sp.sin(sp.Symbol("x"))
        assert parse_math("sqrt(x+1)") == sp.sqrt(sp.Symbol("x") + 1)
