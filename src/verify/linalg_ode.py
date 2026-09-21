"""Verifier cho MAI391 — đại số tuyến tính và phương trình vi phân.

Cùng triết lý với MAE101 (chấm tích phân bằng đạo hàm ngược): KHÔNG so đáp án
của sinh viên với một dạng chuẩn duy nhất, mà kiểm tra TÍNH CHẤT toán học mà
một đáp án đúng phải thoả. Ở môn này điều đó càng quan trọng, vì gần như mọi
loại đáp án đều có vô số dạng đúng:

- Nghiệm hệ vô số nghiệm: ``[1-s-t, s, t]`` và ``[u, v, 1-u-v]`` đều đúng.
  → thế ngược ``A·x = b`` và đếm số bậc tự do, không so khớp.
- Vector riêng: ``[1, 1]``, ``[3, 3]``, ``[-2, -2]`` đều đúng.
  → kiểm ``A·v = λ·v`` và ``v ≠ 0``, không so với một vector chuẩn.
- Ma trận nghịch đảo: kiểm ``A·B = I``.
- Nghiệm tổng quát ODE: ``C1·eˣ + C2·e²ˣ`` hay ``A·e²ˣ + B·eˣ`` đều đúng.
  → thế vào phương trình, rồi đếm số hằng số ĐỘC LẬP (không chỉ đếm số ký hiệu).
- Các bước khử Gauss: hai bước liên tiếp phải tương đương hàng — tức có cùng
  dạng bậc thang rút gọn. Đây là bất biến chính xác, không phải heuristic.

Cái giá của cách làm này là chẩn đoán lỗi phải tự dựng lại: khi đáp án sai, ta
thử xem nó có khớp với một kiểu sai kinh điển nào không (quên chia định thức,
quên chuyển vị, vector riêng của trị riêng khác...).
"""

from __future__ import annotations

import random
import re

import numpy as np
import sympy as sp

from src.core.schema import AnswerType, Item, StepCheck, Subject, Submission, VerificationResult
from src.verify.base import Verifier, parse_answer_list, parse_matrix
from src.verify.equivalence import (
    EquivalenceResult,
    ParseError,
    expr_equal,
    matrix_equal,
    parse_math,
    tidy,
)

# Mã lỗi tầng 2 cho MAI391 (chi tiết trong data/errors/mai391.json).
ERR_SHAPE = "MAI.SHAPE"
ERR_ROWOP = "MAI.ROWOP.INVALID"
ERR_SYS_NOTSOLUTION = "MAI.SYS.NOTSOLUTION"
ERR_SYS_PARTIAL = "MAI.SYS.PARTIAL"
ERR_SYS_INCONSISTENT = "MAI.SYS.INCONSISTENT"
ERR_SYS_FALSE_NOSOL = "MAI.SYS.FALSENOSOL"
ERR_DET_SIGN = "MAI.DET.SIGN"
ERR_DET_SCALE = "MAI.DET.SCALE"
ERR_INV_NODET = "MAI.INV.NODET"
ERR_INV_TRANSPOSE = "MAI.INV.TRANSPOSE"
ERR_INV_NOSIGN = "MAI.INV.NOSIGN"
ERR_INV_SINGULAR = "MAI.INV.SINGULAR"
ERR_INV_FALSE_SINGULAR = "MAI.INV.FALSESINGULAR"
ERR_EIG_ZEROVEC = "MAI.EIG.ZEROVEC"
ERR_EIG_NOTEIGEN = "MAI.EIG.NOTEIGEN"
ERR_EIG_WRONGVALUE = "MAI.EIG.WRONGVALUE"
ERR_EIG_NOTVALUE = "MAI.EIG.NOTVALUE"
ERR_EIG_MISSING = "MAI.EIG.MISSING"
ERR_ODE_NOTSOLUTION = "MAI.ODE.NOTSOLUTION"
ERR_ODE_INCOMPLETE = "MAI.ODE.INCOMPLETE"
ERR_ODE_NOHOMO = "MAI.ODE.NOHOMO"
ERR_ODE_IC = "MAI.ODE.IC"
ERR_ODE_IC_UNSOLVED = "MAI.ODE.IC.UNSOLVED"

NO_SOLUTION = {"vô nghiệm", "vo nghiem", "hệ vô nghiệm", "he vo nghiem", "no solution", "∅", "{}", "none"}
NOT_INVERTIBLE = {
    "không khả nghịch", "khong kha nghich", "không tồn tại", "khong ton tai",
    "suy biến", "suy bien", "singular", "not invertible", "none",
}

_LEADING_FUNCTION = re.compile(r"^\s*[A-Za-z]\s*(\(\s*[A-Za-z]\s*\))?\s*=\s*")


def _words(text: str) -> str:
    return text.strip().lower().rstrip(".")


def _is_zero(expr) -> bool:
    return expr_equal(sp.sympify(expr), sp.Integer(0)).equal


def _is_zero_vector(vector: sp.Matrix) -> bool:
    return all(_is_zero(entry) for entry in vector)


def _ok(detail: str, confidence: float = 1.0) -> EquivalenceResult:
    return EquivalenceResult(True, "symbolic", confidence, detail)


def _wrong(detail: str, confidence: float = 1.0) -> EquivalenceResult:
    return EquivalenceResult(False, "symbolic", confidence, detail)


def parse_trusted(text: str, variable: sp.Symbol, function_name: str = "y") -> sp.Expr:
    """Đọc biểu thức ODE từ NGÂN HÀNG ĐỀ.

    Dùng ``sympify`` được vì đây là dữ liệu do ta viết, không phải đầu vào của
    người dùng. Bài làm của sinh viên thì luôn đi qua ``parse_math`` có danh
    sách trắng.
    """
    return sp.sympify(text, locals={function_name: sp.Function(function_name), str(variable): variable})


class LinalgODEVerifier(Verifier):
    """Chấm bài MAI391."""

    subject = Subject.MAI391
    name = "linalg_ode"
    domain = "positive"

    def verify(self, item: Item, submission: Submission) -> VerificationResult:
        result = VerificationResult(item_id=item.item_id, is_correct=False, verifier_used=self.name)

        checks = self.check_steps(item, submission.steps) if submission.steps else []
        result.step_results = checks
        result.first_wrong_step = self.first_wrong(checks)
        if result.first_wrong_step is not None and any(c.method == "row_equivalence" for c in checks):
            result.candidate_error_codes.append(ERR_ROWOP)

        if submission.final_answer is None:
            result.notes.append("Chưa nộp đáp án cuối, chỉ kiểm tra các bước")
            result.confidence = 0.5
            return result

        try:
            check, codes = self._check(item, submission.final_answer)
        except ParseError as exc:
            # Lỗi nhập liệu KHÔNG phải lỗi toán học: không kết luận đúng/sai.
            result.final_answer_correct = None
            result.notes.extend([str(exc), "Cần sinh viên nhập lại đáp án"])
            return result

        result.final_answer_correct = check.equal
        result.confidence = check.confidence
        result.notes.append(check.detail)
        result.candidate_error_codes.extend(codes)

        result.is_correct = check.equal and result.first_wrong_step is None
        if check.equal and result.first_wrong_step is not None:
            result.notes.append(
                f"Đáp án cuối đúng nhưng bước {result.first_wrong_step} không hợp lệ — có thể sai bù trừ"
            )
        return result

    # ------------------------------------------------------------------

    def _check(self, item: Item, answer: str) -> tuple[EquivalenceResult, list[str]]:
        if not answer.strip():
            return _wrong("Chưa có đáp án"), []

        kind = item.answer_type
        task = item.meta.get("task")

        if kind is AnswerType.LINEAR_SYSTEM:
            return self._check_system(item, answer)
        if kind is AnswerType.EIGENVECTOR:
            return self._check_eigenvector(item, answer)
        if kind is AnswerType.ODE_SOLUTION:
            return self._check_ode(item, answer)
        if task == "inverse":
            return self._check_inverse(item, answer)

        check = self._dispatch_answer(item, answer)
        codes: list[str] = []
        if not check.equal:
            if task == "determinant":
                codes = self._diagnose_determinant(item, answer)
            elif task == "eigenvalues":
                codes = self._diagnose_eigenvalues(item, answer)
        return check, codes

    # ------------------------------------------------------------------
    # Hệ phương trình tuyến tính
    # ------------------------------------------------------------------

    def _check_system(self, item: Item, answer: str) -> tuple[EquivalenceResult, list[str]]:
        A = sp.Matrix(item.meta["A"])
        b = sp.Matrix(item.meta["b"])
        rank = A.rank()

        # Tính tính tương thích từ chính ma trận, không tin vào nhãn trong đề:
        # định lý Kronecker–Capelli — có nghiệm khi và chỉ khi rank(A) = rank(A|b).
        consistent = rank == A.row_join(b).rank()
        claims_no_solution = _words(answer) in NO_SOLUTION

        if not consistent:
            if claims_no_solution:
                return _ok("Hệ vô nghiệm vì rank(A) < rank(A|b)"), []
            return _wrong("Hệ này vô nghiệm (rank(A) < rank(A|b)) nhưng bài làm đưa ra nghiệm"), [ERR_SYS_INCONSISTENT]
        if claims_no_solution:
            return _wrong("Hệ có nghiệm (rank(A) = rank(A|b)) nhưng bài làm kết luận vô nghiệm"), [ERR_SYS_FALSE_NOSOL]

        x = parse_matrix(answer)
        if x.shape != (A.cols, 1):
            return _wrong(f"Hệ có {A.cols} ẩn nhưng đáp án có dạng {x.shape}"), [ERR_SHAPE]

        residual = A * x - b
        failing = [i for i, entry in enumerate(residual) if not _is_zero(entry)]
        if failing:
            return _wrong(f"Thế ngược vào hệ: phương trình thứ {failing[0] + 1} không thoả"), [ERR_SYS_NOTSOLUTION]

        # Thoả hệ rồi — nhưng với hệ vô số nghiệm, một nghiệm riêng lẻ là chưa đủ.
        # Đếm số bậc tự do THẬT bằng hạng Jacobian theo các tham số, chứ không
        # đếm số ký hiệu: [s + t, 0, 1] có hai ký hiệu nhưng chỉ một bậc tự do.
        expected_freedom = A.cols - rank
        parameters = sorted(x.free_symbols, key=str)
        freedom = x.jacobian(parameters).rank() if parameters else 0

        if freedom < expected_freedom:
            return _wrong(
                f"Mới là một phần họ nghiệm: hệ có vô số nghiệm phụ thuộc {expected_freedom} "
                f"tham số, bài làm chỉ có {freedom}"
            ), [ERR_SYS_PARTIAL]

        if expected_freedom == 0:
            return _ok("Thế ngược thoả mọi phương trình, hệ có nghiệm duy nhất"), []
        return _ok(f"Thoả hệ với mọi giá trị tham số, đủ {expected_freedom} bậc tự do"), []

    # ------------------------------------------------------------------
    # Trị riêng, vector riêng
    # ------------------------------------------------------------------

    def _check_eigenvector(self, item: Item, answer: str) -> tuple[EquivalenceResult, list[str]]:
        A = sp.Matrix(item.meta["matrix"])
        eigenvalue = sp.sympify(item.meta["eigenvalue"])
        v = parse_matrix(answer)

        if v.shape != (A.cols, 1):
            return _wrong(f"Vector riêng phải có {A.cols} thành phần, bài làm có dạng {v.shape}"), [ERR_SHAPE]
        if _is_zero_vector(v):
            return _wrong("Vector 0 không bao giờ là vector riêng, theo định nghĩa"), [ERR_EIG_ZEROVEC]
        if _is_zero_vector(A * v - eigenvalue * v):
            return _ok(f"A·v = {eigenvalue}·v và v ≠ 0"), []

        # Sai — nhưng có thể là vector riêng của MỘT TRỊ RIÊNG KHÁC. Chẩn đoán
        # này có giá trị sư phạm lớn: sinh viên tính đúng, chỉ ghép nhầm cặp.
        for other in A.eigenvals():
            if other != eigenvalue and _is_zero_vector(A * v - other * v):
                return _wrong(
                    f"Đây là vector riêng ứng với λ = {other}, không phải λ = {eigenvalue}"
                ), [ERR_EIG_WRONGVALUE]
        return _wrong(f"A·v ≠ {eigenvalue}·v"), [ERR_EIG_NOTEIGEN]

    def _diagnose_eigenvalues(self, item: Item, answer: str) -> list[str]:
        A = sp.Matrix(item.meta["matrix"])
        lam = sp.Symbol("lambda")
        characteristic = (A - lam * sp.eye(A.rows)).det()
        true_values = set(A.eigenvals())

        try:
            given = [parse_math(part) for part in parse_answer_list(answer)]
        except ParseError:
            return []

        if any(not _is_zero(characteristic.subs(lam, value)) for value in given):
            return [ERR_EIG_NOTVALUE]
        if len(set(given)) < len(true_values):
            return [ERR_EIG_MISSING]
        return []

    # ------------------------------------------------------------------
    # Định thức, nghịch đảo
    # ------------------------------------------------------------------

    def _diagnose_determinant(self, item: Item, answer: str) -> list[str]:
        """Lệch dấu: đổi chỗ hai hàng mà quên đổi dấu. Lệch k lần: nhân một hàng với k mà quên chia."""
        true_value = sp.Matrix(item.meta["matrix"]).det()
        if true_value == 0:
            return []
        try:
            given = parse_math(answer)
        except ParseError:
            return []
        if given.free_symbols:
            return []

        ratio = sp.nsimplify(given / true_value)
        if ratio == -1:
            return [ERR_DET_SIGN]
        # Chỉ quy về "nhân hàng với k" khi tỉ số là số nguyên hoặc nghịch đảo số
        # nguyên nhỏ. Một tỉ số tuỳ ý như 7/3 thì không có ý nghĩa gì, gán mã lỗi
        # cho nó là bịa chẩn đoán.
        if ratio.is_Rational and ratio not in (0, 1) and (ratio.p in (1, -1) or ratio.q == 1) and abs(ratio) <= 10:
            return [ERR_DET_SCALE]
        return []

    def _check_inverse(self, item: Item, answer: str) -> tuple[EquivalenceResult, list[str]]:
        A = sp.Matrix(item.meta["matrix"])
        determinant = A.det()
        claims_singular = _words(answer) in NOT_INVERTIBLE

        if determinant == 0:
            if claims_singular:
                return _ok("det(A) = 0 nên A không khả nghịch"), []
            return _wrong("det(A) = 0, ma trận không khả nghịch nên không có nghịch đảo"), [ERR_INV_SINGULAR]
        if claims_singular:
            return _wrong(f"det(A) = {determinant} ≠ 0 nên A khả nghịch"), [ERR_INV_FALSE_SINGULAR]

        B = parse_matrix(answer)
        if B.shape != A.shape:
            return _wrong(f"Nghịch đảo phải có kích thước {A.shape}, bài làm có {B.shape}"), [ERR_SHAPE]

        if _is_zero_vector((A * B - sp.eye(A.rows)).reshape(A.rows * A.cols, 1)):
            return _ok("A·B = I"), []

        inverse = A.inv()
        if matrix_equal(B, determinant * inverse).equal:
            return _wrong("Đây là ma trận phụ hợp — còn thiếu bước chia cho det(A)"), [ERR_INV_NODET]
        if matrix_equal(B, inverse.T).equal:
            return _wrong("Đây là chuyển vị của nghịch đảo — ma trận phụ hợp phải được chuyển vị"), [ERR_INV_TRANSPOSE]
        if A.shape == (2, 2):
            a, b, c, d = A
            if matrix_equal(B, sp.Matrix([[d, b], [c, a]]) / determinant).equal:
                return _wrong("Đổi chỗ đường chéo chính đúng rồi, nhưng quên đổi dấu hai phần tử còn lại"), [ERR_INV_NOSIGN]
        return _wrong("A·B ≠ I"), []

    # ------------------------------------------------------------------
    # Phương trình vi phân
    # ------------------------------------------------------------------

    def _check_ode(self, item: Item, answer: str) -> tuple[EquivalenceResult, list[str]]:
        x = sp.Symbol(item.variable)
        function_name = item.meta.get("func", "y")
        y = sp.Function(function_name)

        lhs = parse_trusted(item.meta["ode"], x, function_name)
        rhs = parse_trusted(item.meta.get("rhs", "0"), x, function_name)

        # Sinh viên hay viết "y = ...", đôi khi "y(x) = ...".
        candidate = parse_math(_LEADING_FUNCTION.sub("", answer, count=1))

        residual = (lhs - rhs).subs(y(x), candidate).doit()
        if not _is_zero(residual):
            return _wrong(f"Thế vào phương trình không ra 0 (còn dư {tidy(residual)})"), [ERR_ODE_NOTSOLUTION]

        constants = sorted(candidate.free_symbols - {x}, key=str)
        conditions = item.meta.get("ics") or []

        if conditions:
            if constants:
                return _wrong(
                    "Nghiệm tổng quát đúng, nhưng chưa dùng điều kiện đầu để tìm hằng số"
                ), [ERR_ODE_IC_UNSOLVED]
            for condition in conditions:
                order = int(condition.get("derivative", 0))
                at = parse_trusted(str(condition["at"]), x, function_name)
                expected = parse_trusted(str(condition["value"]), x, function_name)
                actual = sp.diff(candidate, x, order).subs(x, at)
                if not expr_equal(sp.sympify(actual), expected).equal:
                    label = function_name + "'" * order
                    return _wrong(
                        f"Thoả phương trình nhưng {label}({at}) = {tidy(actual)}, đề yêu cầu {expected}"
                    ), [ERR_ODE_IC]
            return _ok("Thoả phương trình và mọi điều kiện đầu"), []

        order = int(item.meta["order"])
        independent = self.independent_constants(candidate, constants, x)
        if independent < order:
            is_homogeneous = _is_zero(rhs)
            if not is_homogeneous and independent == 0:
                return _wrong(
                    "Đây mới là một nghiệm riêng — còn thiếu nghiệm tổng quát của phương trình thuần nhất"
                ), [ERR_ODE_NOHOMO]
            return _wrong(
                f"Phương trình cấp {order} cần {order} hằng số độc lập, bài làm mới có {independent}"
            ), [ERR_ODE_INCOMPLETE]
        return _ok(f"Thoả phương trình với {independent} hằng số độc lập — đúng nghiệm tổng quát"), []

    @staticmethod
    def independent_constants(candidate: sp.Expr, constants: list[sp.Symbol], x: sp.Symbol) -> int:
        """Số hằng số ĐỘC LẬP thật sự trong nghiệm, không chỉ số ký hiệu.

        Với phương trình có nghiệm kép như y'' − 2y' + y = 0, sinh viên hay viết
        ``C1·eˣ + C2·eˣ``: có hai ký hiệu nhưng chúng gộp được thành một, nên đó
        KHÔNG phải nghiệm tổng quát (đúng phải là ``(C1 + C2·x)·eˣ``). Đếm ký hiệu
        sẽ chấm nhầm bài này là đúng.

        Cách đếm: đạo hàm riêng của nghiệm theo từng hằng số là các hàm của x;
        số hằng số độc lập chính là số hàm độc lập tuyến tính trong số đó. Ước
        lượng bằng hạng của ma trận các giá trị tại nhiều điểm x ngẫu nhiên.
        """
        if not constants:
            return 0

        gradients = [sp.diff(candidate, c) for c in constants]
        rng = random.Random(7)
        rows: list[list[complex]] = []
        for _ in range(len(constants) + 3):
            point = {x: rng.uniform(0.2, 2.2)}
            point.update({c: rng.uniform(0.5, 1.5) for c in constants})
            try:
                rows.append([complex(g.evalf(subs=point)) for g in gradients])
            except (TypeError, ValueError):
                continue

        if not rows:
            return 0
        return int(np.linalg.matrix_rank(np.array(rows)))

    # ------------------------------------------------------------------
    # Các bước khử Gauss
    # ------------------------------------------------------------------

    def check_steps(self, item: Item, steps: list[str]) -> list[StepCheck]:
        """Nếu mọi bước đều là ma trận thì kiểm tra tương đương hàng.

        Hai ma trận tương đương hàng khi và chỉ khi có cùng dạng bậc thang rút
        gọn — đây là bất biến CHÍNH XÁC của phép biến đổi sơ cấp theo hàng. Nhờ
        vậy chấp nhận mọi thứ tự biến đổi, kể cả gộp nhiều phép vào một bước,
        mà vẫn bắt được đúng bước làm sai.
        """
        try:
            matrices = [parse_matrix(step) for step in steps]
        except ParseError:
            return super().check_steps(item, steps)

        checks: list[StepCheck] = []
        for index, matrix in enumerate(matrices, start=1):
            if index == 1:
                checks.append(StepCheck(step=1, ok=True, method="baseline", confidence=1.0,
                                        reason="Ma trận ban đầu, lấy làm mốc"))
                continue
            checks.append(self._row_equivalent(matrices[index - 2], matrix, index))
        return checks

    @staticmethod
    def _nonzero_rref_rows(matrix: sp.Matrix) -> sp.Matrix:
        reduced = matrix.rref()[0]
        rows = [reduced.row(i) for i in range(reduced.rows) if any(e != 0 for e in reduced.row(i))]
        return sp.Matrix.vstack(*rows) if rows else sp.zeros(0, matrix.cols)

    def _row_equivalent(self, previous: sp.Matrix, current: sp.Matrix, index: int) -> StepCheck:
        if previous.cols != current.cols:
            return StepCheck(step=index, ok=False, method="row_equivalence", confidence=1.0,
                             reason=f"Số cột đổi từ {previous.cols} sang {current.cols} — phép biến đổi hàng không làm đổi số cột")

        left, right = self._nonzero_rref_rows(previous), self._nonzero_rref_rows(current)
        if left.shape == right.shape and matrix_equal(left, right).equal:
            return StepCheck(step=index, ok=True, method="row_equivalence", confidence=1.0,
                             reason="Tương đương hàng với bước trước (cùng dạng bậc thang rút gọn)")

        if left.rows != right.rows:
            reason = f"Hạng đổi từ {left.rows} sang {right.rows} — đây không phải phép biến đổi sơ cấp"
        else:
            reason = "Không tương đương hàng với bước trước — có phép biến đổi bị tính sai"
        return StepCheck(step=index, ok=False, method="row_equivalence", confidence=1.0, reason=reason)
