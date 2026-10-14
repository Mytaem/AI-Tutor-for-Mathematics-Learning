"""Sinh bài làm SAI có nhãn sạch, từ các bài đã có lời giải đúng.

Ý tưởng: thay vì đi xin hàng nghìn bài làm sai của sinh viên (tốn thời gian, nhãn
lại không chắc chắn), ta lấy lời giải đúng rồi cố tình làm hỏng nó theo đúng một
mã lỗi đã định nghĩa. Nhãn thu được chính xác tuyệt đối vì ta BIẾT mình đã phá
cái gì, ở đâu.

Hai công dụng:

1. **Dữ liệu huấn luyện** cho bộ phân loại lỗi (LoRA) — sinh được hàng nghìn mẫu.
2. **Bộ test cho chính verifier** — mọi lỗi sinh ra ở đây phải bị bắt. Đây là bộ
   test mạnh nhất viết được cho tầng kiểm chứng, vì nó phủ có hệ thống chứ không
   phụ thuộc vào việc ta nghĩ ra được ca nào.

Một điểm cần nói rõ trong báo cáo: tầng ký hiệu chỉ phân biệt được *bản chất*
sai lệch (lệch một hệ số hằng, ngược dấu, còn chứa biến), chứ không phân biệt
được *nguyên nhân sư phạm*. ``MAE.INT.POWER.NODIV`` và ``MAE.INT.SUBST.NOFACTOR``
đều biểu hiện ra ngoài là "lệch một hệ số" — chính khoảng trống này là lý do cần
tầng neural (bộ phân loại fine-tune) ở trên.

Dữ liệu sinh ra ở đây KHÔNG thay thế được bài làm sai của sinh viên thật: lỗi
tổng hợp dùng để train, lỗi thật dùng để test.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

import sympy as sp

from src.core.itembank import ItemBank, load_course_error_codes, load_error_codes
from src.core.schema import AnswerType, Item, Submission
from src.verify.equivalence import ParseError, expr_equal, parse_math

CONSTANT = sp.Symbol("C")


def var_of(item: Item) -> sp.Symbol:
    """Biến chính của đề.

    Đọc từ ``item.variable`` chứ không giả định luôn là ``x``: mọi đề hiện tại
    dùng x, nhưng một đề theo biến ``t`` thêm vào sau sẽ làm các bộ sinh lỗi
    dưới đây lặng lẽ sinh ra đáp án vô nghĩa thay vì báo lỗi.
    """
    return sp.Symbol(item.variable or "x")


@dataclass
class InjectedError:
    """Một bài làm sai được sinh ra, kèm nhãn chính xác."""

    item_id: str
    subject: str
    error_code: str
    tier: str
    statement_vi: str
    correct_answer: str
    wrong_final_answer: str | None = None
    wrong_steps: list[str] = field(default_factory=list)
    wrong_step_index: int | None = None
    description_vi: str = ""


Injector = Callable[[Item], sp.Expr | str | None]
_REGISTRY: dict[str, Injector] = {}


def register(code: str) -> Callable[[Injector], Injector]:
    """Đăng ký một hàm sinh lỗi cho một mã lỗi."""

    def decorator(function: Injector) -> Injector:
        _REGISTRY[code] = function
        return function

    return decorator


# --------------------------------------------------------------------------
# Tiện ích
# --------------------------------------------------------------------------

def antiderivative_of(item: Item) -> sp.Expr | None:
    """Nguyên hàm chuẩn của bài, đã bỏ hằng số C."""
    if item.answer_type is not AnswerType.ANTIDERIVATIVE or item.answer is None:
        return None
    try:
        return parse_math(str(item.answer)).subs(CONSTANT, 0)
    except ParseError:
        return None


def integrand_of(item: Item) -> sp.Expr | None:
    if not item.integrand:
        return None
    try:
        return parse_math(item.integrand)
    except ParseError:
        return None


def pure_power_exponent(integrand: sp.Expr, var: sp.Symbol) -> sp.Rational | None:
    """Nếu biểu thức có dạng ``x**n`` thì trả về n, ngược lại trả None."""
    if integrand == var:
        return sp.Integer(1)
    if isinstance(integrand, sp.Pow) and integrand.base == var and integrand.exp.is_Rational:
        return integrand.exp
    return None


def with_constant(expr: sp.Expr) -> str:
    return f"{expr} + C"


def limit_parts(item: Item) -> tuple[sp.Expr, object] | None:
    """``(biểu thức, điểm lấy giới hạn)`` của một bài giới hạn, hoặc None.

    Điểm có thể là chuỗi ``"oo"``; trả nguyên để nơi gọi tự quyết định, vì các
    lỗi ở x→∞ khác hẳn các lỗi ở điểm hữu hạn.
    """
    if item.meta.get("task") != "limit":
        return None
    try:
        return parse_math(str(item.meta["expr"])), item.meta.get("point")
    except (ParseError, KeyError):
        return None


def derivative_target(item: Item) -> sp.Expr | None:
    """Biểu thức f(x) của một bài đạo hàm, hoặc None nếu không phải bài đạo hàm."""
    if item.meta.get("task") != "derivative":
        return None
    try:
        return parse_math(str(item.meta["expr"]))
    except (ParseError, KeyError):
        return None


# --------------------------------------------------------------------------
# Các bộ sinh lỗi trên đáp án cuối
# --------------------------------------------------------------------------

@register("MAE.INT.NOCONST")
def _drop_constant(item: Item) -> str | None:
    """Đúng hết nhưng quên '+ C'."""
    reference = antiderivative_of(item)
    return str(reference) if reference is not None else None


@register("MAE.SIGN")
def _flip_sign(item: Item) -> str | None:
    reference = antiderivative_of(item)
    return with_constant(-reference) if reference is not None else None


@register("MAE.INT.CONSTFACTOR")
def _wrong_constant_factor(item: Item) -> str | None:
    """Lệch đúng một hệ số nhân — dùng hệ số 3 cho khác với các lỗi còn lại."""
    reference = antiderivative_of(item)
    return with_constant(3 * reference) if reference is not None else None


@register("MAE.INT.SUBST.NOFACTOR")
def _forget_substitution_factor(item: Item) -> str | None:
    """Đặt u = f(x) nhưng quên chia hệ số từ du.

    Biểu hiện: mất đúng phần mẫu số của hệ số hữu tỉ đứng trước. Ví dụ đáp án
    đúng ``(x²+1)⁴/8`` thành ``(x²+1)⁴`` — sinh viên bỏ qua hẳn việc x dx = du/2.
    """
    if "MAE.INT.SUBST" not in item.skills:
        return None
    reference = antiderivative_of(item)
    if reference is None:
        return None

    coefficient, rest = reference.as_coeff_Mul()
    if not coefficient.is_Rational or coefficient.q == 1:
        return None
    return with_constant(coefficient.p * rest)


@register("MAE.INT.POWER.NODIV")
def _power_rule_no_division(item: Item) -> str | None:
    """Tăng bậc nhưng quên chia cho bậc mới."""
    if item.answer_type is not AnswerType.ANTIDERIVATIVE:
        return None  # bài tích phân xác định phải trả về một số, không phải hàm
    integrand, var = integrand_of(item), sp.Symbol(item.variable)
    if integrand is None:
        return None
    exponent = pure_power_exponent(integrand, var)
    if exponent is None or exponent == -1:
        return None
    return with_constant(var ** (exponent + 1))


@register("MAE.INT.POWER.WRONGEXP")
def _power_rule_wrong_direction(item: Item) -> str | None:
    """Giảm bậc thay vì tăng bậc — nhầm tích phân với đạo hàm."""
    if item.answer_type is not AnswerType.ANTIDERIVATIVE:
        return None
    integrand, var = integrand_of(item), sp.Symbol(item.variable)
    if integrand is None:
        return None
    exponent = pure_power_exponent(integrand, var)
    if exponent is None or exponent - 1 == 0:
        return None
    return with_constant(var ** (exponent - 1) / (exponent - 1))


@register("MAE.INT.DERIV_INSTEAD")
def _differentiate_instead(item: Item) -> str | None:
    """Đọc nhầm đề, lấy đạo hàm."""
    integrand, var = integrand_of(item), sp.Symbol(item.variable)
    if integrand is None or item.answer_type is not AnswerType.ANTIDERIVATIVE:
        return None
    derivative = sp.diff(integrand, var)
    if derivative == 0 or derivative == integrand:
        return None
    return with_constant(derivative)


@register("MAE.INT.LINEARITY")
def _split_product(item: Item) -> str | None:
    """Tưởng ∫f·g = (∫f)(∫g)."""
    integrand, var = integrand_of(item), sp.Symbol(item.variable)
    reference = antiderivative_of(item)
    if integrand is None or reference is None:
        return None

    factors = integrand.as_ordered_factors()
    if len(factors) != 2:
        return None
    try:
        pieces = [sp.integrate(factor, var) for factor in factors]
    except (ValueError, NotImplementedError, sp.SympifyError):
        return None
    if any(piece.has(sp.Integral) for piece in pieces):
        return None

    wrong = pieces[0] * pieces[1]
    if expr_equal(wrong, reference).equal:
        return None  # trùng đáp án đúng thì không phải lỗi
    return with_constant(wrong)


@register("MAE.INT.DEF.NOEVAL")
def _forget_to_evaluate_bounds(item: Item) -> str | None:
    """Tích phân xác định nhưng dừng ở nguyên hàm, quên thế cận."""
    if item.answer_type is not AnswerType.NUMBER or not item.bounds:
        return None
    integrand, var = integrand_of(item), sp.Symbol(item.variable)
    if integrand is None:
        return None
    antiderivative = sp.integrate(integrand, var)
    if antiderivative.has(sp.Integral):
        return None
    return str(antiderivative)


@register("MAE.INT.DEF.SWAPBOUNDS")
def _swap_bounds(item: Item) -> str | None:
    """Thế cận ngược: F(a) − F(b) thay vì F(b) − F(a)."""
    if item.answer_type is not AnswerType.NUMBER or not item.bounds:
        return None
    try:
        value = parse_math(str(item.answer))
    except ParseError:
        return None
    if value == 0:
        return None  # đổi dấu số 0 thì không tạo ra lỗi nào
    return str(-value)


# --------------------------------------------------------------------------
# Bộ sinh lỗi trên chuỗi bước
# --------------------------------------------------------------------------

StepInjector = Callable[[Item], "InjectedError | None"]
_STEP_REGISTRY: list[StepInjector] = []


# --------------------------------------------------------------------------
# Lỗi của chương GIỚI HẠN
# --------------------------------------------------------------------------

@register("MAE.LIM.INDET_ZERO")
def _indeterminate_is_zero(item: Item) -> str | None:
    """Thấy 0/0 rồi kết luận giới hạn bằng 0.

    Chỉ áp dụng cho bài THẬT SỰ là dạng vô định — bài thay thẳng được thì lỗi
    này không có nghĩa, và sinh ra sẽ thành một nhãn vô nghĩa trong tập test.
    """
    if not item.meta.get("indeterminate"):
        return None
    return "0"


@register("MAE.LIM.INF_CONSTTERM")
def _infinity_wrong_ratio(item: Item) -> str | None:
    """x→∞ nhưng lấy tỉ số HẠNG TỰ DO thay vì hệ số bậc cao nhất."""
    parts = limit_parts(item)
    var = var_of(item)
    if parts is None or item.meta.get("indeterminate") != "oo/oo":
        return None
    expr, _ = parts
    numerator, denominator = sp.fraction(expr)
    try:
        top = sp.Poly(numerator, var).coeff_monomial(1)
        bottom = sp.Poly(denominator, var).coeff_monomial(1)
    except sp.PolynomialError:
        return None
    if not bottom:
        return None
    return str(sp.nsimplify(sp.Rational(int(top), int(bottom))))


@register("MAE.LIM.SIGN")
def _limit_flip_sign(item: Item) -> str | None:
    if item.meta.get("task") != "limit" or item.answer is None:
        return None
    try:
        value = parse_math(str(item.answer))
    except ParseError:
        return None
    return None if value == 0 else str(sp.nsimplify(-value))


# --------------------------------------------------------------------------
# Lỗi của chương ĐẠO HÀM
# --------------------------------------------------------------------------

@register("MAE.DER.POWER_NODEC")
def _power_forget_decrement(item: Item) -> str | None:
    """``(a·x**n)' = a·n·x**n`` — nhân số mũ ra nhưng quên giảm bậc."""
    expr = derivative_target(item)
    var = var_of(item)
    if expr is None or item.meta.get("point") is not None:
        return None
    wrong = sum(
        term.as_coeff_exponent(var)[0] * term.as_coeff_exponent(var)[1] * var
        ** term.as_coeff_exponent(var)[1]
        for term in sp.Add.make_args(sp.expand(expr))
    )
    return str(sp.simplify(wrong)) if wrong != 0 else None


@register("MAE.DER.POWER_NOMULT")
def _power_forget_multiply(item: Item) -> str | None:
    """``(a·x**n)' = a·x**(n-1)`` — giảm bậc nhưng quên nhân số mũ."""
    expr = derivative_target(item)
    var = var_of(item)
    if expr is None or item.meta.get("point") is not None:
        return None
    wrong = sum(
        coefficient * var ** (exponent - 1)
        for coefficient, exponent in (
            term.as_coeff_exponent(var) for term in sp.Add.make_args(sp.expand(expr))
        )
    )
    return str(sp.simplify(wrong)) if wrong != 0 else None


@register("MAE.DER.PRODUCT_SEPARATE")
def _product_rule_as_product(item: Item) -> str | None:
    """``(u·v)' = u'·v'`` — lỗi khái niệm phổ biến nhất của chương này."""
    expr = derivative_target(item)
    var = var_of(item)
    if expr is None or item.meta.get("rule") != "product":
        return None
    factors = sp.Mul.make_args(expr)
    if len(factors) < 2:
        return None
    wrong = sp.Mul(*[sp.diff(factor, var) for factor in factors])
    return str(sp.simplify(wrong)) if wrong != 0 else None


@register("MAE.DER.QUOTIENT_SIGN")
def _quotient_rule_wrong_sign(item: Item) -> str | None:
    """Tử là ``u'v + uv'`` thay vì ``u'v − uv'``."""
    expr = derivative_target(item)
    var = var_of(item)
    if expr is None or item.meta.get("rule") != "quotient":
        return None
    u, v = sp.fraction(expr)
    if v == 1:
        return None
    wrong = (sp.diff(u, var) * v + u * sp.diff(v, var)) / v**2
    return str(sp.simplify(wrong))


@register("MAE.DER.CHAIN_NOINNER")
def _chain_rule_forget_inner(item: Item) -> str | None:
    """``(sin(3x))' = cos(3x)`` — đúng hàm ngoài, quên nhân đạo hàm hàm trong."""
    expr = derivative_target(item)
    var = var_of(item)
    if expr is None or item.meta.get("rule") != "chain":
        return None

    if isinstance(expr, sp.Pow) and expr.exp.is_Integer:
        inner, exponent = expr.base, expr.exp
        wrong = exponent * inner ** (exponent - 1)
    elif isinstance(expr, sp.Function) and len(expr.args) == 1:
        inner = expr.args[0]
        wrong = sp.diff(expr.func(var), var).subs(var, inner)
    else:
        return None

    # Hàm trong có đạo hàm bằng 1 thì lỗi này KHÔNG làm đổi đáp án — bỏ, chứ
    # giữ lại thì tập test có một nhãn "sai" mà đáp án vẫn đúng.
    if sp.simplify(sp.diff(inner, var) - 1) == 0:
        return None
    return str(sp.simplify(wrong))


def register_step(function: StepInjector) -> StepInjector:
    """Đăng ký một bộ sinh lỗi trên CHUỖI BƯỚC. Mỗi bộ tự kiểm tra bài có hợp với nó không."""
    _STEP_REGISTRY.append(function)
    return function


@register_step
def inject_algebra_step_error(item: Item) -> InjectedError | None:
    """Chèn một bước biến đổi đại số sai vào giữa lời giải mẫu.

    Khác các bộ ở trên: lỗi nằm ở BƯỚC chứ không ở đáp án cuối, nên đáp án cuối
    vẫn đúng. Dùng để kiểm tra verifier có bắt được kiểu 'sai bù trừ' không.
    """
    steps = [step.expr for step in item.reference_solution_steps]
    if len(steps) < 2:
        return None

    try:
        corrupted = parse_math(steps[-1]) * 2
    except ParseError:
        return None

    wrong_steps = steps[:-1] + [str(corrupted)]
    return InjectedError(
        item_id=item.item_id,
        subject=item.subject.value,
        error_code="MAE.ALG.STEP",
        tier="E-COMPUTE",
        statement_vi=item.statement_vi,
        correct_answer=item.answer_text,
        wrong_final_answer=item.answer_text,
        wrong_steps=wrong_steps,
        wrong_step_index=len(wrong_steps),
    )


# --------------------------------------------------------------------------
# Điều phối
# --------------------------------------------------------------------------

#: Mã lỗi mà đáp án sinh ra vẫn đúng về GIÁ TRỊ — không áp dụng kiểm tra bên dưới.
VALUE_PRESERVING = {"MAE.INT.NOCONST"}


def is_genuinely_wrong(item: Item, candidate: str) -> bool:
    """Đáp án sinh ra có thực sự sai không? Hỏi thẳng verifier của môn.

    Hàng rào bắt buộc ở tầng khung, không để từng injector tự lo. Lý do rất cụ
    thể: injector "lấy đạo hàm thay vì tích phân" gặp ∫e^(-x)dx sẽ sinh ra
    -e^(-x) — mà đó ĐÚNG là nguyên hàm. Hàm e^(λx) là hàm riêng của cả phép đạo
    hàm lẫn phép tích phân, và tại λ = -1 thì hai phép cho cùng kết quả.

    Hỏi verifier thay vì tự so khớp: với MAI391, "sai" nghĩa là A·v ≠ λ·v, hoặc
    nghiệm không thoả phương trình — không có một đáp án chuẩn duy nhất nào để
    so. Đáp án không đọc được (verifier trả None) cũng bị loại: đó là rác, không
    phải một mẫu lỗi.

    Một nhãn sai kiểu này độc hại hơn là thiếu dữ liệu: nó dạy bộ phân loại rằng
    đáp án đúng là sai.
    """
    from src.verify.registry import verifier_for

    try:
        result = verifier_for(item.subject).verify(
            item, Submission(item_id=item.item_id, final_answer=candidate)
        )
    except Exception:
        return False
    return result.final_answer_correct is False


def inject_all(item: Item, taxonomy: dict[str, object]) -> list[InjectedError]:
    """Sinh mọi lỗi áp dụng được cho một bài tập.

    Chỉ dùng những mã lỗi có trong bảng mã lỗi của MÔN chứa bài — không lọc theo
    tiền tố, vì mã lỗi đặt theo kiểu sai: ``LA.*`` của đại số tuyến tính dùng
    chung cho cả MAE101 lẫn MAI391.
    """
    results: list[InjectedError] = []

    for code, injector in _REGISTRY.items():
        if taxonomy and code not in taxonomy:
            continue
        wrong = injector(item)
        if wrong is None:
            continue
        if code not in VALUE_PRESERVING and not is_genuinely_wrong(item, str(wrong)):
            continue

        entry = taxonomy.get(code)
        results.append(InjectedError(
            item_id=item.item_id,
            subject=item.subject.value,
            error_code=code,
            # .value chứ không phải enum: bản ghi này sẽ được ghi thẳng ra JSONL.
            tier=entry.tier.value if entry is not None else "E-COMPUTE",
            statement_vi=item.statement_vi,
            correct_answer=item.answer_text,
            wrong_final_answer=str(wrong),
            description_vi=entry.description_vi if entry is not None else "",
        ))

    for step_injector in _STEP_REGISTRY:
        step_error = step_injector(item)
        if step_error is not None and (not taxonomy or step_error.error_code in taxonomy):
            entry = taxonomy.get(step_error.error_code)
            if entry is not None:
                step_error.tier = entry.tier.value
                step_error.description_vi = entry.description_vi
            results.append(step_error)

    return results


def build_dataset(bank: ItemBank, taxonomy: str | Path | dict | None = None) -> list[InjectedError]:
    """Sinh toàn bộ tập lỗi cho một ngân hàng đề.

    ``taxonomy``: một file bảng mã lỗi, một dict đã nạp sẵn, hoặc để trống để
    dùng bảng mã lỗi đầy đủ của môn.
    """
    if isinstance(taxonomy, dict):
        codes = taxonomy
    elif taxonomy is not None:
        codes = load_error_codes(taxonomy)
    else:
        subject = next(iter(bank.items.values())).subject if bank.items else None
        codes = load_course_error_codes(subject) if subject else {}
    dataset: list[InjectedError] = []
    for item in bank.items.values():
        dataset.extend(inject_all(item, codes))
    return dataset


def write_dataset(dataset: list[InjectedError], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in dataset:
            handle.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")


# Bộ sinh lỗi của từng mảng kiến thức nằm ở module riêng và tự đăng ký vào
# registry ở trên khi được nhập. Nhập ở cuối file vì chúng cần ``register``.
from src.data_gen import discrete_errors, linear_algebra_errors, mml_errors, probstat_errors  # noqa: E402,F401
