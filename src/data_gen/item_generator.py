"""Sinh bài tập theo template có tham số, kèm lời giải chuẩn.

Mỗi template mô tả một *dạng* bài (ví dụ "tích phân hàm mũ tuyến tính"), rồi
random hoá hệ số để sinh ra vô số biến thể. Đáp án KHÔNG viết tay mà do SymPy
tính, nên không bao giờ sai.

Vì sao cần:

- 21 bài chép tay không đủ cho bất cứ thứ gì — không đủ train bộ phân loại lỗi,
  không đủ cho mô hình năng lực, không đủ để bộ chọn bài có cái mà chọn.
- Ghép với ``error_injector``, mỗi bài sinh ra lại đẻ thêm ~5 mẫu lỗi có nhãn.
  Vài trăm bài là có vài nghìn mẫu huấn luyện, miễn phí.

Nguyên tắc: mọi bài sinh ra đều được verifier tự chấm lại ngay tại chỗ. Bài nào
verifier không xác nhận được thì loại bỏ, không đưa vào ngân hàng. Nhờ vậy ngân
hàng đề luôn ở trạng thái đúng, kể cả khi thêm template mới.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable

import sympy as sp

from src.core.schema import AnswerType, Item, SolutionStep, Subject

X = sp.Symbol("x")

#: Template trả về (biểu thức dưới dấu tích phân, cận) — cận None nghĩa là nguyên hàm.
#: Có thể trả thêm phần tử thứ ba là nguyên hàm dạng đẹp, khi dạng SymPy tự tính
#: ra không phải dạng một sinh viên (hay giáo trình) sẽ viết.
Builder = Callable[[random.Random], tuple | None]


@dataclass
class Template:
    template_id: str
    skills: list[str]
    difficulty: float
    build: Builder
    method_vi: str = ""


_TEMPLATES: list[Template] = []


def template(template_id: str, skills: list[str], difficulty: float, method_vi: str = ""):
    def decorator(function: Builder) -> Builder:
        _TEMPLATES.append(Template(template_id, skills, difficulty, function, method_vi))
        return function

    return decorator


def nonzero(rng: random.Random, low: int, high: int) -> int:
    """Hệ số ngẫu nhiên khác 0 — hệ số 0 làm bài tập trở nên vô nghĩa."""
    value = 0
    while value == 0:
        value = rng.randint(low, high)
    return value


# --------------------------------------------------------------------------
# Nguyên hàm cơ bản
# --------------------------------------------------------------------------

@template("power", ["MAE.INT.BASIC"], 0.2, "Quy tắc luỹ thừa")
def _power(rng: random.Random):
    return nonzero(rng, -6, 6) * X ** rng.randint(2, 6), None


@template("polynomial", ["MAE.INT.BASIC"], 0.3, "Tính tuyến tính của tích phân")
def _polynomial(rng: random.Random):
    a, b, c = nonzero(rng, -5, 5), nonzero(rng, -6, 6), rng.randint(-8, 8)
    return a * X**2 + b * X + c, None


@template("root", ["MAE.INT.BASIC"], 0.4, "Quy tắc luỹ thừa với số mũ hữu tỉ")
def _root(rng: random.Random):
    exponent = rng.choice([
        sp.Rational(1, 2), sp.Rational(3, 2), sp.Rational(5, 2),
        sp.Rational(1, 3), sp.Rational(2, 3), sp.Rational(1, 4),
    ])
    return nonzero(rng, 1, 8) * X**exponent, None


@template("negative_power", ["MAE.INT.BASIC"], 0.35, "Quy tắc luỹ thừa với số mũ âm")
def _negative_power(rng: random.Random):
    return nonzero(rng, 1, 6) / X ** rng.randint(2, 4), None


# --------------------------------------------------------------------------
# Mũ, logarit, lượng giác
# --------------------------------------------------------------------------

@template("exp_linear", ["MAE.INT.EXPLOG", "MAE.INT.SUBST"], 0.45, "Đổi biến tuyến tính u = ax + b")
def _exp_linear(rng: random.Random):
    return nonzero(rng, 1, 4) * sp.exp(nonzero(rng, -4, 4) * X), None


@template("trig_linear", ["MAE.INT.TRIG", "MAE.INT.SUBST"], 0.45, "Đổi biến tuyến tính u = ax + b")
def _trig_linear(rng: random.Random):
    function = rng.choice([sp.sin, sp.cos])
    return nonzero(rng, 1, 4) * function(nonzero(rng, 1, 4) * X + rng.randint(-3, 3)), None


@template("reciprocal_linear", ["MAE.INT.EXPLOG", "MAE.INT.SUBST"], 0.5, "Nguyên hàm dạng 1/(ax+b)")
def _reciprocal_linear(rng: random.Random):
    return nonzero(rng, 1, 5) / (nonzero(rng, 1, 4) * X + rng.randint(1, 6)), None


@template("sec_squared", ["MAE.INT.TRIG"], 0.45, "Nguyên hàm của 1/cos²")
def _sec_squared(rng: random.Random):
    a, b, c = nonzero(rng, 1, 3), rng.randint(-2, 2), nonzero(rng, 1, 4)
    inner = a * X + b
    # Tự cho nguyên hàm thay vì để SymPy tính: SymPy trả về dạng góc chia đôi
    # -c·tan(u/2)/(tan²(u/2) - 1), đúng về toán nhưng không ai viết như vậy —
    # và đó lại chính là thứ hiện cho sinh viên ở gợi ý mức 5.
    return c / sp.cos(inner) ** 2, None, sp.Rational(c, a) * sp.tan(inner)


# --------------------------------------------------------------------------
# Đổi biến
# --------------------------------------------------------------------------

@template("subst_power", ["MAE.INT.SUBST"], 0.6, "Đổi biến u = ax² + b")
def _subst_power(rng: random.Random):
    a, b, n = nonzero(rng, 1, 4), rng.randint(1, 5), rng.randint(2, 4)
    return X * (a * X**2 + b) ** n, None


@template("subst_exp", ["MAE.INT.SUBST", "MAE.INT.EXPLOG"], 0.6, "Đổi biến u = ax²")
def _subst_exp(rng: random.Random):
    return nonzero(rng, 1, 5) * X * sp.exp(nonzero(rng, -4, 4) * X**2), None


@template("subst_log", ["MAE.INT.SUBST", "MAE.INT.EXPLOG"], 0.65, "Đổi biến u = mẫu số")
def _subst_log(rng: random.Random):
    a, b, c = nonzero(rng, 1, 3), rng.randint(-4, 4), rng.randint(3, 9)
    denominator = a * X**2 + b * X + c
    if sp.discriminant(denominator, X) >= 0:
        return None  # tránh mẫu số có nghiệm thực -> log của số âm trên miền mẫu
    return sp.diff(denominator, X) / denominator, None


# --------------------------------------------------------------------------
# Từng phần
# --------------------------------------------------------------------------

@template("parts_exp", ["MAE.INT.PARTS"], 0.65, "Từng phần với u = x, dv = e^(ax)dx")
def _parts_exp(rng: random.Random):
    return nonzero(rng, 1, 6) * X * sp.exp(nonzero(rng, -4, 4) * X), None


@template("parts_trig", ["MAE.INT.PARTS", "MAE.INT.TRIG"], 0.7, "Từng phần với u = x")
def _parts_trig(rng: random.Random):
    function = rng.choice([sp.sin, sp.cos])
    return nonzero(rng, 1, 5) * X * function(nonzero(rng, -3, 3) * X), None


@template("parts_log", ["MAE.INT.PARTS", "MAE.INT.EXPLOG"], 0.7, "Từng phần với u = ln x")
def _parts_log(rng: random.Random):
    return nonzero(rng, 1, 8) * X ** rng.randint(1, 3) * sp.log(X), None


# --------------------------------------------------------------------------
# Phân thức hữu tỉ
# --------------------------------------------------------------------------

@template("partial_fractions", ["MAE.INT.RATIONAL"], 0.75, "Phân tích thành phân thức đơn giản")
def _partial_fractions(rng: random.Random):
    a, b = rng.randint(1, 7), rng.randint(1, 7)
    if a == b:
        return None  # nghiệm kép cần phương pháp khác, không thuộc dạng này
    return nonzero(rng, 1, 5) / ((X + a) * (X + b)), None


# --------------------------------------------------------------------------
# Tích phân xác định
# --------------------------------------------------------------------------

@template("definite_power", ["MAE.INT.DEF", "MAE.INT.BASIC"], 0.45, "Newton–Leibniz")
def _definite_power(rng: random.Random):
    lower = rng.randint(0, 2)
    return (
        nonzero(rng, 1, 5) * X ** rng.randint(1, 4),
        (sp.Integer(lower), sp.Integer(lower + rng.randint(1, 4))),
    )


@template("definite_exp", ["MAE.INT.DEF", "MAE.INT.EXPLOG"], 0.55, "Newton–Leibniz với hàm mũ")
def _definite_exp(rng: random.Random):
    return (
        nonzero(rng, 1, 4) * sp.exp(nonzero(rng, -3, 3) * X),
        (sp.Integer(0), sp.Integer(rng.randint(1, 3))),
    )


@template("definite_subst", ["MAE.INT.DEF.SUBST"], 0.75, "Đổi biến trong tích phân xác định")
def _definite_subst(rng: random.Random):
    return (
        nonzero(rng, 1, 4) * X * sp.exp(nonzero(rng, -3, 3) * X**2),
        (sp.Integer(0), sp.Integer(rng.randint(1, 3))),
    )


# --------------------------------------------------------------------------
# Sinh bài
# --------------------------------------------------------------------------

def _build_item(
    spec: Template, integrand: sp.Expr, bounds, index: int, known: sp.Expr | None = None
) -> Item | None:
    """Dựng một Item hoàn chỉnh; trả None nếu SymPy không giải được."""
    if bounds is None:
        antiderivative = known if known is not None else sp.integrate(integrand, X)
        if antiderivative is None or antiderivative.has(sp.Integral) or antiderivative == 0:
            return None
        answer_type = AnswerType.ANTIDERIVATIVE
        answer = f"{antiderivative} + C"
        statement = f"Tính nguyên hàm: ∫ ({sp.sstr(integrand)}) dx"
        latex = rf"\int \left({sp.latex(integrand)}\right)\,dx"
        steps = [
            SolutionStep(step=1, expr=f"Integral({sp.sstr(integrand)}, x)",
                         skill_id=spec.skills[0], explain_vi=spec.method_vi),
            SolutionStep(step=2, expr=sp.sstr(antiderivative),
                         skill_id=spec.skills[0], explain_vi="Kết quả, nhớ cộng hằng số C"),
        ]
    else:
        lower, upper = bounds
        value = sp.integrate(integrand, (X, lower, upper))
        if value is None or value.has(sp.Integral) or value == 0 or value.free_symbols:
            return None
        answer_type = AnswerType.NUMBER
        answer = sp.sstr(sp.nsimplify(value))
        statement = (
            f"Tính tích phân xác định: ∫ từ {sp.sstr(lower)} đến {sp.sstr(upper)} "
            f"của ({sp.sstr(integrand)}) dx"
        )
        latex = rf"\int_{{{sp.latex(lower)}}}^{{{sp.latex(upper)}}} \left({sp.latex(integrand)}\right)\,dx"
        steps = []

    return Item(
        item_id=f"MAE101-GEN-{spec.template_id}-{index:04d}",
        subject=Subject.MAE101,
        skills=list(spec.skills),
        statement_vi=statement,
        statement_latex=latex,
        answer_type=answer_type,
        answer=answer,
        integrand=sp.sstr(integrand),
        variable="x",
        bounds=(sp.sstr(bounds[0]), sp.sstr(bounds[1])) if bounds else None,
        reference_solution_steps=steps,
        difficulty=spec.difficulty,
        source="generated",
        meta={"template": spec.template_id, "method": spec.method_vi},
    )


def generate(count: int, seed: int = 20260921, validate: bool = True) -> list[Item]:
    """Sinh ``count`` bài tập khác nhau, phân bổ đều qua các template.

    ``validate=True`` bắt mỗi bài phải tự verify được trước khi nhận — đây là
    hàng rào giữ cho ngân hàng đề luôn đúng khi thêm template mới.
    """
    from src.core.schema import Submission
    from src.verify.calculus import CalculusVerifier

    rng = random.Random(seed)
    verifier = CalculusVerifier() if validate else None

    items: list[Item] = []
    seen: set[str] = set()
    attempts = 0
    max_attempts = count * 40

    while len(items) < count and attempts < max_attempts:
        attempts += 1
        spec = _TEMPLATES[attempts % len(_TEMPLATES)]

        built = spec.build(rng)
        if built is None:
            continue
        integrand, bounds, *extra = built
        known = extra[0] if extra else None

        fingerprint = f"{spec.template_id}|{sp.sstr(integrand)}|{bounds}"
        if fingerprint in seen:
            continue

        try:
            item = _build_item(spec, integrand, bounds, len(items) + 1, known)
        except (ValueError, NotImplementedError, sp.SympifyError, TypeError):
            continue
        if item is None:
            continue

        if verifier is not None:
            result = verifier.verify(
                item, Submission(item_id=item.item_id, final_answer=str(item.answer))
            )
            if result.final_answer_correct is not True:
                continue  # SymPy tính được nhưng verifier không xác nhận -> loại

        seen.add(fingerprint)
        items.append(item)

    return items


def template_ids() -> list[str]:
    return [spec.template_id for spec in _TEMPLATES]
