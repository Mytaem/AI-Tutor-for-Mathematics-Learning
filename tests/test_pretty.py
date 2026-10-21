import pytest

from src.core.pretty import pretty_math


@pytest.mark.parametrize(("raw", "shown"), [
    ("∫ (-2*x**2 - 6*x - 2) dx", "∫ (-2x² - 6x - 2) dx"),
    ("(4*x*exp(x**2))", "(4x·e^(x²))"),
    ("x*log(4*x + 2)/2 + C", "x·ln(4x + 2)/2 + C"),
    ("x**(n+1)/(n+1)", "x^(n+1)/(n+1)"),
    ("2*(x+1)*sin(x)", "2(x+1)·sin(x)"),
    ("0.5*x", "0.5·x"),
    ("sqrt(p*(1-p)/n)", "√(p·(1-p)/n)"),
    ("x**-2", "x⁻²"),
])
def test_converts_sympy_syntax(raw, shown):
    assert pretty_math(raw) == shown


def test_latex_segments_untouched():
    text = "Ta có $\\exp(x^{2}) * 2$ và $$\\sqrt(a)$$ còn 2*x thì đổi"
    assert pretty_math(text) == "Ta có $\\exp(x^{2}) * 2$ và $$\\sqrt(a)$$ còn 2x thì đổi"


def test_plain_vietnamese_untouched():
    text = "Chu trình Euler đi qua mỗi cạnh đúng một lần; log là logarit."
    assert pretty_math(text) == text
