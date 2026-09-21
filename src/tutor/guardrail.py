"""Chặn gợi ý làm lộ đáp án.

Một gia sư nói "em thử xét u = x²+1 xem" là đang dạy. Nói "đáp án là (x²+1)⁴/8"
là đang làm hộ. Ranh giới đó phải được kiểm tra bằng máy, vì:

- LLM rất hay "giúp quá tay", nhất là model nhỏ và khi prompt dài.
- Đây là một chỉ số ĐO ĐƯỢC (EXP-8), không phải cảm tính: đếm tỉ lệ gợi ý bị
  chặn, so giữa có và không có guardrail.

Cách làm: trích mọi biểu thức toán xuất hiện trong câu gợi ý, rồi hỏi tầng kiểm
chứng xem biểu thức đó có tương đương đáp án cuối không. Nếu có mà mức gợi ý
chưa được phép tiết lộ thì từ chối câu đó.

Thiên lệch có chủ ý: thà trích thừa còn hơn trích thiếu. Trích thừa thì cùng lắm
phải sinh lại câu gợi ý; trích thiếu là để lọt đáp án ra ngoài.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import sympy as sp

from src.core.schema import AnswerType, Item
from src.tutor.hint_policy import HintLevel
from src.verify.equivalence import (
    ParseError,
    expr_equal,
    is_antiderivative_of,
    parse_math,
)

CONSTANT = sp.Symbol("C")

#: Từ mức này trở lên, gợi ý ĐƯỢC PHÉP nói ra đáp án.
DEFAULT_REVEAL_FROM = HintLevel.CORRECT

_DELIMITED_PATTERNS = (
    r"\$(.+?)\$",        # $...$
    r"\\\((.+?)\\\)",    # \(...\)
    r"`(.+?)`",          # `...`
)

#: Ký tự có thể xuất hiện trong biểu thức toán viết bằng ASCII.
_MATH_SPAN = re.compile(r"[0-9A-Za-z_^*/+\-().\s]{3,}")
_MATH_TOKEN = re.compile(r"[0-9A-Za-z_^*/+\-().]{2,}")
_HAS_OPERATOR = re.compile(r"[+\-*/^]")
_HAS_DIGIT_LETTER_MIX = re.compile(r"(\d[A-Za-z(]|[A-Za-z)]\d)")


@dataclass
class LeakReport:
    """Kết quả kiểm tra một câu gợi ý."""

    leaked: bool
    level: HintLevel
    offending_expression: str | None = None
    reason: str = ""

    def __bool__(self) -> bool:
        return self.leaked


def looks_like_math(text: str) -> bool:
    """Lọc thô: chuỗi này có vẻ là biểu thức toán không?

    Loại bỏ các từ thuần chữ ("em thu lai", "buoc nay") để không phí công parse.
    """
    stripped = text.strip()
    if len(stripped) < 2:
        return False
    if stripped.isalpha() and len(stripped) > 1:
        return False
    return bool(_HAS_OPERATOR.search(stripped) or _HAS_DIGIT_LETTER_MIX.search(stripped))


#: Số token tối đa trong một đoạn trước khi ngừng thử mọi tổ hợp con.
_MAX_TOKENS_PER_SPAN = 14


def _span_candidates(span: str):
    """Mọi đoạn con liên tiếp (theo token) của một vùng ký tự toán học.

    Cần thiết vì phần ASCII của chữ tiếng Việt hay dính vào biểu thức: câu
    "Kết quả bằng (x**2+1)**4 / 8" cho ra vùng "ng (x**2+1)**4 / 8", và nếu
    parse nguyên vùng đó thì "ng" biến thành hai biến nhân vào, làm biểu thức
    không còn khớp đáp án — tức là để lọt một ca rò rỉ thật.
    """
    tokens = span.split()
    if not tokens or len(tokens) > _MAX_TOKENS_PER_SPAN:
        # Đoạn quá dài thì chỉ thử các hậu tố, tránh bùng nổ tổ hợp.
        for start in range(len(tokens)):
            candidate = " ".join(tokens[start:])
            if looks_like_math(candidate):
                yield candidate
        return

    for start in range(len(tokens)):
        for end in range(start + 1, len(tokens) + 1):
            candidate = " ".join(tokens[start:end])
            if looks_like_math(candidate):
                yield candidate


def extract_expressions(text: str) -> list[sp.Expr]:
    """Trích mọi biểu thức toán parse được trong một đoạn văn bản."""
    candidates: list[str] = []

    for pattern in _DELIMITED_PATTERNS:
        candidates.extend(re.findall(pattern, text, flags=re.DOTALL))

    for span in _MATH_SPAN.findall(text):
        candidates.extend(_span_candidates(span.strip()))
        for token in _MATH_TOKEN.findall(span):
            if looks_like_math(token):
                candidates.append(token)

    expressions: list[sp.Expr] = []
    seen: set[str] = set()
    for candidate in candidates:
        try:
            expression = parse_math(candidate)
        except (ParseError, RecursionError):
            continue
        key = sp.srepr(expression)
        if key in seen:
            continue
        seen.add(key)
        expressions.append(expression)
    return expressions


def _answer_expression(item: Item) -> sp.Expr | None:
    if item.answer is None:
        return None
    try:
        return parse_math(str(item.answer)).subs(CONSTANT, 0)
    except ParseError:
        return None


def _is_restatement_of_problem(expression: sp.Expr, item: Item) -> bool:
    """Nhắc lại chính đề bài thì không phải là lộ đáp án."""
    if not item.integrand:
        return False
    try:
        return expr_equal(expression, parse_math(item.integrand)).equal
    except ParseError:
        return False


def reveals_answer(expression: sp.Expr, item: Item) -> bool:
    """Biểu thức này có chính là đáp án không?"""
    if _is_restatement_of_problem(expression, item):
        return False

    reference = _answer_expression(item)
    if reference is not None and expr_equal(expression, reference).equal:
        return True

    # Với bài nguyên hàm, mọi biểu thức có đạo hàm khớp biểu thức dưới dấu tích
    # phân đều là đáp án, dù viết ở dạng nào. Phải kiểm bằng đạo hàm chứ không
    # so khớp với một dạng chuẩn duy nhất.
    if item.answer_type is AnswerType.ANTIDERIVATIVE and item.integrand:
        if expression.free_symbols and is_antiderivative_of(
            expression, item.integrand, item.variable
        ).equal:
            return True
    return False


def check_leak(
    hint_text: str,
    item: Item,
    level: HintLevel,
    *,
    reveal_from: HintLevel = DEFAULT_REVEAL_FROM,
) -> LeakReport:
    """Câu gợi ý này có làm lộ đáp án sớm không?"""
    if level >= reveal_from:
        return LeakReport(False, level, reason=f"Mức {int(level)} được phép tiết lộ")

    for expression in extract_expressions(hint_text):
        if reveals_answer(expression, item):
            return LeakReport(
                leaked=True,
                level=level,
                offending_expression=str(expression),
                reason=f"Biểu thức {expression} chính là đáp án, không được nói ở mức {int(level)}",
            )

    return LeakReport(False, level, reason="Không phát hiện đáp án trong câu gợi ý")


def leak_rate(reports: list[LeakReport]) -> float:
    """Tỉ lệ gợi ý bị rò đáp án — số liệu cho EXP-8."""
    if not reports:
        return 0.0
    return sum(1 for report in reports if report.leaked) / len(reports)
