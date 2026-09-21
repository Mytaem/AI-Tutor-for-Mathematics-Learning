"""Bộ sinh lỗi có nhãn cho ĐẠI SỐ TUYẾN TÍNH (MAE101 ch7–10, MAI391 ch4).

Mỗi hàm tái hiện đúng MỘT kiểu sai kinh điển, tính bằng SymPy từ chính dữ liệu
của đề (ma trận, hệ, phương trình), không viết tay. Hàng rào
``is_genuinely_wrong`` ở tầng khung vẫn chặn mọi mẫu tình cờ lại đúng.

Cảnh báo quan trọng cho phần đánh giá: các bộ sinh lỗi này và phần chẩn đoán của
verifier đại số tuyến tính được viết từ CÙNG một bảng phân loại lỗi. Tỉ lệ gán nhãn đúng
trên dữ liệu tổng hợp vì thế sẽ rất cao và phần nào mang tính vòng quanh — nó
chứng minh verifier nhất quán với taxonomy, KHÔNG chứng minh verifier bắt được
lỗi của sinh viên thật. Con số trung thực phải đo trên bài làm sai thật.

Mã lỗi ``LA.*`` dùng chung cho mọi môn có đại số tuyến tính; bài thuộc môn nào
thì chỉ nhận những mã có trong bảng mã lỗi của môn đó.
"""

from __future__ import annotations

import sympy as sp

from src.core.schema import AnswerType, Item
from src.data_gen.error_injector import InjectedError, register, register_step
from src.verify.base import parse_matrix
from src.verify.equivalence import ParseError


def fmt(matrix: sp.Matrix) -> str:
    """Viết ma trận/vector theo đúng cách sinh viên nhập: ``[[1, 2], [3, 4]]`` hoặc ``[1, 2]``."""
    if matrix.cols == 1:
        return "[" + ", ".join(sp.sstr(e) for e in matrix) + "]"
    rows = ("[" + ", ".join(sp.sstr(e) for e in matrix.row(i)) + "]" for i in range(matrix.rows))
    return "[" + ", ".join(rows) + "]"


def _matrix(item: Item) -> sp.Matrix | None:
    return sp.Matrix(item.meta["matrix"]) if "matrix" in item.meta else None


def _task(item: Item) -> str | None:
    return item.meta.get("task")


# --------------------------------------------------------------------------
# Định thức
# --------------------------------------------------------------------------

@register("LA.DET.SIGN")
def _determinant_sign(item: Item) -> str | None:
    """Đổi chỗ hai hàng mà quên đổi dấu."""
    if _task(item) != "determinant":
        return None
    value = _matrix(item).det()
    return sp.sstr(-value) if value != 0 else None


@register("LA.DET.SCALE")
def _determinant_scale(item: Item) -> str | None:
    """Nhân một hàng với 2 để khử cho gọn, rồi quên chia lại."""
    if _task(item) != "determinant":
        return None
    value = _matrix(item).det()
    return sp.sstr(2 * value) if value != 0 else None


# --------------------------------------------------------------------------
# Nghịch đảo
# --------------------------------------------------------------------------

def _invertible(item: Item) -> tuple[sp.Matrix, sp.Expr] | None:
    if _task(item) != "inverse":
        return None
    matrix = _matrix(item)
    determinant = matrix.det()
    return (matrix, determinant) if determinant != 0 else None


@register("LA.INV.NODET")
def _inverse_no_det(item: Item) -> str | None:
    """Dừng ở ma trận phụ hợp, quên nhân 1/det."""
    found = _invertible(item)
    if found is None or found[1] in (1, -1):
        return None  # det = ±1 thì phụ hợp trùng (±) nghịch đảo, không tạo ra lỗi
    matrix, determinant = found
    return fmt(determinant * matrix.inv())


@register("LA.INV.TRANSPOSE")
def _inverse_transpose(item: Item) -> str | None:
    """Quên chuyển vị ma trận các phần bù đại số."""
    found = _invertible(item)
    if found is None:
        return None
    inverse = found[0].inv()
    return fmt(inverse.T) if inverse != inverse.T else None


@register("LA.INV.NOSIGN")
def _inverse_no_sign(item: Item) -> str | None:
    """Ma trận 2×2: đổi chỗ đường chéo chính nhưng quên đổi dấu hai phần tử kia."""
    found = _invertible(item)
    if found is None or found[0].shape != (2, 2):
        return None
    (a, b, c, d), determinant = found[0], found[1]
    if b == 0 and c == 0:
        return None
    return fmt(sp.Matrix([[d, b], [c, a]]) / determinant)


@register("LA.INV.SINGULAR")
def _inverse_of_singular(item: Item) -> str | None:
    """Vẫn đưa ra một "nghịch đảo" cho ma trận suy biến."""
    if _task(item) != "inverse" or _matrix(item).det() != 0:
        return None
    return fmt(sp.eye(_matrix(item).rows))


@register("LA.INV.FALSESINGULAR")
def _inverse_false_singular(item: Item) -> str | None:
    """Tính sai định thức ra 0, kết luận không khả nghịch."""
    return "không khả nghịch" if _invertible(item) is not None else None


# --------------------------------------------------------------------------
# Hệ phương trình
# --------------------------------------------------------------------------

def _system(item: Item):
    """(A, b, nghiệm tham số, các tham số) nếu hệ có nghiệm, ngược lại None."""
    if item.answer_type is not AnswerType.LINEAR_SYSTEM:
        return None
    A, b = sp.Matrix(item.meta["A"]), sp.Matrix(item.meta["b"])
    if A.rank() != A.row_join(b).rank():
        return None
    solution, parameters = A.gauss_jordan_solve(b)
    return A, b, solution, list(parameters)


@register("LA.SYS.NOTSOLUTION")
def _system_not_solution(item: Item) -> str | None:
    """Sai một phép tính khi thế ngược: thành phần cuối lệch 1."""
    found = _system(item)
    if found is None or found[3]:
        return None
    solution = found[2].copy()
    solution[-1] += 1
    return fmt(solution)


@register("LA.SYS.PARTIAL")
def _system_partial(item: Item) -> str | None:
    """Hệ vô số nghiệm mà chỉ đưa ra một nghiệm riêng (cho mọi tham số bằng 0)."""
    found = _system(item)
    if found is None or not found[3]:
        return None
    _, _, solution, parameters = found
    return fmt(solution.subs({p: 0 for p in parameters}))


@register("LA.SYS.INCONSISTENT")
def _system_inconsistent(item: Item) -> str | None:
    """Hệ vô nghiệm nhưng vẫn đưa ra một bộ số."""
    if item.answer_type is not AnswerType.LINEAR_SYSTEM or _system(item) is not None:
        return None
    return fmt(sp.zeros(sp.Matrix(item.meta["A"]).cols, 1))


@register("LA.SYS.FALSENOSOL")
def _system_false_no_solution(item: Item) -> str | None:
    return "vô nghiệm" if _system(item) is not None else None


@register("LA.SHAPE")
def _system_shape(item: Item) -> str | None:
    """Thừa một thành phần — thường do chép cả cột vế phải vào nghiệm."""
    found = _system(item)
    if found is None:
        return None
    _, _, solution, parameters = found
    particular = solution.subs({p: 0 for p in parameters})
    return fmt(particular.col_join(sp.Matrix([0])))


# --------------------------------------------------------------------------
# Trị riêng, vector riêng
# --------------------------------------------------------------------------

def _eigenvalues(item: Item) -> list[sp.Expr] | None:
    if _task(item) != "eigenvalues":
        return None
    return sorted(_matrix(item).eigenvals(), key=lambda v: sp.re(v))


@register("LA.EIG.MISSING")
def _eigen_missing(item: Item) -> str | None:
    """Tìm thiếu một trị riêng."""
    values = _eigenvalues(item)
    if values is None or len(values) < 2:
        return None
    return ", ".join(sp.sstr(v) for v in values[:-1])


@register("LA.EIG.NOTVALUE")
def _eigen_not_value(item: Item) -> str | None:
    """Giải sai phương trình đặc trưng: một nghiệm bị lệch."""
    values = _eigenvalues(item)
    if values is None:
        return None
    wrong = values[-1] + 1
    while wrong in values:
        wrong += 1
    return ", ".join(sp.sstr(v) for v in values[:-1] + [wrong])


def _eigen_item(item: Item) -> tuple[sp.Matrix, sp.Expr] | None:
    # Bài có ``task`` riêng (PCA...) do mảng khác chấm và có mã lỗi riêng: cùng
    # một đáp án sai mà mang hai nhãn (LA.EIG.WRONGVALUE và MAI.PCA.SMALLEST)
    # là dữ liệu huấn luyện mâu thuẫn.
    if item.answer_type is not AnswerType.EIGENVECTOR or item.meta.get("task"):
        return None
    return sp.Matrix(item.meta["matrix"]), sp.sympify(item.meta["eigenvalue"])


def _is_eigenvector_of_any(matrix: sp.Matrix, vector: sp.Matrix) -> bool:
    return any((matrix * vector - value * vector).is_zero_matrix for value in matrix.eigenvals())


@register("LA.EIG.ZEROVEC")
def _eigen_zero_vector(item: Item) -> str | None:
    found = _eigen_item(item)
    return fmt(sp.zeros(found[0].cols, 1)) if found else None


@register("LA.EIG.WRONGVALUE")
def _eigen_wrong_value(item: Item) -> str | None:
    """Tính đúng một vector riêng — nhưng của trị riêng khác."""
    found = _eigen_item(item)
    if found is None:
        return None
    matrix, eigenvalue = found
    for value, _, vectors in matrix.eigenvects():
        if value != eigenvalue:
            return fmt(vectors[0])
    return None


@register("LA.EIG.NOTEIGEN")
def _eigen_not_eigenvector(item: Item) -> str | None:
    """Giải sai hệ (A − λI)v = 0: ra một vector không phải vector riêng của trị riêng nào."""
    found = _eigen_item(item)
    if found is None:
        return None
    matrix = found[0]
    try:
        correct = parse_matrix(item.answer_text)
    except ParseError:
        return None
    for index in range(matrix.cols):
        candidate = correct.copy()
        candidate[index] += 1
        # Tránh tình cờ ra vector riêng của trị riêng KHÁC — đó là một mã lỗi khác.
        if not _is_eigenvector_of_any(matrix, candidate):
            return fmt(candidate)
    return None


# --------------------------------------------------------------------------
# Khử Gauss
# --------------------------------------------------------------------------

@register_step
def inject_row_operation_error(item: Item) -> InjectedError | None:
    """Tính sai một phép cộng bội hàng ở bước thứ hai của lời giải mẫu.

    Lỗi nằm ở bước, đáp án cuối vẫn đúng — kiểm tra verifier có bắt được kiểu
    sai bù trừ không, và có chỉ đúng bước sai ĐẦU TIÊN không.
    """
    steps = [step.expr for step in item.reference_solution_steps]
    if len(steps) < 2:
        return None
    try:
        matrix = parse_matrix(steps[1])
    except ParseError:
        return None

    matrix[matrix.rows - 1, matrix.cols - 1] += 2
    wrong_steps = [steps[0], fmt(matrix)] + steps[2:]
    return InjectedError(
        item_id=item.item_id,
        subject=item.subject.value,
        error_code="LA.ROWOP.INVALID",
        tier="E-PROCEDURE",
        statement_vi=item.statement_vi,
        correct_answer=item.answer_text,
        wrong_final_answer=item.answer_text,
        wrong_steps=wrong_steps,
        wrong_step_index=2,
    )
