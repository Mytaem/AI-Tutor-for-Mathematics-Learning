"""Sinh đề MAI391 (toán cho học máy) theo template có tham số.

Khác hai môn kia, bộ chấm MML không có một hàm "đáp án chuẩn" dùng chung — mỗi
loại bài kiểm theo một TÍNH CHẤT riêng (θ thoả phương trình chuẩn, ∇f tại điểm
dừng bằng 0, A·v = λv). Nên ở đây đáp án được tính thẳng bằng SymPy, và hàng rào
duy nhất là verifier chấm lại bài vừa sinh — đúng vai trò nó sinh ra để làm.

Ma trận không gieo ngẫu nhiên tự do mà **dựng ngược từ trị riêng đã chọn**:
``A = P·D·P⁻¹`` với P tam giác đơn vị (định thức 1) cho ra ma trận nguyên có trị
riêng nguyên. Gieo bừa thì hầu hết ma trận có trị riêng vô tỉ, đề trở thành bài
tập bấm máy tính chứ không còn dạy được gì.
"""

from __future__ import annotations

import random

import sympy as sp

from src.core.schema import Subject
from src.data_gen.bank_builder import Registry

MAI391 = Registry(Subject.MAI391, "MAI391")
template = MAI391.template

X, Y = sp.symbols("x y")


def text(value) -> str:
    return sp.sstr(value)


def as_list(matrix: sp.Matrix) -> list[str]:
    return [text(entry) for entry in matrix]


def as_rows(matrix: sp.Matrix) -> list[list[str]]:
    return [[text(matrix[r, c]) for c in range(matrix.cols)] for r in range(matrix.rows)]


def show_matrix(values) -> str:
    return "[" + ", ".join("[" + ", ".join(str(v) for v in row) + "]" for row in values) + "]"


def draft(meta: dict, statement_vi: str, answer, answer_type: str, **extra) -> dict:
    return {"meta": meta, "statement_vi": statement_vi, "answer": answer,
            "answer_type": answer_type, **extra}


def integer_matrix(rng: random.Random, eigenvalues: list[int]) -> sp.Matrix:
    """Ma trận NGUYÊN có đúng các trị riêng cho trước (dựng bằng P·D·P⁻¹)."""
    D = sp.diag(*eigenvalues)
    shear = rng.choice([1, 2, -1, -2, 3])
    P = sp.Matrix([[1, shear], [0, 1]])
    return sp.Matrix(P * D * P.inv())


def symmetric_matrix(rng: random.Random) -> tuple[sp.Matrix, list[int]]:
    """Ma trận đối xứng [[a, b], [b, a]] — trị riêng a ± b, luôn chéo hoá được."""
    a = rng.randint(2, 7)
    b = rng.randint(1, a - 1)
    return sp.Matrix([[a, b], [b, a]]), [a + b, a - b]


def nice_vector(rng: random.Random) -> list[int]:
    """Vector có độ dài nguyên — bộ ba Pythagoras, để bài chuẩn/lề không ra căn xấu."""
    return list(rng.choice([[3, 4], [6, 8], [5, 12], [8, 15], [9, 12], [7, 24]]))


# --------------------------------------------------------------------------
# Chương 3 — hình học giải tích
# --------------------------------------------------------------------------

@template("norm", ["MAI.GEO.NORM"], 0.25, "Chuẩn Euclid")
def _norm(rng: random.Random):
    vector = nice_vector(rng)
    if rng.random() < 0.3:
        vector = [-vector[0], vector[1]]
    order = rng.choice([1, 2, 2, 2])
    meta = {"task": "norm", "vector": vector, "ord": order}
    name = "‖v‖₁ (chuẩn 1)" if order == 1 else "‖v‖ (chuẩn Euclid)"
    value = sum(abs(v) for v in vector) if order == 1 else sp.sqrt(sum(v**2 for v in vector))
    return draft(meta, f"Cho v = {vector}. Tính {name}", text(sp.nsimplify(value)), "number")


@template("inner_product", ["MAI.GEO.ANGLE"], 0.25, "Tích vô hướng")
def _inner_product(rng: random.Random):
    u = [rng.randint(-5, 5) for _ in range(2)]
    v = [rng.randint(-5, 5) for _ in range(2)]
    if u == [0, 0] or v == [0, 0]:
        return None
    meta = {"task": "inner_product", "u": u, "v": v}
    return draft(meta, f"Cho u = {u}, v = {v}. Tính tích vô hướng uᵀv",
                 text(sum(a * b for a, b in zip(u, v))), "number")


@template("angle_cos", ["MAI.GEO.ANGLE"], 0.45, "Góc giữa hai vector")
def _angle_cos(rng: random.Random):
    u = rng.choice([[1, 0], [0, 1], [1, 1], [2, 0], [3, 4]])
    v = rng.choice([[1, 1], [1, -1], [0, 2], [4, 3], [2, 2]])
    dot = sum(a * b for a, b in zip(u, v))
    norms = sp.sqrt(sum(a**2 for a in u)) * sp.sqrt(sum(b**2 for b in v))
    if norms == 0:
        return None
    meta = {"task": "angle_cos", "u": u, "v": v}
    return draft(meta, f"Cho u = {u}, v = {v}. Tính cos của góc giữa hai vector",
                 text(sp.nsimplify(sp.simplify(dot / norms))), "number")


@template("projection", ["MAI.GEO.PROJ"], 0.5, "Hình chiếu trực giao")
def _projection(rng: random.Random):
    x = [rng.randint(-4, 5), rng.randint(-4, 5)]
    b = rng.choice([[1, 0], [0, 1], [1, 1], [2, 1], [1, 2], [3, 4]])
    if x == [0, 0]:
        return None
    xv, bv = sp.Matrix(x), sp.Matrix(b)
    meta = {"task": "projection", "x": x, "b": b}
    projection = (bv.dot(xv) / bv.dot(bv)) * bv
    return draft(meta, f"Chiếu vector x = {x} lên đường thẳng sinh bởi b = {b}. Tìm hình chiếu",
                 as_list(projection), "matrix")


# --------------------------------------------------------------------------
# Chương 4 — phân rã ma trận (dùng chung mã lỗi LA.* với MAE101)
# --------------------------------------------------------------------------

@template("trace", ["MAI.DEC.TRACE"], 0.2, "Vết ma trận")
def _trace(rng: random.Random):
    matrix = [[rng.randint(-5, 6), rng.randint(-5, 6)], [rng.randint(-5, 6), rng.randint(-5, 6)]]
    meta = {"task": "trace", "matrix": matrix}
    return draft(meta, f"Tính vết (trace) của A = {show_matrix(matrix)}",
                 text(matrix[0][0] + matrix[1][1]), "number")


@template("determinant", ["MAI.DEC.TRACE"], 0.3, "Định thức 2×2")
def _determinant(rng: random.Random):
    matrix = [[rng.randint(-5, 6), rng.randint(-5, 6)], [rng.randint(-5, 6), rng.randint(-5, 6)]]
    meta = {"task": "determinant", "matrix": matrix}
    return draft(meta, f"Tính định thức của A = {show_matrix(matrix)}",
                 text(sp.Matrix(matrix).det()), "number")


@template("eigenvalues", ["MAI.DEC.EIGEN"], 0.5, "Đa thức đặc trưng")
def _eigenvalues(rng: random.Random):
    values = rng.sample([-3, -2, -1, 1, 2, 3, 4, 5, 6], 2)
    matrix = integer_matrix(rng, values)
    meta = {"task": "eigenvalues", "matrix": as_rows(matrix)}
    return draft(meta, f"Tìm các trị riêng của A = {show_matrix(as_rows(matrix))}",
                 sorted(text(v) for v in values), "set")


@template("diagonal_form", ["MAI.DEC.DIAG"], 0.6, "Chéo hoá")
def _diagonal_form(rng: random.Random):
    values = rng.sample([-2, 1, 2, 3, 4, 5, 6], 2)
    matrix = integer_matrix(rng, values)
    meta = {"task": "diagonal_form", "matrix": as_rows(matrix)}
    diagonal = as_rows(sp.diag(*values))
    return draft(meta, f"Chéo hoá A = {show_matrix(as_rows(matrix))}. Viết ma trận chéo D",
                 diagonal, "matrix")


@template("singular_values", ["MAI.DEC.SVD"], 0.6, "Giá trị kỳ dị")
def _singular_values(rng: random.Random):
    a, b = rng.randint(1, 6), rng.randint(1, 6)
    matrix = rng.choice([[[a, 0], [0, -b]], [[a, 0], [0, b]], [[0, a], [b, 0]]])
    values = sp.Matrix(matrix).singular_values()
    meta = {"task": "singular_values", "matrix": matrix}
    return draft(meta, f"Tìm các giá trị kỳ dị của A = {show_matrix(matrix)}",
                 [text(v) for v in values], "set")


# --------------------------------------------------------------------------
# Đại số tuyến tính dùng chung với MAE101 (mã lỗi LA.*)
# --------------------------------------------------------------------------
# Các dạng dưới đây do LinearAlgebraVerifier chấm, không phải MMLVerifier. Chúng
# có mặt ở đây vì mã lỗi LA.* dùng chung cho cả hai môn, mà bộ sinh đề MAE101
# lại gắn chặt vào tích phân nên không chứa nổi chúng.

@template("eigenvector", ["MAI.DEC.EIGEN"], 0.6, "Vector riêng: giải (A − λI)v = 0")
def _eigenvector(rng: random.Random):
    values = rng.sample([-2, 1, 2, 3, 4, 5, 6], 2)
    matrix = integer_matrix(rng, values)
    chosen = rng.choice(values)
    vectors = [v for value, _, vectors in matrix.eigenvects() if value == chosen for v in vectors]
    if not vectors:
        return None
    direction = vectors[0] / max(abs(entry) for entry in vectors[0])
    meta = {"matrix": as_rows(matrix), "eigenvalue": text(chosen)}
    return draft(meta, f"Cho A = {show_matrix(as_rows(matrix))} và trị riêng λ = {chosen}. "
                       f"Tìm một vector riêng ứng với λ",
                 as_list(direction), "eigenvector")


@template("inverse", ["MAI.DEC.TRACE"], 0.55, "Ma trận nghịch đảo 2×2")
def _inverse(rng: random.Random):
    entries = [[rng.randint(-5, 6), rng.randint(-5, 6)], [rng.randint(-5, 6), rng.randint(-5, 6)]]
    matrix = sp.Matrix(entries)
    meta = {"task": "inverse", "matrix": entries}
    if matrix.det() == 0:
        # Ma trận suy biến: đáp án đúng là "không khả nghịch" — dạng bài rất đáng có,
        # vì lỗi kinh điển là cứ áp công thức nghịch đảo bất kể định thức bằng 0.
        return draft(meta, f"Tìm ma trận nghịch đảo của A = {show_matrix(entries)}",
                     "không khả nghịch", "text")
    return draft(meta, f"Tìm ma trận nghịch đảo của A = {show_matrix(entries)}",
                 as_rows(matrix.inv()), "matrix")


@template("rank", ["MAI.DEC.TRACE"], 0.45, "Hạng qua dạng bậc thang")
def _rank(rng: random.Random):
    rows = rng.choice([2, 3])
    entries = [[rng.randint(-4, 5) for _ in range(3)] for _ in range(rows)]
    if rng.random() < 0.4:
        entries[-1] = [2 * value for value in entries[0]]   # hàng phụ thuộc -> hạng giảm
    meta = {"task": "rank", "matrix": entries}
    return draft(meta, f"Tìm hạng của A = {show_matrix(entries)}",
                 text(sp.Matrix(entries).rank()), "number")


@template("system_inconsistent", ["MAI.DEC.TRACE"], 0.6, "Hệ vô nghiệm: rank A < rank [A|b]")
def _system_inconsistent(rng: random.Random):
    """Hệ VÔ NGHIỆM — dạng đề mà cả taxonomy lỗi xoay quanh.

    Hai mã LA.SYS.INCONSISTENT và LA.SYS.FALSENOSOL chỉ cài được vào đúng dạng
    này; không có template riêng thì cả tập dữ liệu chỉ có một mẫu duy nhất.
    """
    row = [rng.randint(1, 4), rng.randint(1, 4)]
    factor = rng.choice([1, 2, 3])
    first = rng.randint(1, 6)
    second = first * factor + rng.choice([1, 2, -1, -2])     # lệch đi -> mâu thuẫn
    A = [row, [value * factor for value in row]]
    meta = {"A": A, "b": [first, second]}
    equations = ", ".join(_equation(r, v) for r, v in zip(A, meta["b"]))
    return draft(meta, f"Giải hệ: {equations}", "vô nghiệm", "linear_system")


@template("system_underdetermined", ["MAI.DEC.TRACE"], 0.65, "Hệ vô số nghiệm: nghiệm tổng quát")
def _system_underdetermined(rng: random.Random):
    """Hệ VÔ SỐ NGHIỆM — bẫy: đưa ra một nghiệm riêng rồi coi là xong (LA.SYS.PARTIAL)."""
    a, b, c = rng.randint(1, 3), rng.randint(1, 3), rng.randint(1, 3)
    factor = rng.choice([2, 3])
    total = rng.randint(2, 8)
    A = [[a, b, c], [a * factor, b * factor, c * factor]]
    meta = {"A": A, "b": [total, total * factor]}
    equations = ", ".join(
        _equation3(row, value) for row, value in zip(A, meta["b"])
    )
    # Nghiệm tổng quát hai tham số: x = (total − b·s − c·t)/a
    general = [f"({total} - {b}*s - {c}*t)/{a}", "s", "t"]
    return draft(meta, f"Giải hệ: {equations}", general, "linear_system")


def _equation3(row: list[int], value) -> str:
    parts: list[str] = []
    for coefficient, name in zip(row, ("x", "y", "z")):
        if coefficient == 0:
            continue
        sign = "− " if coefficient < 0 else ("+ " if parts else "")
        size = abs(coefficient)
        parts.append(f"{sign}{'' if size == 1 else size}{name}")
    return f"{' '.join(parts) or '0'} = {value}"


@template("inverse_singular", ["MAI.DEC.TRACE"], 0.5, "Ma trận suy biến thì không có nghịch đảo")
def _inverse_singular(rng: random.Random):
    """Ma trận SUY BIẾN — bẫy: cứ áp công thức nghịch đảo bất kể định thức bằng 0."""
    a, b = rng.randint(1, 6), rng.randint(1, 6)
    factor = rng.choice([2, 3, -1, -2])
    entries = [[a, b], [a * factor, b * factor]]
    meta = {"task": "inverse", "matrix": entries}
    return draft(meta, f"Tìm ma trận nghịch đảo của A = {show_matrix(entries)}",
                 "không khả nghịch", "text")


def _equation(row: list[int], value) -> str:
    """Viết một phương trình như sách: bỏ hệ số 0, không in hệ số 1, dấu trừ gọn."""
    parts: list[str] = []
    for coefficient, name in zip(row, ("x", "y")):
        if coefficient == 0:
            continue
        sign = "− " if coefficient < 0 else ("+ " if parts else "")
        size = abs(coefficient)
        parts.append(f"{sign}{'' if size == 1 else size}{name}")
    return f"{' '.join(parts) or '0'} = {value}"


@template("linear_system", ["MAI.DEC.TRACE"], 0.5, "Khử Gauss")
def _linear_system(rng: random.Random):
    A = [[rng.randint(-4, 5), rng.randint(-4, 5)], [rng.randint(-4, 5), rng.randint(-4, 5)]]
    matrix = sp.Matrix(A)
    solution = [rng.randint(-4, 5), rng.randint(-4, 5)]
    b = list(matrix * sp.Matrix(solution))
    meta = {"A": A, "b": [int(value) for value in b]}
    if matrix.det() == 0:
        return None                                  # nghiệm không duy nhất, để dạng khác lo
    equations = ", ".join(_equation(row, value) for row, value in zip(A, b))
    return draft(meta, f"Giải hệ: {equations}", [text(v) for v in solution], "linear_system")


# --------------------------------------------------------------------------
# Chương 5 — giải tích vector
# --------------------------------------------------------------------------

def _polynomial(rng: random.Random) -> sp.Expr:
    a, b, c = rng.randint(1, 4), rng.randint(1, 4), rng.randint(-4, 4)
    return rng.choice([
        a * X**2 * Y + c * Y,
        a * X**3 + b * X * Y,
        a * X**2 + b * Y**2 + c * X,
        a * X * Y**2 + b * X,
    ])


@template("gradient", ["MAI.VC.PARTIAL"], 0.45, "Gradient")
def _gradient(rng: random.Random):
    f = _polynomial(rng)
    meta = {"task": "gradient", "f": text(f), "vars": ["x", "y"]}
    return draft(meta, f"Cho f(x, y) = {text(f)}. Tính ∇f",
                 [text(sp.diff(f, v)) for v in (X, Y)], "matrix")


@template("gradient_chain", ["MAI.VC.CHAIN"], 0.6, "Quy tắc dây chuyền")
def _gradient_chain(rng: random.Random):
    """Gradient của hàm HỢP.

    Template gradient ở trên chỉ dùng đa thức, nên lỗi "quên nhân đạo hàm hàm
    trong" không bao giờ cài vào được — mã MAI.VC.NOCHAIN chỉ có đúng một mẫu
    trong cả tập dữ liệu. Dạng bài này sinh ra đúng cái bẫy đó.
    """
    inner = rng.choice([X * Y, X**2 + Y, X**2 * Y, X + Y**2])
    outer = rng.choice([sp.exp, sp.sin, sp.cos, sp.log])
    f = outer(inner) if outer is not sp.log else sp.log(1 + inner**2)
    meta = {"task": "gradient", "f": text(f), "vars": ["x", "y"]}
    return draft(meta, f"Cho f(x, y) = {text(f)}. Tính ∇f",
                 [text(sp.diff(f, v)) for v in (X, Y)], "matrix")


@template("partial", ["MAI.VC.PARTIAL"], 0.35, "Đạo hàm riêng")
def _partial(rng: random.Random):
    f = _polynomial(rng) + rng.choice([sp.sin(Y), sp.exp(X), sp.Integer(0)])
    var = rng.choice(["x", "y"])
    meta = {"task": "partial", "f": text(f), "vars": ["x", "y"], "var": var}
    return draft(meta, f"Cho f(x, y) = {text(f)}. Tính ∂f/∂{var}",
                 text(sp.diff(f, sp.Symbol(var))), "expression")


@template("jacobian", ["MAI.VC.JACOBIAN"], 0.6, "Ma trận Jacobi")
def _jacobian(rng: random.Random):
    f1 = rng.choice([X**2 * Y, X * Y, X**2 + Y, X**3])
    f2 = rng.choice([X + Y, X - Y, X * Y, Y**2])
    meta = {"task": "jacobian", "F": [text(f1), text(f2)], "vars": ["x", "y"]}
    jacobian = sp.Matrix([[sp.diff(f, v) for v in (X, Y)] for f in (f1, f2)])
    return draft(meta, f"Cho F(x, y) = ({text(f1)}, {text(f2)}). Tính ma trận Jacobi",
                 as_rows(jacobian), "matrix")


# --------------------------------------------------------------------------
# Chương 6 — xác suất; chương 7 — tối ưu
# --------------------------------------------------------------------------

@template("moments", ["MAI.PROB.MOMENTS"], 0.45, "Kỳ vọng và phương sai")
def _moments(rng: random.Random):
    values = [0, 1, 2] if rng.random() < 0.5 else [1, 2, 3]
    denominator = rng.choice([4, 5, 8, 10])
    first = rng.randint(1, denominator - 2)
    second = rng.randint(1, denominator - first - 1)
    probabilities = [sp.Rational(first, denominator), sp.Rational(second, denominator),
                     1 - sp.Rational(first + second, denominator)]
    if any(p <= 0 for p in probabilities):
        return None
    task = rng.choice(["expectation", "variance"])
    meta = {"task": task, "values": values, "probs": [text(p) for p in probabilities]}
    mean = sum(v * p for v, p in zip(values, probabilities))
    second_moment = sum(v**2 * p for v, p in zip(values, probabilities))
    answer = mean if task == "expectation" else sp.simplify(second_moment - mean**2)
    name = "E[X]" if task == "expectation" else "Var(X)"
    table = ", ".join(f"P(X = {v}) = {text(p)}" for v, p in zip(values, probabilities))
    return draft(meta, f"Biến ngẫu nhiên X có {table}. Tính {name}", text(answer), "number")


@template("gd_step", ["MAI.OPT.GD"], 0.55, "Một bước gradient descent")
def _gd_step(rng: random.Random):
    a, b = rng.randint(1, 3), rng.randint(1, 3)
    f = a * X**2 + b * Y**2
    x0 = [rng.randint(1, 4), rng.randint(1, 4)]
    rate = sp.Rational(1, rng.choice([5, 10, 20]))
    meta = {"task": "gd_step", "f": text(f), "vars": ["x", "y"], "x0": x0, "lr": text(rate)}
    point = sp.Matrix(x0)
    gradient = sp.Matrix([sp.diff(f, v).subs({X: x0[0], Y: x0[1]}) for v in (X, Y)])
    return draft(meta, f"Cho f(x, y) = {text(f)}, điểm x₀ = {x0}, tốc độ học η = {text(rate)}. "
                       f"Tính x₁ sau một bước gradient descent",
                 as_list(point - rate * gradient), "matrix")


@template("stationary", ["MAI.OPT.CRIT"], 0.5, "Điểm dừng ∇f = 0")
def _stationary(rng: random.Random):
    px, py = rng.randint(-3, 3), rng.randint(-3, 3)
    f = sp.expand((X - px)**2 + (Y - py)**2)
    meta = {"task": "stationary", "f": text(f), "vars": ["x", "y"]}
    return draft(meta, f"Tìm điểm dừng của f(x, y) = {text(f)}", [text(px), text(py)], "matrix")


# --------------------------------------------------------------------------
# Chương 9 — hồi quy; chương 10 — PCA; chương 12 — SVM
# --------------------------------------------------------------------------

@template("least_squares", ["MAI.REG.LS"], 0.65, "Phương trình chuẩn")
def _least_squares(rng: random.Random):
    size = rng.choice([3, 4])
    X_design = [[1, index] for index in range(size)]
    y = [rng.randint(0, 6) for _ in range(size)]
    if len(set(y)) == 1:
        return None
    matrix, target = sp.Matrix(X_design), sp.Matrix(y)
    try:
        theta = (matrix.T * matrix).inv() * matrix.T * target
    except ValueError:
        return None
    meta = {"task": "least_squares", "X": X_design, "y": y}
    return draft(meta, f"Cho X = {show_matrix(X_design)}, y = {y}. "
                       f"Tìm θ bình phương tối thiểu (giải XᵀXθ = Xᵀy)",
                 as_list(theta), "matrix")


@template("pca_first", ["MAI.PCA"], 0.6, "Thành phần chính thứ nhất")
def _pca_first(rng: random.Random):
    matrix, values = symmetric_matrix(rng)
    largest = max(values)
    vectors = [v for value, _, vectors in matrix.eigenvects() if value == largest for v in vectors]
    if not vectors:
        return None
    direction = vectors[0] / max(abs(entry) for entry in vectors[0])
    meta = {"task": "pca_first", "matrix": as_rows(matrix), "eigenvalue": text(largest)}
    return draft(meta, f"Ma trận hiệp phương sai S = {show_matrix(as_rows(matrix))}. "
                       f"Tìm thành phần chính thứ nhất (vector riêng ứng với trị riêng lớn nhất)",
                 as_list(direction), "eigenvector")


@template("pca_ratio", ["MAI.PCA"], 0.5, "Tỉ lệ phương sai giải thích")
def _pca_ratio(rng: random.Random):
    a = rng.randint(2, 9)
    b = rng.randint(1, a - 1)
    matrix = [[a, 0], [0, b]]
    meta = {"task": "pca_ratio", "matrix": matrix, "k": 1}
    return draft(meta, f"Ma trận hiệp phương sai S = {show_matrix(matrix)}. "
                       f"Thành phần chính thứ nhất giải thích bao nhiêu phần phương sai?",
                 text(sp.Rational(a, a + b)), "number")


@template("svm_margin", ["MAI.SVM.MARGIN"], 0.45, "Độ rộng lề 2/‖w‖")
def _svm_margin(rng: random.Random):
    # Một nửa số đề lấy w có chuẩn nguyên cho đẹp, nửa còn lại gieo tự do: chỉ
    # dùng 6 bộ ba Pythagoras thì cả template chỉ sinh nổi vài đề khác nhau.
    w = nice_vector(rng) if rng.random() < 0.5 else [rng.randint(-6, 6), rng.randint(-6, 6)]
    if w == [0, 0]:
        return None
    meta = {"task": "svm_margin", "w": w}
    norm = sp.sqrt(sum(value**2 for value in w))
    return draft(meta, f"Siêu phẳng phân tách có w = {w}. Tính độ rộng lề",
                 text(sp.nsimplify(2 / norm)), "number")


def generate(count: int, seed: int = 20260923, validate: bool = True):
    return MAI391.generate(count, seed=seed, validate=validate)


def template_ids() -> list[str]:
    return MAI391.template_ids()
