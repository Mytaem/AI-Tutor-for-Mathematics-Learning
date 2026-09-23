"""Bộ chấm Mathematics for Machine Learning — MAI391 (Deisenroth, Faisal, Ong 2020).

Phủ các chương của đề cương MAI391: hình học giải tích (chuẩn, góc, phép chiếu),
phân rã ma trận (vết, chéo hoá, SVD), giải tích vector (gradient, Jacobi, quy
tắc dây chuyền), xác suất (kỳ vọng, phương sai), tối ưu (gradient descent, điểm
dừng), hồi quy tuyến tính (bình phương tối thiểu), PCA và lề SVM. Phần định
thức, trị riêng, vector riêng của chương 4 do ``LinearAlgebraVerifier`` chấm.

Đáp án chuẩn được TÍNH LẠI từ dữ liệu của đề (ma trận, hàm, điểm...), không
đọc từ trường ``answer`` — nên một đáp án chuẩn gõ nhầm trong ngân hàng đề sẽ
bị test tự verify bắt ngay. Với bài có nhiều đáp án đúng thì kiểm TÍNH CHẤT:

- Bình phương tối thiểu: kiểm phương trình chuẩn ``Xᵀ(Xθ − y) = 0``.
- Điểm dừng: kiểm ``∇f(p) = 0``.
- Thành phần chính: kiểm vector riêng của trị riêng lớn nhất (mọi bội đều đúng).

Mỗi chẩn đoán lỗi thử xem đáp án sai có khớp ĐÚNG một kiểu sai kinh điển không
(quên căn, nhầm trị riêng với giá trị kỳ dị, đi xuôi chiều gradient...). Không
khớp kiểu nào thì không gán mã — không bịa chẩn đoán.
"""

from __future__ import annotations

import sympy as sp

from src.core.schema import Item
from src.verify.base import Verifier, parse_answer_list, parse_matrix
from src.verify.equivalence import (
    EquivalenceResult,
    expr_equal,
    matrix_equal,
    number_equal,
    parse_math,
    set_equal,
)
from src.verify.linalg import ERR_EIG_WRONGVALUE, ERR_SHAPE, LinearAlgebraVerifier

ERR_NOSQRT = "MAI.GEO.NOSQRT"
ERR_WRONGNORM = "MAI.GEO.WRONGNORM"
ERR_PROJ_NONORM = "MAI.GEO.PROJ_NONORM"
ERR_PROJ_WRONG = "MAI.GEO.PROJ_WRONG"
ERR_TRACE_DET = "MAI.DEC.TRACE_DET"
ERR_TRACE_SUMALL = "MAI.DEC.TRACE_SUMALL"
ERR_NOTDIAG = "MAI.DEC.NOTDIAG"
ERR_WRONGSPECTRUM = "MAI.DEC.WRONGSPECTRUM"
ERR_SVD_EIGEN = "MAI.SVD.EIGEN_INSTEAD"
ERR_SVD_NOSQRT = "MAI.SVD.NOSQRT"
ERR_SWAPPED = "MAI.VC.SWAPPED"
ERR_NOCHAIN = "MAI.VC.NOCHAIN"
ERR_JACOBIAN_T = "MAI.VC.JACOBIAN_TRANSPOSE"
ERR_NOMEAN = "MAI.PROB.NOMEAN"
ERR_STD = "MAI.PROB.STD_INSTEAD"
ERR_GD_SIGN = "MAI.OPT.GD_SIGN"
ERR_GD_NOLR = "MAI.OPT.GD_NOLR"
ERR_NOTSTATIONARY = "MAI.OPT.NOTSTATIONARY"
ERR_NOTLS = "MAI.REG.NOTLS"
ERR_PCA_SMALLEST = "MAI.PCA.SMALLEST"
ERR_PCA_NORATIO = "MAI.PCA.NORATIO"
ERR_SVM_HALF = "MAI.SVM.HALFMARGIN"
ERR_SVM_SQUARED = "MAI.SVM.SQUARED"

MML_TASKS = {
    "norm", "inner_product", "angle_cos", "projection", "trace", "diagonal_form",
    "singular_values", "gradient", "jacobian", "partial", "chain", "expectation",
    "variance", "gd_step", "stationary", "least_squares", "pca_first", "pca_ratio",
    "svm_margin",
}

#: Hàm một biến hay gặp làm "hàm ngoài" của hàm hợp — để nhận ra lỗi quên dây chuyền.
_OUTER_FUNCTIONS = (sp.exp, sp.sin, sp.cos, sp.log)


def _ok(detail: str) -> EquivalenceResult:
    return EquivalenceResult(True, "symbolic", 1.0, detail)


def _wrong(detail: str) -> EquivalenceResult:
    return EquivalenceResult(False, "symbolic", 1.0, detail)


def column(values) -> sp.Matrix:
    return sp.Matrix([sp.sympify(v) for v in values])


def variables(item: Item) -> list[sp.Symbol]:
    return [sp.Symbol(name) for name in item.meta.get("vars", [item.variable])]


def trusted(text: str, item: Item) -> sp.Expr:
    """Đọc biểu thức từ NGÂN HÀNG ĐỀ (dữ liệu của ta, không phải bài làm của sinh viên)."""
    return sp.sympify(text, locals={v.name: v for v in variables(item)})


#: Dung sai số học — CÙNG mức với bài một-con-số (``number_equal``): chấp nhận
#: đáp án thập phân đúng tới khoảng 6 chữ số có nghĩa. Mọi phép kiểm trong file
#: này phải dùng chung một mức, nếu không thì cùng một cách làm tròn sẽ được
#: nhận ở bài này mà bị từ chối ở bài khác.
NUMERIC_TOL = 1e-6


def _close(given: sp.Expr, value: sp.Expr) -> bool:
    return number_equal(given, value, rel_tol=NUMERIC_TOL).equal


def _near_zero(values, scale: sp.Expr) -> bool:
    """Mọi phần tử gần 0 so với độ lớn ``scale`` của bài toán.

    Không so với 0 tuyệt đối: đáp án làm tròn 0.8333333 cho 5/6 để lại phần dư
    cỡ 1e-7 trong phương trình chuẩn — vẫn phải được chấp nhận.
    """
    bound = NUMERIC_TOL * max(1.0, float(abs(sp.N(scale))))
    try:
        return all(abs(complex(sp.N(v))) <= bound for v in values)
    except TypeError:
        # Còn chứa ký hiệu (ví dụ tham số): phải bằng 0 đồng nhất.
        return all(expr_equal(sp.sympify(v), sp.Integer(0)).equal for v in values)


def _same(given: sp.Matrix, reference: sp.Matrix) -> bool:
    return matrix_equal(given, reference, tol=NUMERIC_TOL).equal


class MMLVerifier(Verifier):
    """Chấm các bài Mathematics for Machine Learning."""

    name = "mml"
    domain = "positive"

    def __init__(self) -> None:
        self._linear_algebra = LinearAlgebraVerifier()

    def handles(self, item: Item) -> bool:
        return item.meta.get("task") in MML_TASKS

    def check(self, item: Item, answer: str) -> tuple[EquivalenceResult, list[str]]:
        if not answer.strip():
            return _wrong("Chưa có đáp án"), []
        handler = getattr(self, f"_check_{item.meta['task']}", None)
        if handler is not None:
            return handler(item, answer)
        return self._dispatch_answer(item, answer), []

    # ------------------------------------------------------------------
    # Tiện ích cho bài ra một con số
    # ------------------------------------------------------------------

    def _numeric(
        self, answer: str, reference: sp.Expr, alternatives: list[tuple[sp.Expr, str]], label: str
    ) -> tuple[EquivalenceResult, list[str]]:
        """So một đáp án số với giá trị đúng; sai thì thử khớp với từng kiểu sai đã biết."""
        given = parse_math(answer)
        if given.free_symbols:
            return _wrong(f"{label} phải là một con số, bài làm còn chứa biến"), []
        if _close(given, reference):
            return _ok(f"{label} = {reference}"), []
        for value, code in alternatives:
            if not _close(value, reference) and _close(given, value):
                return _wrong(f"{label} đúng là {reference}; giá trị {given} ứng với một lỗi hay gặp"), [code]
        return _wrong(f"{label} đúng là {reference}, bài làm ra {given}"), []

    # ------------------------------------------------------------------
    # Chương 3 — hình học giải tích
    # ------------------------------------------------------------------

    @staticmethod
    def _norm(vector: sp.Matrix, order: int) -> sp.Expr:
        if order == 1:
            return sum(abs(e) for e in vector)
        return sp.sqrt(sum(e**2 for e in vector))

    def _check_norm(self, item: Item, answer: str):
        vector, order = column(item.meta["vector"]), int(item.meta.get("ord", 2))
        reference = self._norm(vector, order)
        alternatives = [(self._norm(vector, 2 if order == 1 else 1), ERR_WRONGNORM)]
        if order == 2:
            alternatives.insert(0, (reference**2, ERR_NOSQRT))
        return self._numeric(answer, reference, alternatives, f"‖x‖{order}")

    def _check_inner_product(self, item: Item, answer: str):
        u, v = column(item.meta["u"]), column(item.meta["v"])
        return self._numeric(answer, u.dot(v), [], "⟨u, v⟩")

    def _check_angle_cos(self, item: Item, answer: str):
        u, v = column(item.meta["u"]), column(item.meta["v"])
        reference = sp.nsimplify(u.dot(v) / (sp.sqrt(u.dot(u)) * sp.sqrt(v.dot(v))))
        return self._numeric(answer, reference, [], "cos θ")

    def _check_projection(self, item: Item, answer: str):
        x, b = column(item.meta["x"]), column(item.meta["b"])
        given = parse_matrix(answer)
        if given.shape != x.shape:
            return _wrong(f"Hình chiếu phải có {x.rows} thành phần, bài làm có dạng {given.shape}"), [ERR_SHAPE]
        # Hình chiếu lên một đường thẳng là DUY NHẤT, nên so trực tiếp được.
        reference = (b.dot(x) / b.dot(b)) * b
        if _same(given, reference):
            return _ok("p = (bᵀx / bᵀb)·b: cùng phương với b và x − p vuông góc với b"), []
        if b.dot(b) != 1 and _same(given, b.dot(x) * b):
            return _wrong("Đây là (bᵀx)·b — còn thiếu phép chia cho bᵀb vì b không phải vector đơn vị"), [ERR_PROJ_NONORM]
        return _wrong("Vector này không phải hình chiếu trực giao của x lên span{b}"), [ERR_PROJ_WRONG]

    # ------------------------------------------------------------------
    # Chương 4 — phân rã ma trận
    # ------------------------------------------------------------------

    def _check_trace(self, item: Item, answer: str):
        matrix = sp.Matrix(item.meta["matrix"])
        alternatives = [(matrix.det(), ERR_TRACE_DET), (sum(matrix), ERR_TRACE_SUMALL)]
        return self._numeric(answer, matrix.trace(), alternatives, "tr(A)")

    def _check_diagonal_form(self, item: Item, answer: str):
        matrix = sp.Matrix(item.meta["matrix"])
        given = parse_matrix(answer)
        if given.shape != matrix.shape:
            return _wrong(f"D phải có kích thước {matrix.shape}, bài làm có {given.shape}"), [ERR_SHAPE]

        off_diagonal = [given[i, j] for i in range(given.rows) for j in range(given.cols) if i != j]
        if any(not expr_equal(sp.sympify(e), sp.Integer(0)).equal for e in off_diagonal):
            return _wrong("D phải là ma trận chéo — mọi phần tử ngoài đường chéo bằng 0"), [ERR_NOTDIAG]

        # Thứ tự trị riêng trên đường chéo tuỳ ý (tuỳ cách sắp cột của P), nên so như TẬP có bội.
        spectrum = [value for value, count in matrix.eigenvals().items() for _ in range(count)]
        diagonal = [given[i, i] for i in range(given.rows)]
        if set_equal(diagonal, spectrum).equal:
            return _ok("D chéo và đường chéo đúng là các trị riêng của A (thứ tự tuỳ ý)"), []
        return _wrong(f"Đường chéo của D phải là các trị riêng {spectrum}"), [ERR_WRONGSPECTRUM]

    def _check_singular_values(self, item: Item, answer: str):
        matrix = sp.Matrix(item.meta["matrix"])
        given = parse_answer_list(answer)
        reference = matrix.singular_values()
        if set_equal(given, reference).equal:
            return _ok(f"Giá trị kỳ dị = căn trị riêng của AᵀA = {reference}"), []

        eigen_a = [v for v, n in matrix.eigenvals().items() for _ in range(n)]
        eigen_ata = [v for v, n in (matrix.T * matrix).eigenvals().items() for _ in range(n)]
        if not set_equal(eigen_a, reference).equal and set_equal(given, eigen_a).equal:
            return _wrong("Đây là trị riêng của A, không phải giá trị kỳ dị"), [ERR_SVD_EIGEN]
        if set_equal(given, eigen_ata).equal:
            return _wrong("Đây là trị riêng của AᵀA — giá trị kỳ dị là căn bậc hai của chúng"), [ERR_SVD_NOSQRT]
        return _wrong(f"Giá trị kỳ dị đúng là {reference}"), []

    # ------------------------------------------------------------------
    # Chương 5 — giải tích vector
    # ------------------------------------------------------------------

    def _check_gradient(self, item: Item, answer: str):
        f, names = trusted(item.meta["f"], item), variables(item)
        reference = sp.Matrix([sp.diff(f, v) for v in names])
        given = parse_matrix(answer)
        if given.shape != reference.shape:
            return _wrong(f"Gradient có {len(names)} thành phần, bài làm có dạng {given.shape}"), [ERR_SHAPE]
        if _same(given, reference):
            return _ok("Mỗi thành phần khớp đạo hàm riêng theo đúng biến"), []
        if len(names) > 1 and matrix_equal(given, sp.Matrix(list(reversed(list(reference))))).equal:
            return _wrong("Các đạo hàm riêng đúng nhưng xếp ngược thứ tự biến"), [ERR_SWAPPED]

        # f = F(u) với u nhiều biến: quên dây chuyền nghĩa là mọi thành phần đều là F'(u).
        if f.func in _OUTER_FUNCTIONS and len(f.args) == 1:
            t = sp.Symbol("_t")
            outer = sp.diff(f.func(t), t).subs(t, f.args[0])
            if matrix_equal(given, sp.Matrix([outer] * len(names))).equal:
                return _wrong("Mới lấy đạo hàm hàm ngoài — còn thiếu nhân đạo hàm riêng của hàm trong"), [ERR_NOCHAIN]
        return _wrong("Gradient chưa đúng"), []

    def _check_jacobian(self, item: Item, answer: str):
        names = variables(item)
        reference = sp.Matrix([trusted(c, item) for c in item.meta["F"]]).jacobian(names)
        given = parse_matrix(answer)
        if given.shape == reference.shape and _same(given, reference):
            return _ok("Hàng i là gradient của thành phần thứ i"), []
        if reference != reference.T and given.shape == reference.T.shape and matrix_equal(given, reference.T).equal:
            return _wrong("Đây là chuyển vị của ma trận Jacobi — mỗi HÀNG phải ứng với một thành phần của F"), [ERR_JACOBIAN_T]
        if given.shape != reference.shape:
            return _wrong(f"Ma trận Jacobi có kích thước {reference.shape}, bài làm có {given.shape}"), [ERR_SHAPE]
        return _wrong("Ma trận Jacobi chưa đúng"), []

    # ------------------------------------------------------------------
    # Chương 6 — xác suất
    # ------------------------------------------------------------------

    @staticmethod
    def _moments(item: Item) -> tuple[sp.Expr, sp.Expr]:
        values = [sp.sympify(v) for v in item.meta["values"]]
        probabilities = [sp.sympify(p) for p in item.meta["probs"]]
        mean = sum(v * p for v, p in zip(values, probabilities))
        second = sum(v**2 * p for v, p in zip(values, probabilities))
        return mean, second

    def _check_expectation(self, item: Item, answer: str):
        mean, _ = self._moments(item)
        return self._numeric(answer, mean, [], "E[X]")

    def _check_variance(self, item: Item, answer: str):
        mean, second = self._moments(item)
        variance = second - mean**2
        return self._numeric(answer, variance, [(second, ERR_NOMEAN), (sp.sqrt(variance), ERR_STD)], "Var(X)")

    # ------------------------------------------------------------------
    # Chương 7 — tối ưu
    # ------------------------------------------------------------------

    def _gradient_at(self, item: Item, point: sp.Matrix) -> sp.Matrix:
        f, names = trusted(item.meta["f"], item), variables(item)
        substitution = dict(zip(names, point))
        return sp.Matrix([sp.diff(f, v).subs(substitution) for v in names])

    def _check_gd_step(self, item: Item, answer: str):
        x0, rate = column(item.meta["x0"]), sp.sympify(item.meta["lr"])
        gradient = self._gradient_at(item, x0)
        given = parse_matrix(answer)
        if given.shape != x0.shape:
            return _wrong(f"x₁ phải có {x0.rows} thành phần, bài làm có dạng {given.shape}"), [ERR_SHAPE]
        if _same(given, x0 - rate * gradient):
            return _ok("x₁ = x₀ − η∇f(x₀)"), []
        if _same(given, x0 + rate * gradient):
            return _wrong("Đây là x₀ + η∇f(x₀) — bước này làm hàm TĂNG, phải đi ngược chiều gradient"), [ERR_GD_SIGN]
        if rate != 1 and _same(given, x0 - gradient):
            return _wrong("Đây là x₀ − ∇f(x₀) — còn thiếu nhân tốc độ học η"), [ERR_GD_NOLR]
        return _wrong(f"x₁ đúng là {list(x0 - rate * gradient)}"), []

    def _check_stationary(self, item: Item, answer: str):
        given = parse_matrix(answer)
        if given.rows != len(variables(item)) or given.cols != 1:
            return _wrong(f"Điểm dừng có {len(variables(item))} toạ độ, bài làm có dạng {given.shape}"), [ERR_SHAPE]
        gradient = self._gradient_at(item, given)
        if _near_zero(gradient, max((abs(c) for c in given), default=1)):
            return _ok("∇f tại điểm này bằng vector 0"), []
        return _wrong(f"∇f tại điểm này là {list(gradient)}, khác 0"), [ERR_NOTSTATIONARY]

    # ------------------------------------------------------------------
    # Chương 9 — hồi quy tuyến tính
    # ------------------------------------------------------------------

    def _check_least_squares(self, item: Item, answer: str):
        X, y = sp.Matrix(item.meta["X"]), column(item.meta["y"])
        theta = parse_matrix(answer)
        if theta.shape != (X.cols, 1):
            return _wrong(f"θ có {X.cols} thành phần, bài làm có dạng {theta.shape}"), [ERR_SHAPE]
        # Kiểm phương trình chuẩn thay vì so với một nghiệm: đúng cả khi XᵀX suy
        # biến (vô số nghiệm bình phương tối thiểu), và không cần tin trường answer.
        normal = X.T * (X * theta - y)
        if _near_zero(normal, (X.T * y).norm()):
            return _ok("Thoả phương trình chuẩn Xᵀ(Xθ − y) = 0"), []
        return _wrong("θ không thoả phương trình chuẩn XᵀXθ = Xᵀy"), [ERR_NOTLS]

    # ------------------------------------------------------------------
    # Chương 10 — PCA; chương 12 — SVM
    # ------------------------------------------------------------------

    def _check_pca_first(self, item: Item, answer: str):
        result, codes = self._linear_algebra.check(item, answer)
        if codes == [ERR_EIG_WRONGVALUE]:
            # Vector riêng của trị riêng khác — với PCA, lỗi kinh điển là chọn trị riêng NHỎ nhất.
            matrix = sp.Matrix(item.meta["matrix"])
            vector = parse_matrix(answer)
            smallest = min(matrix.eigenvals(), key=lambda v: sp.re(v))
            if (matrix * vector - smallest * vector).is_zero_matrix:
                return _wrong("Đây là hướng có phương sai NHỎ nhất; thành phần chính thứ nhất ứng với trị riêng lớn nhất"), [ERR_PCA_SMALLEST]
        return result, codes

    def _check_pca_ratio(self, item: Item, answer: str):
        matrix = sp.Matrix(item.meta["matrix"])
        k = int(item.meta.get("k", 1))
        spectrum = sorted((v for v, n in matrix.eigenvals().items() for _ in range(n)), key=lambda v: -sp.re(v))
        explained = sum(spectrum[:k])
        return self._numeric(answer, explained / sum(spectrum), [(explained, ERR_PCA_NORATIO)], "tỉ lệ phương sai")

    def _check_svm_margin(self, item: Item, answer: str):
        norm = sp.sqrt(sum(e**2 for e in column(item.meta["w"])))
        alternatives = [(1 / norm, ERR_SVM_HALF), (2 / norm**2, ERR_SVM_SQUARED)]
        return self._numeric(answer, 2 / norm, alternatives, "độ rộng lề 2/‖w‖")
