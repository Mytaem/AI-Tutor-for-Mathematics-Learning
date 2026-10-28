import pytest

from src.verify.equivalence import ParseError, expr_equal, parse_math


@pytest.mark.parametrize(("written", "meant"), [
    ("x²/2 + C", "x**2/2 + C"),          # chép ký hiệu từ đề
    ("x³/3 + C", "x**3/3 + C"),
    ("x⁻¹", "1/x"),
    ("x·e^(x²)", "x*exp(x**2)"),
    ("ln|x| + C", "log(Abs(x)) + C"),
    ("sin^2(x)", "sin(x)**2"),
    ("sinx", "sin(x)"),                  # trước đây thành s*i*n*x
    ("lnx + C", "log(x) + C"),
    ("sin 2x", "sin(2*x)"),
    ("sin x^2", "sin(x**2)"),
    ("arctan x", "atan(x)"),
    ("tg(x)", "tan(x)"),
    ("cotg x", "cot(x)"),
    ("căn x", "sqrt(x)"),                # viết bằng chữ
    ("2 căn bậc hai của x", "2*sqrt(x)"),
    ("x bình phương", "x**2"),
    ("e mũ x", "exp(x)"),
    ("1 phần 2 x^2", "x**2/2"),
    ("x^2/2 + hằng số C", "x**2/2 + C"),
    ("0,75", "3/4"),                     # dấu thập phân kiểu Việt Nam
])
def test_hieu_cach_viet_cua_sinh_vien(written, meant):
    assert expr_equal(parse_math(written), parse_math(meant))


@pytest.mark.parametrize("text", ["x mét", "căn của nhà", "θ₀ + 1"])
def test_chu_khong_hieu_thi_bao_chua_doc_duoc_chu_khong_cham(text):
    with pytest.raises(ParseError):
        parse_math(text)


def test_khong_dung_vao_ten_bien_co_so():
    assert str(parse_math("C1*exp(x) + C2")) == "C1*exp(x) + C2"
