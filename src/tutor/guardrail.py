"""Chặn gợi ý làm lộ đáp án.

Một gia sư nói "em thử xét u = x²+1 xem" là đang dạy. Nói "đáp án là (x²+1)⁴/8"
là đang làm hộ. Ranh giới đó phải được kiểm tra bằng máy, vì:

- LLM rất hay "giúp quá tay", nhất là model nhỏ và khi prompt dài.
- Đây là một chỉ số ĐO ĐƯỢC (EXP-8), không phải cảm tính: đếm tỉ lệ gợi ý bị
  chặn, so giữa có và không có guardrail.

Tiêu chí: **một câu gợi ý làm lộ đáp án khi có một mảnh trong nó mà, nếu nộp
làm đáp án, verifier sẽ chấm đúng.** Guardrail không tự phán xét "thế nào là
đáp án" — nó hỏi thẳng verifier của môn. Nhờ vậy:

- Mọi dạng tương đương của đáp án đều bị chặn, vì verifier vốn đã chấp nhận
  mọi dạng tương đương (nguyên hàm viết khác, vector riêng nhân bội khác,
  nghiệm ODE đặt tên hằng số khác...).
- Thêm môn mới là được bảo vệ ngay, không phải viết thêm luật cho guardrail.

Bản trước tự so khớp với đáp án chuẩn, và để lọt đúng loại đáp án mà MAI391
toàn gặp: ma trận, vector, nghiệm tham số.

Thiên lệch có chủ ý: thà trích thừa còn hơn trích thiếu. Trích thừa thì cùng lắm
phải sinh lại câu gợi ý; trích thiếu là để lọt đáp án ra ngoài.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

import sympy as sp

from src.core.schema import Item, Submission
from src.tutor.hint_policy import HintLevel
from src.verify.equivalence import ParseError, expr_equal, parse_math

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

#: Số đứng trơ trọi — ứng viên khi đáp án là một con số (định thức, hạng...).
_BARE_NUMBER = re.compile(r"(?<![\w./])-?\d+(?:[./]\d+)?(?![\w./])")
#: Số đứng sau những từ này là số THỨ TỰ, không phải giá trị: "bước 3", "hàng 2".
#: Không loại ra thì gợi ý chỉ bước sai ("em xem lại bước 3") sẽ bị chặn oan
#: mỗi khi đáp án tình cờ bằng 3.
_ORDINAL_CONTEXT = re.compile(r"(bước|hàng|dòng|cột|thứ|mức|câu|phần|R)\s*$", re.IGNORECASE)

#: Vùng công thức LOGIC (MAD101). Vùng toán học ở trên chỉ nhận ký tự ASCII số
#: học, nên "¬p ∨ ¬q" hay "~p | ~q" không bao giờ lọt vào đó — nếu không trích
#: riêng thì gợi ý có thể nói thẳng đáp án logic mà guardrail không hay biết.
_LOGIC_SPAN = re.compile(r"[A-Za-z0-9_¬∧∨→↔⇒⇔⊕~&|^()<>\-\s]{3,}")
_LOGIC_OPERATOR = re.compile(r"[¬∧∨→↔⇒⇔⊕~&|^]|->")

#: Số token tối đa trong một đoạn trước khi ngừng thử mọi tổ hợp con.
_MAX_TOKENS_PER_SPAN = 14


@dataclass
class LeakReport:
    """Kết quả kiểm tra một câu gợi ý."""

    leaked: bool
    level: HintLevel
    offending_expression: str | None = None
    reason: str = ""

    def __bool__(self) -> bool:
        return self.leaked


@lru_cache(maxsize=None)
def _verifier(subject: str):
    # Nhập muộn: registry kéo theo mọi verifier, không cần tới khi chỉ trích biểu thức.
    from src.verify.registry import verifier_for

    return verifier_for(subject)


# --------------------------------------------------------------------------
# Trích ứng viên
# --------------------------------------------------------------------------

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


def _bracket_groups(text: str) -> list[str]:
    """Mọi cụm trong ngoặc cân bằng có dấu phẩy: ``[1, 1]``, ``[[3/5, -7/10], ...]``, ``(2, 1)``.

    Vùng ký tự toán ở trên cố ý không chứa ``[`` ``]`` và dấu phẩy, nên ma trận
    với vector không bao giờ lọt vào đó — phải trích riêng. Ngoặc tròn đứng
    ngay sau chữ cái là lời gọi hàm (``sin(x)``, ``f(1, 2)``), bỏ qua.
    """
    groups: list[str] = []
    for start, char in enumerate(text):
        if char not in "[(":
            continue
        if char == "(" and start > 0 and text[start - 1].isalnum():
            continue
        depth = 0
        for end in range(start, len(text)):
            if text[end] in "[(":
                depth += 1
            elif text[end] in "])":
                depth -= 1
                if depth == 0:
                    group = text[start:end + 1]
                    if "," in group:
                        groups.append(group)
                    break
    return groups


def _bare_numbers(text: str) -> list[str]:
    numbers: list[str] = []
    for match in _BARE_NUMBER.finditer(text):
        if not _ORDINAL_CONTEXT.search(text[: match.start()]):
            numbers.append(match.group())
    return numbers


def extract_candidates(text: str) -> list[str]:
    """Mọi mảnh văn bản có thể là một đáp án, đã khử trùng lặp."""
    candidates: list[str] = []
    for pattern in _DELIMITED_PATTERNS:
        candidates.extend(re.findall(pattern, text, flags=re.DOTALL))
    for span in _MATH_SPAN.findall(text):
        candidates.extend(_span_candidates(span.strip()))
        candidates.extend(t for t in _MATH_TOKEN.findall(span) if looks_like_math(t))
    candidates.extend(_bracket_groups(text))
    candidates.extend(_bare_numbers(text))
    for span in _LOGIC_SPAN.findall(text):
        tokens = span.split()
        for start in range(len(tokens)):
            for end in range(start + 1, min(len(tokens), start + _MAX_TOKENS_PER_SPAN) + 1):
                piece = " ".join(tokens[start:end])
                if _LOGIC_OPERATOR.search(piece):
                    candidates.append(piece)

    unique: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = candidate.strip()
        if key and key not in seen:
            seen.add(key)
            unique.append(key)
    return unique


def extract_expressions(text: str) -> list[sp.Expr]:
    """Các ứng viên parse được thành biểu thức (bỏ ma trận, vector, số thứ tự)."""
    expressions: list[sp.Expr] = []
    seen: set[str] = set()
    for candidate in extract_candidates(text):
        if candidate.startswith("[") or not looks_like_math(candidate):
            continue
        try:
            expression = parse_math(candidate)
        except (ParseError, RecursionError):
            continue
        key = sp.srepr(expression)
        if key not in seen:
            seen.add(key)
            expressions.append(expression)
    return expressions


# --------------------------------------------------------------------------
# Phán xét
# --------------------------------------------------------------------------

def _is_restatement_of_problem(candidate: str, item: Item) -> bool:
    """Nhắc lại chính đề bài thì không phải là lộ đáp án."""
    if not item.integrand:
        return False
    try:
        return expr_equal(parse_math(candidate), parse_math(item.integrand)).equal
    except (ParseError, RecursionError):
        return False


def reveals_answer(candidate: str | sp.Expr, item: Item) -> bool:
    """Nếu nộp mảnh này làm đáp án thì verifier có chấm đúng không?"""
    text = str(candidate)
    if _is_restatement_of_problem(text, item):
        return False
    try:
        result = _verifier(item.subject.value).verify(
            item, Submission(item_id=item.item_id, final_answer=text)
        )
    except Exception:
        # Một mảnh văn bản làm verifier lỗi thì không thể là đáp án đúng.
        return False
    return result.final_answer_correct is True


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

    candidates = extract_candidates(hint_text)

    # Đáp án bằng lời ("vô nghiệm", "không khả nghịch") không phải biểu thức
    # nào cả — phải dò trực tiếp trong câu. Chỉ xét cụm có chữ và đủ dài để
    # không khớp nhầm vào một mẩu của từ khác.
    lowered = hint_text.lower()
    for phrase in getattr(_verifier(item.subject.value), "verbal_answers", ()):
        if len(phrase) >= 5 and any(c.isalpha() for c in phrase) and phrase in lowered:
            candidates.append(phrase)

    for candidate in candidates:
        if reveals_answer(candidate, item):
            return LeakReport(
                leaked=True,
                level=level,
                offending_expression=candidate,
                reason=f"«{candidate}» sẽ được chấm là đáp án đúng — không được nói ở mức {int(level)}",
            )

    return LeakReport(False, level, reason="Không phát hiện đáp án trong câu gợi ý")


def leak_rate(reports: list[LeakReport]) -> float:
    """Tỉ lệ gợi ý bị rò đáp án — số liệu cho EXP-8."""
    if not reports:
        return 0.0
    return sum(1 for report in reports if report.leaked) / len(reports)
