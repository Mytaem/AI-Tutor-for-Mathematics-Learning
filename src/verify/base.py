"""Giao diện chung cho verifier của cả 4 môn.

Lý do tách lớp cơ sở này ra: phần lớn công việc chấm bài giống nhau giữa các môn
(so đáp án cuối theo kiểu dữ liệu, kiểm tra chuỗi bước biến đổi). Mỗi môn chỉ
khác ở *cách kiểm chứng đặc thù* — đạo hàm ngược cho MAE101, ``checkodesol`` cho
MAI391, Monte Carlo cho MAS291. Nhờ vậy việc "mở rộng sang môn mới" chỉ là viết
thêm một lớp con, và đó là điều cần chứng minh khi bảo vệ.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod

import sympy as sp

from src.core.schema import (
    AnswerType,
    Item,
    StepCheck,
    Subject,
    Submission,
    VerificationResult,
)
from src.verify.equivalence import (
    Domain,
    EquivalenceResult,
    ParseError,
    expr_equal,
    is_antiderivative_of,
    matrix_equal,
    number_equal,
    parallel_vectors,
    parse_math,
    set_equal,
)


def split_top_level(text: str, separator: str = ",") -> list[str]:
    """Tách chuỗi theo dấu phân cách, bỏ qua dấu nằm trong ngoặc.

    ``"1, 3"`` -> ``["1", "3"]`` nhưng ``"f(1, 2), 3"`` -> ``["f(1, 2)", "3"]``.
    Cần cho việc đọc tập nghiệm sinh viên nhập.
    """
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for char in text:
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
        if char == separator and depth <= 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(char)
    parts.append("".join(current))
    return [p.strip() for p in parts if p.strip()]


def parse_answer_list(text: str) -> list[str]:
    """Đọc đáp án dạng tập hợp mà sinh viên nhập theo nhiều kiểu khác nhau.

    Chấp nhận: ``{1, 3}``, ``[1, 3]``, ``1, 3``, ``x = 1; x = 3``.
    """
    cleaned = text.strip()
    if cleaned.startswith(("{", "[", "(")) and cleaned.endswith(("}", "]", ")")):
        cleaned = cleaned[1:-1]
    cleaned = cleaned.replace(";", ",")
    # Bỏ tiền tố kiểu "x =" hay "λ =" mà sinh viên hay viết trước mỗi nghiệm.
    # [^\W\d] = mọi chữ cái Unicode, để nhận cả ký hiệu Hy Lạp như λ.
    parts = split_top_level(cleaned)
    return [re.sub(r"^[^\W\d]\w*\s*=\s*", "", p).strip() for p in parts]


def _wrapped(text: str, opening: str, closing: str) -> bool:
    """Chuỗi có được bao trọn bởi MỘT cặp ngoặc từ đầu tới cuối không?

    ``[1, 2]`` thì có; ``[1] + [2]`` thì không, dù nó cũng mở đầu bằng ``[`` và
    kết thúc bằng ``]``.
    """
    if not (text.startswith(opening) and text.endswith(closing)):
        return False
    depth = 0
    for index, char in enumerate(text):
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
            if depth == 0 and index != len(text) - 1:
                return False
    return depth == 0


def parse_matrix(text: str) -> sp.Matrix:
    """Đọc ma trận hoặc vector sinh viên nhập.

    Chấp nhận ``[[1, 2], [3, 4]]``, ``Matrix([[1, 2], [3, 4]])``, ``[1, -1]``,
    ``(1, -1)``. Vector một hàng được dựng thành vector CỘT, đúng quy ước của
    đại số tuyến tính.

    Không dùng thẳng ``parse_math`` cho cả chuỗi: nó đổi ``[`` thành ``(`` để
    đọc được biểu thức, nên ``[1, -1]`` bị hiểu thành một tuple và bị từ chối.
    Ở đây ta tách cấu trúc ngoặc trước, chỉ đưa từng PHẦN TỬ cho ``parse_math``.
    """
    cleaned = text.strip()
    match = re.match(r"^Matrix\s*\((.*)\)\s*$", cleaned, flags=re.DOTALL)
    if match:
        cleaned = match.group(1).strip()

    def build(fragment: str):
        fragment = fragment.strip()
        for opening, closing in (("[", "]"), ("(", ")")):
            if _wrapped(fragment, opening, closing):
                inner = fragment[1:-1]
                parts = split_top_level(inner)
                # "(x + 1)" là một biểu thức trong ngoặc, không phải vector 1 phần tử.
                if opening == "(" and len(parts) == 1:
                    break
                return [build(part) for part in parts]
        return parse_math(fragment)

    structure = build(cleaned)
    if not isinstance(structure, list):
        raise ParseError(f"{text!r} không phải ma trận hay vector")

    try:
        # sp.Matrix dựng danh sách phẳng thành vector cột, danh sách lồng thành ma trận.
        return sp.Matrix(structure)
    except (ValueError, TypeError, sp.SympifyError) as exc:
        raise ParseError(f"Các hàng của {text!r} không cùng độ dài") from exc


class Verifier(ABC):
    """Lớp cơ sở cho verifier của một môn."""

    subject: Subject
    name: str = "base"
    domain: Domain = "positive"

    @abstractmethod
    def verify(self, item: Item, submission: Submission) -> VerificationResult:
        """Chấm một bài làm, trả về kết quả theo hợp đồng ``VerificationResult``."""

    # ------------------------------------------------------------------
    # Chấm đáp án cuối
    # ------------------------------------------------------------------

    def check_final_answer(self, item: Item, answer: str) -> EquivalenceResult:
        """Điều phối theo ``answer_type`` sang đúng hàm so sánh."""
        if not answer or not answer.strip():
            return EquivalenceResult(False, "structural", 1.0, "Chưa có đáp án")

        try:
            return self._dispatch_answer(item, answer)
        except ParseError as exc:
            # Không đọc được đầu vào thì đây là lỗi nhập liệu, KHÔNG phải lỗi
            # toán học — không được kết luận sinh viên làm sai.
            return EquivalenceResult(False, "parse_error", 0.0, str(exc))

    def _dispatch_answer(self, item: Item, answer: str) -> EquivalenceResult:
        kind = item.answer_type

        if kind is AnswerType.ANTIDERIVATIVE:
            if not item.integrand:
                return EquivalenceResult(False, "structural", 0.0, "Đề thiếu trường integrand")
            return is_antiderivative_of(answer, item.integrand, item.variable, domain=self.domain)

        if kind is AnswerType.EXPRESSION:
            return expr_equal(answer, str(item.answer), domain=self.domain)

        if kind is AnswerType.NUMBER:
            return number_equal(parse_math(answer), item.answer)

        if kind is AnswerType.SET:
            expected = item.answer if isinstance(item.answer, (list, tuple)) else [item.answer]
            return set_equal(parse_answer_list(answer), list(expected), domain=self.domain)

        if kind is AnswerType.MATRIX:
            return matrix_equal(parse_matrix(answer), item.answer)

        if kind is AnswerType.VECTOR_DIRECTION:
            return parallel_vectors(parse_matrix(answer), item.answer)

        if kind is AnswerType.BOOLEAN:
            return self._check_boolean(answer, item.answer)

        return EquivalenceResult(
            False, "manual", 0.0,
            f"Kiểu đáp án {kind.value} phải chấm bằng rubric, không chấm tự động được",
        )

    @staticmethod
    def _check_boolean(answer: str, expected: object) -> EquivalenceResult:
        truthy = {"true", "đúng", "dung", "t", "yes", "1", "có", "co"}
        falsy = {"false", "sai", "f", "no", "0", "không", "khong"}
        normalized = answer.strip().lower()

        if normalized in truthy:
            value: bool | None = True
        elif normalized in falsy:
            value = False
        else:
            return EquivalenceResult(False, "parse_error", 0.0, f"Không hiểu đáp án {answer!r}")

        ok = value is bool(expected)
        return EquivalenceResult(ok, "structural", 1.0, f"Trả lời {value}, đáp án đúng là {bool(expected)}")

    # ------------------------------------------------------------------
    # Chấm chuỗi bước biến đổi
    # ------------------------------------------------------------------

    def check_steps(self, item: Item, steps: list[str]) -> list[StepCheck]:
        """Kiểm tra từng bước có tương đương bước liền trước không.

        Quy ước quan trọng: khi không đủ cơ sở kết luận (không parse được, hai
        bước dùng biến khác nhau sau khi đổi biến), trả ``ok=None`` chứ không
        trả ``ok=False``. Xem docstring của ``StepCheck``.
        """
        checks: list[StepCheck] = []
        previous: sp.Expr | None = None
        substitutions: dict[sp.Symbol, sp.Expr] = {}

        for index, raw in enumerate(steps, start=1):
            # Sinh viên hay viết "Đặt u = x² + 1" thành một dòng riêng. Đó là
            # khai báo phép thế chứ không phải một bước biến đổi, và nếu không
            # đọc nó thì mọi bước sau đều thành "không kiểm chứng được".
            declaration = self._parse_substitution(raw, item.variable)
            if declaration is not None:
                symbol, expression = declaration
                substitutions[symbol] = expression
                checks.append(StepCheck(
                    step=index, ok=True, method="substitution", confidence=1.0,
                    reason=f"Ghi nhận phép đổi biến {symbol} = {expression}",
                ))
                continue

            try:
                current = parse_math(raw)
            except ParseError as exc:
                checks.append(StepCheck(step=index, ok=None, reason=f"Không đọc được: {exc}", method="parse_error"))
                previous = None
                continue

            if previous is None:
                checks.append(StepCheck(step=index, ok=True, reason="Bước đầu tiên, lấy làm mốc", method="baseline", confidence=1.0))
                previous = current
                continue

            checks.append(self.compare_consecutive(item, previous, current, index, substitutions))
            previous = current

        return checks

    @staticmethod
    def _parse_substitution(raw: str, base_var: str) -> tuple[sp.Symbol, sp.Expr] | None:
        """Nhận diện dòng khai báo phép đổi biến, ví dụ ``u = x**2 + 1``.

        Chỉ coi là phép thế khi vế trái là một biến MỚI và vế phải có chứa biến
        gốc. Nhờ điều kiện thứ hai, dòng kiểu ``I = x**3/3`` (sinh viên đặt tên
        cho kết quả) không bị hiểu nhầm thành phép đổi biến.
        """
        match = re.match(r"^\s*([A-Za-z]\w*)\s*=\s*(.+)$", raw.strip())
        if match is None:
            return None

        name, right_hand_side = match.groups()
        if name == base_var:
            return None
        try:
            expression = parse_math(right_hand_side)
        except ParseError:
            return None
        if sp.Symbol(base_var) not in expression.free_symbols:
            return None
        return sp.Symbol(name), expression

    def compare_consecutive(
        self,
        item: Item,
        previous: sp.Expr,
        current: sp.Expr,
        index: int,
        substitutions: dict[sp.Symbol, sp.Expr] | None = None,
    ) -> StepCheck:
        """So sánh hai bước liên tiếp. Lớp con ghi đè để xử lý đặc thù từng môn."""
        substitutions = substitutions or {}
        previous = self.apply_substitutions(previous, substitutions)
        current = self.apply_substitutions(current, substitutions)

        if previous.free_symbols != current.free_symbols and previous.free_symbols and current.free_symbols:
            return StepCheck(
                step=index, ok=None, method="skipped",
                reason="Hai bước dùng biến khác nhau và chưa có khai báo phép thế tương ứng",
            )

        result = expr_equal(previous, current, domain=self.domain)
        return StepCheck(
            step=index,
            ok=result.equal,
            reason=result.detail,
            method=result.method,
            confidence=result.confidence,
        )

    @staticmethod
    def apply_substitutions(expr: sp.Expr, substitutions: dict[sp.Symbol, sp.Expr]) -> sp.Expr:
        """Thay biến phụ trở lại theo biến gốc để hai bước so sánh được với nhau."""
        for symbol, replacement in substitutions.items():
            if symbol in expr.free_symbols:
                expr = expr.subs(symbol, replacement)
        return expr

    # ------------------------------------------------------------------
    # Tiện ích dựng kết quả
    # ------------------------------------------------------------------

    @staticmethod
    def first_wrong(checks: list[StepCheck]) -> int | None:
        """Chỉ số bước sai đầu tiên; bỏ qua các bước không kiểm chứng được."""
        for check in checks:
            if check.ok is False:
                return check.step
        return None
