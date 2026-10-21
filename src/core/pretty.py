"""Đổi biểu thức kiểu SymPy (``3*x**2 - 4*x``) sang ký hiệu đọc được (``3x² - 4x``).

Chỉ dùng ở chỗ gửi chữ RA cho người đọc. Bộ chấm, guardrail và cách sinh viên gõ
đáp án vẫn dùng cú pháp gốc — đổi ở đó là đổi cả ngữ nghĩa.
"""

from __future__ import annotations

import re

_SUP = str.maketrans("0123456789-n", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻ⁿ")


def _power(match: re.Match) -> str:
    exponent = match.group(1)
    return exponent.translate(_SUP) if re.fullmatch(r"-?\d+|n", exponent) else f"^{exponent}"


#: Đoạn LaTeX ``$...$`` / ``$$...$$`` (đã chuẩn hoá bởi src.rag.mathtext) để KaTeX
#: render — đụng vào là hỏng, ví dụ ``\exp(`` thành ``\e^(``.
_LATEX = re.compile(r"(\$\$.+?\$\$|\$[^$\n]+?\$)", re.DOTALL)


def pretty_math(text: str) -> str:
    parts = _LATEX.split(text)
    return "".join(part if index % 2 else _pretty(part) for index, part in enumerate(parts))


def _pretty(text: str) -> str:
    if "*" not in text and not re.search(r"\b(exp|log|sqrt)\(", text):
        return text
    text = re.sub(r"\bexp\(", "e^(", text)
    text = re.sub(r"\blog\(", "ln(", text)
    text = re.sub(r"\bsqrt\(", "√(", text)
    text = re.sub(r"\*\*(-?\d+|[A-Za-z])", _power, text)
    text = text.replace("**", "^")
    # 2*x -> 2x, 2*(x+1) -> 2(x+1); mọi phép nhân còn lại thành dấu chấm giữa.
    text = re.sub(r"(?<![\w.])(\d+)\*(?=[A-Za-zα-ω(√])", r"\1", text)
    return text.replace("*", "·")
