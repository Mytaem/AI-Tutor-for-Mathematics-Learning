"""Verifier cho MAE101 — Mathematics for Engineering (giới hạn, đạo hàm, tích phân).

Nguyên tắc chấm tích phân: KHÔNG so đáp án sinh viên với một dạng chuẩn duy
nhất, mà lấy đạo hàm đáp án của họ rồi đối chiếu với biểu thức dưới dấu tích
phân. Một tích phân có vô số dạng viết đúng (``sin²x/2``, ``-cos²x/2``,
``-cos2x/4`` đều là nguyên hàm của ``sinx·cosx``); liệt kê trước là bất khả thi,
còn đạo hàm ngược thì chấp nhận đúng tất cả.
"""

from __future__ import annotations

from contextlib import suppress

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
ERR_DERIV_INSTEAD = "MAE.INT.DERIV_INSTEAD"  # lấy đạo hàm thay vì nguyên hàm
ERR_SUBST_NOFACTOR = "MAE.INT.SUBST.NOFACTOR"  # đổi biến nhưng quên nhân du
ERR_LINEARITY = "MAE.INT.LINEARITY"        # tưởng ∫f·g = (∫f)(∫g)
ERR_LIM_INDET_ZERO = "MAE.LIM.INDET_ZERO"      # thay 0/0 rồi kết luận bằng 0
ERR_LIM_INF_CONSTTERM = "MAE.LIM.INF_CONSTTERM"  # x->oo: lấy tỉ số hạng tự do
ERR_LIM_SIGN = "MAE.LIM.SIGN"                  # sai dấu khi thay giá trị
ERR_DER_POWER_NODEC = "MAE.DER.POWER_NODEC"    # nhân số mũ, quên giảm bậc
ERR_DER_POWER_NOMULT = "MAE.DER.POWER_NOMULT"  # giảm bậc, quên nhân số mũ
ERR_DER_PRODUCT_SEPARATE = "MAE.DER.PRODUCT_SEPARATE"  # (u.v)' = u'.v'
ERR_DER_QUOTIENT_SIGN = "MAE.DER.QUOTIENT_SIGN"  # sai dấu quy tắc thương
ERR_DER_CHAIN_NOINNER = "MAE.DER.CHAIN_NOINNER"  # quên nhân đạo hàm hàm trong


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
        elif item.meta.get("task") == "limit":
            codes.extend(self._diagnose_limit(item, raw))
        elif item.meta.get("task") == "derivative":
            codes.extend(self._diagnose_derivative(item, raw))

        return codes

    # ------------------------------------------------------------------
    # Giới hạn
    # ------------------------------------------------------------------

    def _diagnose_limit(self, item: Item, raw: str) -> list[str]:
        """Gọi tên lỗi bằng cách DỰNG LẠI đúng đáp án mà từng lỗi sẽ cho ra.

        Cách này đáng tin hơn so khớp mẫu trên chuỗi: nó trả lời đúng câu hỏi
        "bài làm này khớp với lỗi nào", và không bao giờ gắn nhãn cho một đáp án
        mà lỗi đó không thể sinh ra.
        """
        try:
            given = parse_math(raw)
        except ParseError:
            return []

        indeterminate = item.meta.get("indeterminate")
        expression = self._limit_expression(item)
        variable = sp.Symbol(item.variable or "x")

        # Dạng vô định mà trả 0 — lỗi khái niệm nặng nhất của chương này.
        if indeterminate and given == 0:
            return [ERR_LIM_INDET_ZERO]

        if expression is not None and indeterminate == "oo/oo":
            wrong = self._constant_term_ratio(expression, variable)
            if wrong is not None and expr_equal(given, wrong, domain=self.domain).equal:
                return [ERR_LIM_INF_CONSTTERM]

        # Sai dấu: xét cuối cùng vì nó khớp rộng nhất.
        if item.answer is not None:
            with suppress(ParseError):
                correct = parse_math(str(item.answer))
                if correct != 0 and expr_equal(given, -correct, domain=self.domain).equal:
                    return [ERR_LIM_SIGN]
        return []

    def _limit_expression(self, item: Item):
        with suppress(ParseError, KeyError):
            return parse_math(str(item.meta["expr"]))
        return None

    @staticmethod
    def _constant_term_ratio(expression, variable):
        """Tỉ số HẠNG TỰ DO của tử và mẫu — đáp án mà lỗi `INF_CONSTTERM` cho ra."""
        numerator, denominator = sp.fraction(expression)
        with suppress(sp.PolynomialError, TypeError, ZeroDivisionError):
            top = sp.Poly(numerator, variable).coeff_monomial(1)
            bottom = sp.Poly(denominator, variable).coeff_monomial(1)
            if bottom:
                return sp.Rational(int(top), int(bottom))
        return None

    # ------------------------------------------------------------------
    # Đạo hàm
    # ------------------------------------------------------------------

    def _diagnose_derivative(self, item: Item, raw: str) -> list[str]:
        try:
            given = parse_math(raw)
        except ParseError:
            return []

        expression = self._limit_expression(item)      # cùng khoá meta["expr"]
        if expression is None:
            return []
        variable = sp.Symbol(item.variable or "x")
        rule = item.meta.get("rule")

        def matches(candidate) -> bool:
            if candidate is None:
                return False
            with suppress(TypeError, ValueError, sp.SympifyError):
                return expr_equal(given, candidate, domain=self.domain).equal
            return False

        if rule == "product" and matches(self._product_as_product(expression, variable)):
            return [ERR_DER_PRODUCT_SEPARATE]
        if rule == "quotient" and matches(self._quotient_wrong_sign(expression, variable)):
            return [ERR_DER_QUOTIENT_SIGN]
        if rule == "chain" and matches(self._chain_without_inner(expression, variable)):
            return [ERR_DER_CHAIN_NOINNER]
        if matches(self._power_no_decrement(expression, variable)):
            return [ERR_DER_POWER_NODEC]
        if matches(self._power_no_multiply(expression, variable)):
            return [ERR_DER_POWER_NOMULT]
        return []

    @staticmethod
    def _power_no_decrement(expression, variable):
        """``(a·xⁿ)' = a·n·xⁿ`` — nhân số mũ nhưng quên giảm bậc."""
        with suppress(TypeError, ValueError):
            terms = sp.Add.make_args(sp.expand(expression))
            return sp.simplify(sum(
                coefficient * exponent * variable**exponent
                for coefficient, exponent in (t.as_coeff_exponent(variable) for t in terms)
            ))
        return None

    @staticmethod
    def _power_no_multiply(expression, variable):
        """``(a·xⁿ)' = a·xⁿ⁻¹`` — giảm bậc nhưng quên nhân số mũ."""
        with suppress(TypeError, ValueError):
            terms = sp.Add.make_args(sp.expand(expression))
            return sp.simplify(sum(
                coefficient * variable ** (exponent - 1)
                for coefficient, exponent in (t.as_coeff_exponent(variable) for t in terms)
            ))
        return None

    @staticmethod
    def _product_as_product(expression, variable):
        """``(u·v)' = u'·v'``."""
        factors = sp.Mul.make_args(expression)
        if len(factors) < 2:
            return None
        return sp.simplify(sp.Mul(*[sp.diff(f, variable) for f in factors]))

    @staticmethod
    def _quotient_wrong_sign(expression, variable):
        """Tử là ``u'v + uv'`` thay vì ``u'v − uv'``."""
        u, v = sp.fraction(expression)
        if v == 1:
            return None
        return sp.simplify((sp.diff(u, variable) * v + u * sp.diff(v, variable)) / v**2)

    @staticmethod
    def _chain_without_inner(expression, variable):
        """Đúng hàm ngoài, quên nhân đạo hàm hàm trong."""
        if isinstance(expression, sp.Pow) and expression.exp.is_Integer:
            inner, exponent = expression.base, expression.exp
            return sp.simplify(exponent * inner ** (exponent - 1))
        if isinstance(expression, sp.Function) and len(expression.args) == 1:
            inner = expression.args[0]
            return sp.simplify(
                sp.diff(expression.func(variable), variable).subs(variable, inner)
            )
        return None

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
            # => sinh viên làm đúng dạng nhưng sai đúng một hệ số.
            #
            # Mã CỤ THỂ đứng trước, mã mô tả hiện tượng đứng sau. Thứ tự này quan
            # trọng vì gợi ý mức 2 lấy mã đầu tiên: bản cũ luôn đặt "sai hệ số
            # hằng" lên đầu nên 262 ca lỗi DẤU nhận được câu nhắc chệch hẳn cái
            # bẫy đang mắc.
            #
            # Vẫn giữ cả hai mã chứ không bỏ mã chung: nhìn vào ĐÁP ÁN CUỐI thì
            # "quên nhân du khi đổi biến" và "sai một hệ số hằng" cho ra đúng một
            # thứ, không có cách nào phân biệt. Bỏ đi một mã là giả vờ chắc chắn
            # hơn thực tế — và đo được: làm thế thì tỉ lệ gán đúng mã tụt 93% → 89%.
            if abs(ratio + 1.0) < 1e-9:
                codes.append(ERR_SIGN)
            elif any(skill.startswith("MAE.INT.SUBST") for skill in item.skills):
                codes.append(ERR_SUBST_NOFACTOR)
            codes.append(ERR_CONST_FACTOR)
            return codes

        # Hai luật dưới đây thêm vào sau khi phân tích lỗi (mục L4): chúng là hai
        # nguyên nhân "không gán nổi mã nào" lớn nhất — 224 và 125 ca.
        if self._looks_like_derivative(answer, integrand, var):
            codes.append(ERR_DERIV_INSTEAD)
        elif self._looks_like_split_product(answer, integrand, var):
            codes.append(ERR_LINEARITY)

        return codes

    @staticmethod
    def _looks_like_derivative(answer: sp.Expr, integrand: sp.Expr, var: sp.Symbol) -> bool:
        """Sinh viên ĐẠO HÀM biểu thức thay vì lấy nguyên hàm.

        Nhận ra bằng cách so trực tiếp với f′(x), bỏ qua hằng số cộng thêm (bài
        làm thường vẫn có "+ C" theo thói quen).
        """
        done, derivative = run_with_timeout(lambda: sp.diff(integrand, var))
        if not done or derivative is None or derivative == 0:
            return False
        return equal_up_to_constant(answer, derivative, var)

    @staticmethod
    def _looks_like_split_product(answer: sp.Expr, integrand: sp.Expr, var: sp.Symbol) -> bool:
        """Tưởng ∫f·g dx = (∫f dx)·(∫g dx).

        Chỉ xét khi biểu thức dưới dấu tích phân đúng là một tích hai thừa số, và
        cả hai thừa số đều lấy được nguyên hàm — đúng điều kiện sinh ra kiểu sai này.
        """
        factors = integrand.as_ordered_factors()
        if len(factors) != 2:
            return False
        done, pieces = run_with_timeout(
            lambda: [sp.integrate(factor, var) for factor in factors])
        if not done or pieces is None or any(p is None or p.has(sp.Integral) for p in pieces):
            return False
        return equal_up_to_constant(answer, pieces[0] * pieces[1], var)

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
