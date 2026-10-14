"""Sinh đề MAE101 cho hai chương GIỚI HẠN và ĐẠO HÀM.

Vì sao có file này: cây nội dung (`src/core/syllabus.py`) phơi ra rằng hai chương
ĐẦU TIÊN của MAE101 có **0 đề** — 5 kỹ năng không có bài nào, nên sinh viên chọn
chương "Giới hạn và liên tục" thì không luyện được gì. Phần đại số tuyến tính và
tích phân đã có bộ sinh riêng; hai chương này bị bỏ sót.

Nguyên tắc đặt tham số, và đây là phần quyết định đề có dạy được hay không:

* **Giới hạn phải ra số đẹp.** Gieo đa thức bừa rồi lấy giới hạn tại một điểm
  thì hầu hết ra phân số lạ, đề thành bài bấm máy. Ở đây mọi dạng vô định được
  dựng NGƯỢC từ nghiệm đã chọn: ``(x−a)(x−b) / (x−a)`` luôn rút gọn được.
* **Đạo hàm phải cần đúng quy tắc đang dạy.** Bài cho kỹ năng "quy tắc hàm hợp"
  phải thực sự không giải được bằng công thức lũy thừa đơn thuần, nếu không thì
  mô hình năng lực ghi nhận một kỹ năng mà sinh viên chưa hề dùng tới.

Mọi đề sinh ra đều bị chính verifier MAE101 chấm lại trước khi được nhận — đó là
hàng rào duy nhất, và nó đủ (xem `Registry.generate`).
"""

from __future__ import annotations

import random

import sympy as sp

from src.core.schema import Subject
from src.data_gen.bank_builder import Registry

MAE101_CALC = Registry(Subject.MAE101, "MAE101")
template = MAE101_CALC.template

X = sp.Symbol("x")


def text(value) -> str:
    return sp.sstr(value)


def draft(meta: dict, statement_vi: str, answer, answer_type: str, **extra) -> dict:
    return {"meta": meta, "statement_vi": statement_vi, "answer": answer,
            "answer_type": answer_type, **extra}


def pretty(expr) -> str:
    """Biểu thức viết cho người đọc: ``x**2`` thành ``x²``.

    Chỉ đổi ở phần ĐỀ BÀI. Đáp án giữ nguyên cú pháp SymPy vì nó còn phải nộp
    lại được vào verifier, và vì ô nhập của sinh viên cũng dùng cú pháp đó.
    """
    out = sp.sstr(expr)
    for old, new in (("**2", "²"), ("**3", "³"), ("**4", "⁴"), ("*", "·")):
        out = out.replace(old, new)
    return out


# ==========================================================================
# Giới hạn
# ==========================================================================

@template("limit_polynomial", ["MAE.LIM.BASIC"], 0.15, "Thay trực tiếp vào đa thức")
def _limit_polynomial(rng: random.Random):
    a, b, c = (rng.randint(-4, 4) for _ in range(3))
    point = rng.randint(-3, 3)
    expr = a * X**2 + b * X + c
    if a == 0 and b == 0:
        return None
    meta = {"task": "limit", "point": point, "expr": text(expr)}
    return draft(
        meta,
        f"Tính giới hạn: lim(x→{point}) ({pretty(expr)})",
        text(expr.subs(X, point)),
        "number",
    )


@template("limit_rational", ["MAE.LIM.BASIC"], 0.3, "Thay trực tiếp vào phân thức")
def _limit_rational(rng: random.Random):
    """Mẫu KHÔNG triệt tiêu tại điểm lấy giới hạn — đây là ca thay thẳng được."""
    point = rng.randint(-3, 3)
    numerator = X + rng.randint(-4, 4)
    shift = rng.choice([1, 2, 3, -1, -2, -3])
    denominator = X - (point + shift)       # mẫu khác 0 tại x = point
    meta = {"task": "limit", "point": point, "expr": text(numerator / denominator)}
    value = sp.nsimplify((numerator / denominator).subs(X, point))
    return draft(
        meta,
        f"Tính giới hạn: lim(x→{point}) ({pretty(numerator)}) / ({pretty(denominator)})",
        text(value),
        "number",
    )


@template("limit_factor", ["MAE.LIM.INDET"], 0.45, "Khử 0/0 bằng phân tích nhân tử")
def _limit_factor(rng: random.Random):
    """Dạng 0/0 dựng ngược từ nghiệm: ``(x−a)(x−b) / (x−a)``.

    Dựng ngược chứ không gieo bừa, vì gieo bừa thì mẫu hiếm khi triệt tiêu và
    đề mất hẳn tính chất "dạng vô định" mà kỹ năng này nhắm tới.
    """
    a = rng.randint(-3, 3)
    b = rng.randint(-4, 4)
    if a == b:
        return None
    numerator = sp.expand((X - a) * (X - b))
    meta = {"task": "limit", "point": a, "expr": text(numerator / (X - a)), "indeterminate": "0/0"}
    return draft(
        meta,
        f"Tính giới hạn: lim(x→{a}) ({pretty(numerator)}) / ({pretty(X - a)})",
        text(a - b),
        "number",
        reference_solution_steps=[
            {"step": 1, "expr": f"({pretty(numerator)})/({pretty(X - a)})",
             "explain_vi": f"Thay x = {a} cho dạng 0/0, chưa kết luận được"},
            {"step": 2, "expr": f"(x - {a})(x - {b})/(x - {a})",
             "explain_vi": "Phân tích tử thành nhân tử"},
            {"step": 3, "expr": f"x - {b}", "explain_vi": f"Rút gọn nhân tử (x - {a})"},
            {"step": 4, "expr": text(a - b), "explain_vi": f"Thay x = {a} vào biểu thức đã rút gọn"},
        ],
    )


@template("limit_conjugate", ["MAE.LIM.INDET"], 0.6, "Khử 0/0 bằng nhân liên hợp")
def _limit_conjugate(rng: random.Random):
    """``(√(x+k) − √k) / x`` khi x→0, đáp án ``1/(2√k)``. Chọn k chính phương."""
    k = rng.choice([1, 4, 9, 16, 25])
    expr = (sp.sqrt(X + k) - sp.sqrt(k)) / X
    meta = {"task": "limit", "point": 0, "expr": text(expr), "indeterminate": "0/0"}
    return draft(
        meta,
        f"Tính giới hạn: lim(x→0) (√(x+{k}) − {sp.sqrt(k)}) / x",
        text(sp.nsimplify(sp.Rational(1, 2) / sp.sqrt(k))),
        "number",
    )


@template("limit_infinity", ["MAE.LIM.INDET"], 0.5, "Khử ∞/∞ bằng chia bậc cao nhất")
def _limit_infinity(rng: random.Random):
    """Hai đa thức CÙNG BẬC → giới hạn là tỉ số hệ số đầu, luôn là số hữu tỉ."""
    degree = rng.choice([1, 2, 2, 3])
    lead_top = rng.choice([1, 2, 3, 4, 6])
    lead_bottom = rng.choice([1, 2, 3, 4])
    numerator = lead_top * X**degree + rng.randint(-5, 5) * X + rng.randint(-5, 5)
    denominator = lead_bottom * X**degree + rng.randint(-5, 5)
    meta = {"task": "limit", "point": "oo", "expr": text(numerator / denominator),
            "indeterminate": "oo/oo"}
    return draft(
        meta,
        f"Tính giới hạn: lim(x→∞) ({pretty(numerator)}) / ({pretty(denominator)})",
        text(sp.nsimplify(sp.Rational(lead_top, lead_bottom))),
        "number",
    )


# ==========================================================================
# Đạo hàm
# ==========================================================================

@template("derivative_power", ["MAE.DER.BASIC"], 0.2, "Công thức lũy thừa")
def _derivative_power(rng: random.Random):
    a = rng.randint(1, 6)
    n = rng.randint(2, 5)
    b = rng.randint(-6, 6)
    expr = a * X**n + b * X
    meta = {"task": "derivative", "expr": text(expr)}
    return draft(
        meta,
        f"Tính đạo hàm của f(x) = {pretty(expr)}",
        text(sp.diff(expr, X)),
        "expression",
        variable="x",
    )


@template("derivative_elementary", ["MAE.DER.BASIC"], 0.3, "Đạo hàm hàm sơ cấp")
def _derivative_elementary(rng: random.Random):
    base = rng.choice([sp.sin(X), sp.cos(X), sp.exp(X), sp.log(X), sp.sqrt(X)])
    a = rng.randint(2, 5)
    expr = a * base
    meta = {"task": "derivative", "expr": text(expr)}
    return draft(
        meta,
        f"Tính đạo hàm của f(x) = {pretty(expr)}",
        text(sp.diff(expr, X)),
        "expression",
        variable="x",
    )


@template("derivative_product", ["MAE.DER.PRODUCT"], 0.45, "Quy tắc đạo hàm tích")
def _derivative_product(rng: random.Random):
    """Hai thừa số đều PHỤ THUỘC x, nên không tách được thành hằng số nhân hàm.

    Nếu một thừa số là hằng thì bài giải được bằng công thức lũy thừa và kỹ
    năng "quy tắc tích" không hề được dùng — mô hình năng lực sẽ ghi nhận sai.
    """
    n = rng.randint(1, 3)
    other = rng.choice([sp.sin(X), sp.cos(X), sp.exp(X), sp.log(X)])
    expr = X**n * other
    meta = {"task": "derivative", "expr": text(expr), "rule": "product"}
    return draft(
        meta,
        f"Tính đạo hàm của f(x) = {pretty(expr)}",
        text(sp.diff(expr, X)),
        "expression",
        variable="x",
    )


@template("derivative_quotient", ["MAE.DER.PRODUCT"], 0.55, "Quy tắc đạo hàm thương")
def _derivative_quotient(rng: random.Random):
    a, b, c, d = (rng.randint(1, 5) for _ in range(4))
    numerator = a * X + b
    denominator = c * X + d
    if a * d - b * c == 0:
        return None                       # thương là hằng số, đạo hàm bằng 0
    expr = numerator / denominator
    meta = {"task": "derivative", "expr": text(expr), "rule": "quotient"}
    return draft(
        meta,
        f"Tính đạo hàm của f(x) = ({pretty(numerator)}) / ({pretty(denominator)})",
        text(sp.simplify(sp.diff(expr, X))),
        "expression",
        variable="x",
    )


@template("derivative_chain", ["MAE.DER.CHAIN"], 0.5, "Quy tắc hàm hợp")
def _derivative_chain(rng: random.Random):
    """Hàm ngoài hợp với hàm trong BẬC ≥ 1, để quy tắc hàm hợp là bắt buộc."""
    inner = rng.choice([
        rng.randint(2, 5) * X + rng.randint(-4, 4),
        X**2 + rng.randint(1, 5),
        rng.randint(2, 4) * X**2 + X,
    ])
    outer = rng.choice(["sin", "cos", "exp", "power"])
    if outer == "power":
        expr = inner ** rng.randint(2, 4)
    else:
        expr = {"sin": sp.sin, "cos": sp.cos, "exp": sp.exp}[outer](inner)
    meta = {"task": "derivative", "expr": text(expr), "rule": "chain"}
    return draft(
        meta,
        f"Tính đạo hàm của f(x) = {pretty(expr)}",
        text(sp.diff(expr, X)),
        "expression",
        variable="x",
    )


@template("derivative_at_point", ["MAE.DER.BASIC"], 0.35, "Đạo hàm tại một điểm")
def _derivative_at_point(rng: random.Random):
    a = rng.randint(1, 4)
    n = rng.randint(2, 4)
    b = rng.randint(-5, 5)
    point = rng.randint(-3, 3)
    expr = a * X**n + b * X
    meta = {"task": "derivative", "expr": text(expr), "point": point}
    return draft(
        meta,
        f"Cho f(x) = {pretty(expr)}. Tính f'({point})",
        text(sp.diff(expr, X).subs(X, point)),
        "number",
    )


# ==========================================================================

def generate(count: int, seed: int = 20261014, validate: bool = True):
    return MAE101_CALC.generate(count, seed=seed, validate=validate)


def template_ids() -> list[str]:
    return MAE101_CALC.template_ids()
