"""Bộ sinh lỗi có nhãn cho Mathematics for Machine Learning (MAI391).

Mỗi hàm tái hiện đúng MỘT kiểu sai kinh điển, tính từ dữ liệu của đề. Hàng rào
``is_genuinely_wrong`` ở tầng khung vẫn chặn mọi mẫu tình cờ lại đúng.

Cùng cảnh báo như ``linear_algebra_errors``: bộ sinh và phần chẩn đoán của
``MMLVerifier`` viết từ cùng một bảng mã lỗi, nên tỉ lệ gán đúng mã trên dữ liệu
tổng hợp mang tính vòng quanh. Con số trung thực phải đo trên bài làm sai thật.
"""

from __future__ import annotations

import sympy as sp

from src.core.schema import Item
from src.data_gen.error_injector import register
from src.data_gen.linear_algebra_errors import fmt
from src.verify.mml import MMLVerifier, column, trusted, variables

_norm = MMLVerifier._norm
_moments = MMLVerifier._moments


def _task(item: Item) -> str | None:
    return item.meta.get("task")


# --------------------------------------------------------------------------
# Hình học giải tích
# --------------------------------------------------------------------------

@register("MAI.GEO.NOSQRT")
def _norm_no_sqrt(item: Item) -> str | None:
    if _task(item) != "norm" or int(item.meta.get("ord", 2)) != 2:
        return None
    return sp.sstr(_norm(column(item.meta["vector"]), 2) ** 2)


@register("MAI.GEO.WRONGNORM")
def _norm_wrong_order(item: Item) -> str | None:
    if _task(item) != "norm":
        return None
    order = int(item.meta.get("ord", 2))
    return sp.sstr(_norm(column(item.meta["vector"]), 1 if order == 2 else 2))


@register("MAI.GEO.PROJ_NONORM")
def _projection_no_norm(item: Item) -> str | None:
    if _task(item) != "projection":
        return None
    x, b = column(item.meta["x"]), column(item.meta["b"])
    return fmt(b.dot(x) * b) if b.dot(b) != 1 else None


@register("MAI.GEO.PROJ_WRONG")
def _projection_is_x(item: Item) -> str | None:
    """Đưa luôn x làm hình chiếu — không chiếu gì cả."""
    return fmt(column(item.meta["x"])) if _task(item) == "projection" else None


# --------------------------------------------------------------------------
# Phân rã ma trận
# --------------------------------------------------------------------------

@register("MAI.DEC.TRACE_DET")
def _trace_as_det(item: Item) -> str | None:
    return sp.sstr(sp.Matrix(item.meta["matrix"]).det()) if _task(item) == "trace" else None


@register("MAI.DEC.TRACE_SUMALL")
def _trace_sum_all(item: Item) -> str | None:
    return sp.sstr(sum(sp.Matrix(item.meta["matrix"]))) if _task(item) == "trace" else None


@register("MAI.DEC.NOTDIAG")
def _diagonal_not_diagonal(item: Item) -> str | None:
    """Đưa lại chính A — nhầm D với ma trận ban đầu."""
    if _task(item) != "diagonal_form":
        return None
    matrix = sp.Matrix(item.meta["matrix"])
    return fmt(matrix) if not matrix.is_diagonal() else None


@register("MAI.DEC.WRONGSPECTRUM")
def _diagonal_wrong_spectrum(item: Item) -> str | None:
    if _task(item) != "diagonal_form":
        return None
    spectrum = [v for v, n in sp.Matrix(item.meta["matrix"]).eigenvals().items() for _ in range(n)]
    spectrum[0] += 1
    return fmt(sp.diag(*spectrum))


@register("MAI.SVD.EIGEN_INSTEAD")
def _svd_eigenvalues(item: Item) -> str | None:
    if _task(item) != "singular_values":
        return None
    values = [v for v, n in sp.Matrix(item.meta["matrix"]).eigenvals().items() for _ in range(n)]
    return ", ".join(sp.sstr(v) for v in values)


@register("MAI.SVD.NOSQRT")
def _svd_no_sqrt(item: Item) -> str | None:
    if _task(item) != "singular_values":
        return None
    matrix = sp.Matrix(item.meta["matrix"])
    values = [v for v, n in (matrix.T * matrix).eigenvals().items() for _ in range(n)]
    return ", ".join(sp.sstr(v) for v in values)


# --------------------------------------------------------------------------
# Giải tích vector
# --------------------------------------------------------------------------

def _gradient(item: Item) -> sp.Matrix | None:
    if _task(item) != "gradient":
        return None
    f = trusted(item.meta["f"], item)
    return sp.Matrix([sp.diff(f, v) for v in variables(item)])


@register("MAI.VC.SWAPPED")
def _gradient_swapped(item: Item) -> str | None:
    gradient = _gradient(item)
    if gradient is None or gradient.rows < 2:
        return None
    return fmt(sp.Matrix(list(reversed(list(gradient)))))


@register("MAI.VC.NOCHAIN")
def _gradient_no_chain(item: Item) -> str | None:
    """f = F(u): chỉ lấy F'(u) cho mọi thành phần, quên nhân ∂u/∂xᵢ."""
    if _task(item) != "gradient":
        return None
    f = trusted(item.meta["f"], item)
    if f.func not in (sp.exp, sp.sin, sp.cos, sp.log) or len(f.args) != 1:
        return None
    t = sp.Symbol("_t")
    outer = sp.diff(f.func(t), t).subs(t, f.args[0])
    return fmt(sp.Matrix([outer] * len(variables(item))))


@register("MAI.VC.JACOBIAN_TRANSPOSE")
def _jacobian_transpose(item: Item) -> str | None:
    if _task(item) != "jacobian":
        return None
    jacobian = sp.Matrix([trusted(c, item) for c in item.meta["F"]]).jacobian(variables(item))
    return fmt(jacobian.T) if jacobian != jacobian.T else None


# --------------------------------------------------------------------------
# Xác suất
# --------------------------------------------------------------------------

@register("MAI.PROB.NOMEAN")
def _variance_no_mean(item: Item) -> str | None:
    return sp.sstr(_moments(item)[1]) if _task(item) == "variance" else None


@register("MAI.PROB.STD_INSTEAD")
def _variance_as_std(item: Item) -> str | None:
    if _task(item) != "variance":
        return None
    mean, second = _moments(item)
    return sp.sstr(sp.sqrt(second - mean**2))


# --------------------------------------------------------------------------
# Tối ưu
# --------------------------------------------------------------------------

def _gd(item: Item):
    if _task(item) != "gd_step":
        return None
    x0, rate = column(item.meta["x0"]), sp.sympify(item.meta["lr"])
    f, names = trusted(item.meta["f"], item), variables(item)
    gradient = sp.Matrix([sp.diff(f, v).subs(dict(zip(names, x0))) for v in names])
    return x0, rate, gradient


@register("MAI.OPT.GD_SIGN")
def _gd_ascent(item: Item) -> str | None:
    found = _gd(item)
    return fmt(found[0] + found[1] * found[2]) if found else None


@register("MAI.OPT.GD_NOLR")
def _gd_no_rate(item: Item) -> str | None:
    found = _gd(item)
    if found is None or found[1] == 1:
        return None
    return fmt(found[0] - found[2])


@register("MAI.OPT.NOTSTATIONARY")
def _stationary_off_by_one(item: Item) -> str | None:
    """Giải sai hệ ∇f = 0: toạ độ đầu lệch 1."""
    if _task(item) != "stationary":
        return None
    f, names = trusted(item.meta["f"], item), variables(item)
    solution = sp.solve([sp.diff(f, v) for v in names], names, dict=True)
    if not solution:
        return None
    point = sp.Matrix([solution[0][v] for v in names])
    point[0] += 1
    return fmt(point)


# --------------------------------------------------------------------------
# Hồi quy tuyến tính, PCA, SVM
# --------------------------------------------------------------------------

@register("MAI.REG.NOTLS")
def _least_squares_interpolate(item: Item) -> str | None:
    """Cho đường thẳng đi qua ĐÚNG hai điểm đầu, bỏ qua các điểm còn lại."""
    if _task(item) != "least_squares":
        return None
    X, y = sp.Matrix(item.meta["X"]), column(item.meta["y"])
    head = X[: X.cols, :]
    if head.det() == 0:
        return None
    return fmt(head.solve(y[: X.cols, :]))


@register("MAI.PCA.SMALLEST")
def _pca_smallest(item: Item) -> str | None:
    if _task(item) != "pca_first":
        return None
    matrix = sp.Matrix(item.meta["matrix"])
    value, _, vectors = min(matrix.eigenvects(), key=lambda entry: sp.re(entry[0]))
    return fmt(vectors[0])


@register("MAI.PCA.NORATIO")
def _pca_no_ratio(item: Item) -> str | None:
    if _task(item) != "pca_ratio":
        return None
    spectrum = sorted((v for v, n in sp.Matrix(item.meta["matrix"]).eigenvals().items() for _ in range(n)),
                      key=lambda v: -sp.re(v))
    return sp.sstr(sum(spectrum[: int(item.meta.get("k", 1))]))


def _w_norm(item: Item) -> sp.Expr | None:
    if _task(item) != "svm_margin":
        return None
    return sp.sqrt(sum(e**2 for e in column(item.meta["w"])))


@register("MAI.SVM.HALFMARGIN")
def _svm_half(item: Item) -> str | None:
    norm = _w_norm(item)
    return sp.sstr(1 / norm) if norm is not None else None


@register("MAI.SVM.SQUARED")
def _svm_squared(item: Item) -> str | None:
    norm = _w_norm(item)
    return sp.sstr(2 / norm**2) if norm is not None else None
