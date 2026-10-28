"""Lời giải từng bước, tính bằng máy — không do mô hình ngôn ngữ viết.

Mỗi dạng bài có một hàm giải đọc tham số của đề (``item.meta``) và trả về các
bước. Con số trong từng bước do SymPy/NumPy tính, nên không có chỗ cho bịa.

Một bước có bốn phần, tách riêng vì gợi ý dùng chúng ở các mức khác nhau:

    action   làm gì ("Tính trung bình mẫu x̄")          — không có số, gợi ý mức thấp dùng được
    formula  công thức/định lý dùng ("x̄ = Σxᵢ / n")     — không có số
    work     thay số vào ("x̄ = (2 + 4 + 4) / 3")       — có số của đề
    result   kết quả của bước ("x̄ = 3,33")              — có thể là chính đáp án

``Solution.answer`` là đáp án ở dạng NỘP ĐƯỢC cho bộ chấm. ``solve`` chỉ trả lời
giải nếu bộ chấm xác nhận đáp án đó đúng — hàm giải nào có lỗi thì người học
không bao giờ thấy lời giải sai, chỉ thấy không có lời giải.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import sympy as sp

from src.core.pretty import pretty_math
from src.core.schema import Item


@dataclass
class Step:
    action: str
    formula: str = ""
    work: str = ""
    result: str = ""


@dataclass
class Solution:
    steps: list[Step]
    answer: str
    #: Kiến thức nền của cả bài: định nghĩa/định lý cần nhớ, một hai câu.
    theory: str = ""
    #: Công thức chính của dạng bài.
    formula: str = ""
    notes: list[str] = field(default_factory=list)


Solver = Callable[[Item], Solution | None]
SOLVERS: dict[str, Solver] = {}


def solver(*keys: str):
    """Đăng ký hàm giải cho một hay nhiều ``meta.task`` (hoặc mã template)."""
    def decorator(function: Solver) -> Solver:
        for key in keys:
            SOLVERS[key] = function
        return function
    return decorator


# --------------------------------------------------------------------------
# Định dạng số và biểu thức cho người đọc
# --------------------------------------------------------------------------

def show(value) -> str:
    """Biểu thức/số SymPy -> chữ đọc được (``3*x**2`` -> ``3x²``)."""
    if isinstance(value, float):
        return num(value)
    return pretty_math(sp.sstr(value))


def num(value: float, digits: int = 6) -> str:
    """Số thực gọn: bỏ đuôi 0, tối đa ``digits`` chữ số thập phân."""
    value = float(value)
    rounded = round(value, digits)
    if rounded == int(rounded):
        return str(int(rounded))
    return f"{rounded:.{digits}f}".rstrip("0").rstrip(".")


def vec(values) -> str:
    return "(" + ", ".join(show(v) for v in values) + ")"


def mat(rows) -> str:
    return "[" + ", ".join("[" + ", ".join(show(v) for v in row) + "]" for row in rows) + "]"


def sympy_matrix(rows) -> sp.Matrix:
    return sp.Matrix([[sp.nsimplify(sp.sympify(v)) for v in row] for row in rows])


def answer_list(values) -> str:
    """Đáp án dạng danh sách mà bộ chấm đọc được: ``[a, b]``."""
    return "[" + ", ".join(sp.sstr(v) for v in values) + "]"
