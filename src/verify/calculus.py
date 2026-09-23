"""Verifier cho MAE101 — Mathematics for Engineering (giới hạn, đạo hàm, tích phân).

Nguyên tắc chấm tích phân: KHÔNG so đáp án sinh viên với một dạng chuẩn duy
nhất, mà lấy đạo hàm đáp án của họ rồi đối chiếu với biểu thức dưới dấu tích
phân. Một tích phân có vô số dạng viết đúng (``sin²x/2``, ``-cos²x/2``,
``-cos2x/4`` đều là nguyên hàm của ``sinx·cosx``); liệt kê trước là bất khả thi,
còn đạo hàm ngược thì chấp nhận đúng tất cả.
"""

from __future__ import annotations

import sympy as sp

from src.core.schema import (
    AnswerType,
    Item,
    StepCheck,
    Subject,
    Submission,
    VerificationResult,
)
from src.verify.base import Verifier
from src.verify.equivalence import (
    EquivalenceResult,
    ParseError,
    equal_up_to_constant,
    number_equal,
    expr_equal,
    parse_math,
    run_with_timeout,
)

# Mã lỗi tầng 2 cho MAE101 (xem mục A3 trong PLAN.md).
ERR_NO_CONSTANT = "MAE.INT.NOCONST"        # quên "+ C" ở nguyên hàm
ERR_CONST_FACTOR = "MAE.INT.CONSTFACTOR"   # sai đúng một hệ số hằng
ERR_DEF_NOT_EVALUATED = "MAE.INT.DEF.NOEVAL"  # tích phân xác định còn chứa biến
ERR_SIGN = "MAE.SIGN"                      # sai dấu toàn cục
ERR_ALG_STEP = "MAE.ALG.STEP"             # một bước biến đổi không tương đương bước trước
ERR_DEF_SWAPBOUNDS = "MAE.INT.DEF.SWAPBOUNDS"  # thế cận ngược: F(a) − F(b)


class CalculusVerifier(Verifier):
    """Chấm bài MAE101."""

    subject = Subject.MAE101
    name = "calculus"
    domain = "positive"

    def verify(self, item: Item, submission: Submission) -> VerificationResult:
        result = VerificationResult(item_id=item.item_id, is_correct=False, verifier_used=self.name)

        step_checks = self.check_steps(item, submission.steps) if submission.steps else []
        result.step_results = step_checks
        result.first_wrong_step = self.first_wrong(step_checks)
        # Đã tìm ra bước sai thì phải NÓI ra bằng mã lỗi, không chỉ đánh dấu vị
        # trí — thiếu mã này thì gợi ý mức 2 không có gì để cảnh báo, và số liệu
        # "gán đúng mã" bỏ sót trọn một loại lỗi mà tầng ký hiệu vốn đã bắt được.
        step_codes = [ERR_ALG_STEP] if result.first_wrong_step is not None else []

        if submission.final_answer is None:
            result.notes.append("Chưa nộp đáp án cuối, chỉ kiểm tra các bước")
            result.confidence = 0.5
            result.candidate_error_codes = step_codes
            return result

        answer_check = self.check_final_answer(item, submission.final_answer)
        result.final_answer_correct = answer_check.equal
        result.confidence = answer_check.confidence
        result.notes.append(answer_check.detail)

        if answer_check.method == "parse_error":
            # Lỗi nhập liệu: không kết luận đúng/sai, hỏi lại sinh viên.
            result.final_answer_correct = None
            result.confidence = 0.0
            result.notes.append("Cần sinh viên nhập lại đáp án")
            return result

        result.candidate_error_codes = self.diagnose(item, submission, answer_check) + step_codes

        # Đáp án cuối đúng nhưng có bước sai giữa chừng vẫn là bài làm chưa đạt:
        # rất có thể sinh viên đoán ra kết quả hoặc sai bù trừ.
        result.is_correct = bool(answer_check.equal) and result.first_wrong_step is None
        if answer_check.equal and result.first_wrong_step is not None:
            result.notes.append(
                f"Đáp án cuối đúng nhưng bước {result.first_wrong_step} không hợp lệ — có thể sai bù trừ"
            )
        return result

    # ------------------------------------------------------------------
    # Chẩn đoán lỗi (tầng symbolic)
    # ------------------------------------------------------------------

    def diagnose(self, item: Item, submission: Submission, answer_check: EquivalenceResult) -> list[str]:
        """Suy ra mã lỗi ứng viên từ bản chất sai lệch, không đoán bằng LLM."""
        codes: list[str] = []
        raw = submission.final_answer or ""

        if item.answer_type is AnswerType.ANTIDERIVATIVE:
            codes.extend(self._diagnose_antiderivative(item, raw, answer_check))
        elif item.answer_type is AnswerType.NUMBER and item.bounds:
            codes.extend(self._diagnose_definite_integral(item, raw))

        return codes

    def _diagnose_antiderivative(self, item: Item, raw: str, answer_check: EquivalenceResult) -> list[str]:
        codes: list[str] = []

        # Quên "+ C". Đây là lỗi hình thức: đáp án vẫn đúng về mặt nguyên hàm,
        # nên không đánh trượt, chỉ nhắc.
        if not self._has_integration_constant(raw):
            codes.append(ERR_NO_CONSTANT)

        if answer_check.equal:
            return codes

        try:
            answer = parse_math(raw)
            integrand = parse_math(item.integrand or "")
            var = sp.Symbol(item.variable)
        except ParseError:
            return codes

        done, derivative = run_with_timeout(lambda: sp.diff(answer, var))
        if not done or derivative is None:
            return codes

        ratio = self._constant_ratio(derivative, integrand, var)
        if ratio is not None and abs(ratio - 1.0) > 1e-9:
            # Đạo hàm của đáp án tỉ lệ hằng với biểu thức dưới dấu tích phân
            # => sinh viên làm đúng dạng nhưng sai đúng một hệ số. Đây là dấu
            # hiệu kinh điển của việc quên chia hệ số khi đổi biến.
            codes.append(ERR_CONST_FACTOR)
            if abs(ratio + 1.0) < 1e-9:
                codes.append(ERR_SIGN)

        return codes

    def _diagnose_definite_integral(self, item: Item, raw: str) -> list[str]:
        """Tích phân xác định phải ra một số; còn chứa biến là chưa thế cận."""
        try:
            answer = parse_math(raw)
        except ParseError:
            return []
        if sp.Symbol(item.variable) in answer.free_symbols:
            return [ERR_DEF_NOT_EVALUATED]

        # Đúng độ lớn nhưng ngược dấu: dấu hiệu của F(a) − F(b) thay vì F(b) − F(a).
        if item.answer is not None and not answer.free_symbols:
            try:
                reference = parse_math(str(item.answer))
            except ParseError:
                return []
            if reference != 0 and number_equal(answer, -reference).equal:
                return [ERR_DEF_SWAPBOUNDS]
        return []

    @staticmethod
    def _has_integration_constant(raw: str) -> bool:
        """Đáp án có kèm hằng số tích phân không?"""
        try:
            expr = parse_math(raw)
        except ParseError:
            return False
        return any(str(symbol).upper().startswith("C") for symbol in expr.free_symbols)

    @staticmethod
    def _constant_ratio(numerator: sp.Expr, denominator: sp.Expr, var: sp.Symbol) -> float | None:
        """Tỉ số hai biểu thức có phải hằng số không? Trả giá trị hằng, hoặc None.

        Dùng lấy mẫu số học thay vì ``simplify`` vì ở đây ta chỉ cần biết tỉ số
        có ổn định hay không — lấy mẫu trả lời trong vài ms và không treo.
        """
        ratio = numerator / denominator
        done, samples = run_with_timeout(
            lambda: [complex(ratio.evalf(subs={var: value}, n=20)) for value in (0.37, 0.91, 1.53, 2.11)]
        )
        if not done or samples is None:
            return None

        finite = [s for s in samples if s == s and abs(s) != float("inf")]
        if len(finite) < 3:
            return None
        first = finite[0]
        if any(abs(value - first) > 1e-7 * max(1.0, abs(first)) for value in finite):
            return None
        if abs(first.imag) > 1e-9:
            return None
        return first.real

    # ------------------------------------------------------------------
    # Chấm bước, có xử lý dấu tích phân
    # ------------------------------------------------------------------

    def compare_consecutive(
        self,
        item: Item,
        previous: sp.Expr,
        current: sp.Expr,
        index: int,
        substitutions: dict[sp.Symbol, sp.Expr] | None = None,
    ) -> StepCheck:
        """Ghi đè lớp cơ sở để xử lý bước còn chứa ``Integral``.

        Lời giải tích phân đi qua các dạng trung gian như ``Integral(x**2, x)``
        rồi mới ra ``x**3/3``. Hai dạng đó không "bằng nhau" về cấu trúc nhưng
        bằng nhau về giá trị, nên phải tính ``.doit()`` trước khi so, và so theo
        kiểu sai khác hằng số vì hằng số tích phân có thể xuất hiện bất cứ lúc nào.
        """
        substitutions = substitutions or {}
        base_var = sp.Symbol(item.variable)

        # Hai bước đều là tích phân nhưng khác biến => đang đổi biến. Phải so ở
        # mức biểu thức dưới dấu tích phân SAU KHI quy về biến gốc, vì phép đổi
        # biến làm đổi cả vi phân.
        if isinstance(previous, sp.Integral) and isinstance(current, sp.Integral):
            left = self._integrand_in_base_var(previous, base_var, substitutions)
            right = self._integrand_in_base_var(current, base_var, substitutions)
            if left is None or right is None:
                return StepCheck(
                    step=index, ok=None, method="skipped",
                    reason="Bước đổi biến nhưng chưa khai báo phép thế (ví dụ: u = x**2 + 1)",
                )
            result = expr_equal(left, right, domain=self.domain)
            return StepCheck(
                step=index, ok=result.equal, method=result.method, confidence=result.confidence,
                reason=f"Quy về biến {base_var}: {left} so với {right} — {result.detail}",
            )

        if not (previous.has(sp.Integral) or current.has(sp.Integral)):
            return super().compare_consecutive(item, previous, current, index, substitutions)

        # Một bên còn dấu tích phân, bên kia đã tính xong. Phải tính .doit()
        # TRƯỚC rồi mới thay biến ngược — thay biến thẳng vào một Integral sẽ
        # làm hỏng biến lấy tích phân và cho kết quả vô nghĩa.
        done_prev, evaluated_prev = run_with_timeout(lambda: previous.doit())
        done_curr, evaluated_curr = run_with_timeout(lambda: current.doit())
        if not (done_prev and done_curr) or evaluated_prev is None or evaluated_curr is None:
            return StepCheck(
                step=index, ok=None, method="timeout",
                reason="Không tính được tích phân trong giới hạn thời gian",
            )

        evaluated_prev = self.apply_substitutions(evaluated_prev, substitutions)
        evaluated_curr = self.apply_substitutions(evaluated_curr, substitutions)

        if (
            evaluated_prev.free_symbols != evaluated_curr.free_symbols
            and evaluated_prev.free_symbols
            and evaluated_curr.free_symbols
        ):
            return StepCheck(
                step=index, ok=None, method="skipped",
                reason="Bước đổi biến — cần khai báo phép thế mới kiểm chứng được",
            )

        variable = next(iter(evaluated_prev.free_symbols), base_var)
        result = equal_up_to_constant(evaluated_prev, evaluated_curr, variable)
        return StepCheck(
            step=index,
            ok=result.equal,
            reason=result.detail,
            method=result.method,
            confidence=result.confidence,
        )

    @staticmethod
    def _integrand_in_base_var(
        integral: sp.Integral,
        base_var: sp.Symbol,
        substitutions: dict[sp.Symbol, sp.Expr],
    ) -> sp.Expr | None:
        """Quy biểu thức dưới dấu tích phân về biến gốc.

        Công thức đổi biến: ``∫ g(u) du = ∫ g(f(x))·f'(x) dx`` với ``u = f(x)``.
        Hệ số ``f'(x)`` chính là chỗ sinh viên hay quên — và cũng là chỗ mà việc
        thay biến một cách thô (chỉ subs u -> f(x)) sẽ cho kết quả sai.
        """
        if len(integral.limits) != 1:
            return None

        variable = integral.limits[0][0]
        if variable == base_var:
            return integral.function

        replacement = substitutions.get(variable)
        if replacement is None:
            return None
        return integral.function.subs(variable, replacement) * sp.diff(replacement, base_var)
