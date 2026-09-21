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

from src.core.itembank import ItemBank, load_error_codes
from src.core.schema import AnswerType, Item
from src.verify.equivalence import (
    ParseError,
    expr_equal,
    is_antiderivative_of,
    parse_math,
)

CONSTANT = sp.Symbol("C")


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
        correct_answer=str(item.answer),
        wrong_final_answer=str(item.answer),
        wrong_steps=wrong_steps,
        wrong_step_index=len(wrong_steps),
    )


# --------------------------------------------------------------------------
# Điều phối
# --------------------------------------------------------------------------

#: Mã lỗi mà đáp án sinh ra vẫn đúng về GIÁ TRỊ — không áp dụng kiểm tra bên dưới.
VALUE_PRESERVING = {"MAE.INT.NOCONST"}


def is_genuinely_wrong(item: Item, candidate: str) -> bool:
    """Đáp án sinh ra có thực sự sai không?

    Hàng rào bắt buộc ở tầng khung, không để từng injector tự lo. Lý do rất cụ
    thể: injector "lấy đạo hàm thay vì tích phân" gặp ∫e^(-x)dx sẽ sinh ra
    -e^(-x) — mà đó ĐÚNG là nguyên hàm. Hàm e^(λx) là hàm riêng của cả phép đạo
    hàm lẫn phép tích phân, và tại λ = -1 thì hai phép cho cùng kết quả.

    Một nhãn sai kiểu này độc hại hơn là thiếu dữ liệu: nó dạy bộ phân loại rằng
    đáp án đúng là sai.
    """
    try:
        if item.answer_type is AnswerType.ANTIDERIVATIVE and item.integrand:
            return not is_antiderivative_of(candidate, item.integrand, item.variable).equal
        if item.answer is not None:
            return not expr_equal(candidate, str(item.answer)).equal
    except (ParseError, TypeError):
        return False
    return True


def inject_all(item: Item, taxonomy: dict[str, object]) -> list[InjectedError]:
    """Sinh mọi lỗi áp dụng được cho một bài tập."""
    results: list[InjectedError] = []

    for code, injector in _REGISTRY.items():
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
            correct_answer=str(item.answer),
            wrong_final_answer=str(wrong),
            description_vi=entry.description_vi if entry is not None else "",
        ))

    step_error = inject_algebra_step_error(item)
    if step_error is not None:
        results.append(step_error)

    return results


def build_dataset(bank: ItemBank, taxonomy_path: str | Path | None = None) -> list[InjectedError]:
    """Sinh toàn bộ tập lỗi cho một ngân hàng đề."""
    codes = load_error_codes(taxonomy_path) if taxonomy_path else {}
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
