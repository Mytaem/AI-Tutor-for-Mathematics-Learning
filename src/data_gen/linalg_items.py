"""Sinh đề đại số tuyến tính dùng chung cho MAE101 và MAI391.

Hai môn dạy cùng một mảng kiến thức và **dùng chung bảng mã lỗi `LA.*`**, chỉ khác
mã kỹ năng: MAE101 gọi là ``MAE.LA.DET``, MAI391 gọi là ``MAI.DEC.TRACE``. Viết
template hai lần là tự chuốc lấy hai bản dần dần lệch nhau, nên ở đây mỗi dạng bài
viết một lần rồi đăng ký vào cả hai môn với bảng kỹ năng riêng.

Trước module này, MAE101 chỉ có 20 bài đại số tuyến tính chép tay trong khi phần
giải tích có 1.200 bài sinh tự động — bộ chọn bài gần như không có gì để chọn khi
người học vào chương ma trận.
"""

from __future__ import annotations

import random
from typing import Callable

import sympy as sp

from src.core.schema import Subject
from src.data_gen.bank_builder import Registry

#: Mã kỹ năng của từng môn cho cùng một dạng bài.
SKILL_MAP: dict[str, dict[str, list[str]]] = {
    "MAE101": {
        "determinant": ["MAE.LA.DET"],
        "inverse": ["MAE.LA.INV"],
        "rank": ["MAE.LA.RANK"],
        "eigenvalues": ["MAE.LA.EIGVAL"],
        "eigenvector": ["MAE.LA.EIGVEC"],
        "linear_system": ["MAE.LA.GAUSS"],
        "system_inconsistent": ["MAE.LA.GAUSS", "MAE.LA.RANK"],
        "system_underdetermined": ["MAE.LA.PARAM"],
        "inverse_singular": ["MAE.LA.INV", "MAE.LA.DET"],
        "matrix_product": ["MAE.LA.MAT"],
    },
    "MAI391": {
        "determinant": ["MAI.DEC.TRACE"],
        "inverse": ["MAI.DEC.TRACE"],
        "rank": ["MAI.DEC.TRACE"],
        "eigenvalues": ["MAI.DEC.EIGEN"],
        "eigenvector": ["MAI.DEC.EIGEN"],
        "linear_system": ["MAI.DEC.TRACE"],
        "system_inconsistent": ["MAI.DEC.TRACE"],
        "system_underdetermined": ["MAI.DEC.TRACE"],
        "inverse_singular": ["MAI.DEC.TRACE"],
        "matrix_product": ["MAI.DEC.TRACE"],
    },
}


def text(value) -> str:
    return sp.sstr(value)


def as_rows(matrix: sp.Matrix) -> list[list[str]]:
    return [[text(matrix[r, c]) for c in range(matrix.cols)] for r in range(matrix.rows)]


def show_matrix(values) -> str:
    return "[" + ", ".join("[" + ", ".join(str(v) for v in row) + "]" for row in values) + "]"


def integer_matrix(rng: random.Random, eigenvalues: list[int]) -> sp.Matrix:
    """Ma trận NGUYÊN có đúng các trị riêng cho trước (dựng bằng P·D·P⁻¹)."""
    shear = rng.choice([1, 2, -1, -2, 3])
    P = sp.Matrix([[1, shear], [0, 1]])
    return sp.Matrix(P * sp.diag(*eigenvalues) * P.inv())


def equation(row: list[int], names: tuple[str, ...]) -> str:
    """Viết vế trái một phương trình như sách: bỏ hệ số 0, không in hệ số 1."""
    parts: list[str] = []
    for coefficient, name in zip(row, names):
        if coefficient == 0:
            continue
        sign = "− " if coefficient < 0 else ("+ " if parts else "")
        size = abs(coefficient)
        parts.append(f"{sign}{'' if size == 1 else size}{name}")
    return " ".join(parts) or "0"


def gauss_steps(matrix: sp.Matrix, target: sp.Matrix) -> list[str]:
    """Lời giải mẫu dạng ma trận mở rộng, từng bước khử Gauss.

    Có lời giải theo bước thì mới cài được lỗi ở mức BƯỚC (biến đổi hàng không
    hợp lệ) — không có nó thì mã ``LA.ROWOP.INVALID`` không có mẫu nào.
    """
    augmented = matrix.row_join(target)
    steps = [augmented]
    if augmented[0, 0] == 0:
        augmented = augmented.elementary_row_op("n<->m", row1=0, row2=1)
        steps.append(augmented)
    if augmented[0, 0] != 0 and augmented[1, 0] != 0:
        factor = sp.Rational(augmented[1, 0], augmented[0, 0])
        augmented = augmented.elementary_row_op("n->n+km", row=1, k=-factor, row2=0)
        steps.append(augmented)
    steps.append(augmented.rref()[0])
    return [show_matrix(as_rows(step)) for step in steps]


# --------------------------------------------------------------------------
# Các dạng bài — mỗi hàm trả về phần riêng của một đề, chưa gắn kỹ năng
# --------------------------------------------------------------------------

Builder = Callable[[random.Random], dict | None]
BUILDERS: dict[str, tuple[Builder, float, str]] = {}


def builder(name: str, difficulty: float, method_vi: str):
    def decorator(function: Builder) -> Builder:
        BUILDERS[name] = (function, difficulty, method_vi)
        return function

    return decorator


@builder("determinant", 0.3, "Định thức 2×2")
def _determinant(rng: random.Random):
    entries = [[rng.randint(-5, 6), rng.randint(-5, 6)] for _ in range(2)]
    return {"meta": {"task": "determinant", "matrix": entries},
            "statement_vi": f"Tính định thức của A = {show_matrix(entries)}",
            "answer": text(sp.Matrix(entries).det()), "answer_type": "number"}


@builder("rank", 0.45, "Hạng qua dạng bậc thang")
def _rank(rng: random.Random):
    rows = rng.choice([2, 3])
    entries = [[rng.randint(-4, 5) for _ in range(3)] for _ in range(rows)]
    if rng.random() < 0.4:
        entries[-1] = [2 * value for value in entries[0]]   # hàng phụ thuộc
    return {"meta": {"task": "rank", "matrix": entries},
            "statement_vi": f"Tìm hạng của A = {show_matrix(entries)}",
            "answer": text(sp.Matrix(entries).rank()), "answer_type": "number"}


@builder("inverse", 0.55, "Ma trận nghịch đảo 2×2")
def _inverse(rng: random.Random):
    entries = [[rng.randint(-5, 6), rng.randint(-5, 6)] for _ in range(2)]
    matrix = sp.Matrix(entries)
    meta = {"task": "inverse", "matrix": entries}
    statement = f"Tìm ma trận nghịch đảo của A = {show_matrix(entries)}"
    if matrix.det() == 0:
        return {"meta": meta, "statement_vi": statement,
                "answer": "không khả nghịch", "answer_type": "text"}
    return {"meta": meta, "statement_vi": statement,
            "answer": as_rows(matrix.inv()), "answer_type": "matrix"}


@builder("inverse_singular", 0.5, "Ma trận suy biến không có nghịch đảo")
def _inverse_singular(rng: random.Random):
    a, b = rng.randint(1, 6), rng.randint(1, 6)
    factor = rng.choice([2, 3, -1, -2])
    entries = [[a, b], [a * factor, b * factor]]
    return {"meta": {"task": "inverse", "matrix": entries},
            "statement_vi": f"Tìm ma trận nghịch đảo của A = {show_matrix(entries)}",
            "answer": "không khả nghịch", "answer_type": "text"}


@builder("eigenvalues", 0.5, "Đa thức đặc trưng")
def _eigenvalues(rng: random.Random):
    values = rng.sample([-3, -2, -1, 1, 2, 3, 4, 5, 6], 2)
    matrix = integer_matrix(rng, values)
    return {"meta": {"task": "eigenvalues", "matrix": as_rows(matrix)},
            "statement_vi": f"Tìm các trị riêng của A = {show_matrix(as_rows(matrix))}",
            "answer": sorted(text(v) for v in values), "answer_type": "set"}


@builder("eigenvector", 0.6, "Giải (A − λI)v = 0")
def _eigenvector(rng: random.Random):
    values = rng.sample([-2, 1, 2, 3, 4, 5, 6], 2)
    matrix = integer_matrix(rng, values)
    chosen = rng.choice(values)
    vectors = [v for value, _, vectors in matrix.eigenvects() if value == chosen for v in vectors]
    if not vectors:
        return None
    direction = vectors[0] / max(abs(entry) for entry in vectors[0])
    return {"meta": {"matrix": as_rows(matrix), "eigenvalue": text(chosen)},
            "statement_vi": (f"Cho A = {show_matrix(as_rows(matrix))} và trị riêng λ = {chosen}. "
                             f"Tìm một vector riêng ứng với λ"),
            "answer": [text(entry) for entry in direction], "answer_type": "eigenvector"}


@builder("linear_system", 0.5, "Khử Gauss")
def _linear_system(rng: random.Random):
    A = [[rng.randint(-4, 5), rng.randint(-4, 5)] for _ in range(2)]
    matrix = sp.Matrix(A)
    if matrix.det() == 0:
        return None
    solution = [rng.randint(-4, 5), rng.randint(-4, 5)]
    b = [int(value) for value in matrix * sp.Matrix(solution)]
    equations = ", ".join(f"{equation(row, ('x', 'y'))} = {value}" for row, value in zip(A, b))
    return {"meta": {"A": A, "b": b}, "statement_vi": f"Giải hệ: {equations}",
            "answer": [text(v) for v in solution], "answer_type": "linear_system",
            "steps": gauss_steps(matrix, sp.Matrix(b))}


@builder("system_inconsistent", 0.6, "Hệ vô nghiệm: rank A < rank [A|b]")
def _system_inconsistent(rng: random.Random):
    row = [rng.randint(1, 4), rng.randint(1, 4)]
    factor = rng.choice([1, 2, 3])
    first = rng.randint(1, 6)
    second = first * factor + rng.choice([1, 2, -1, -2])
    A = [row, [value * factor for value in row]]
    b = [first, second]
    equations = ", ".join(f"{equation(r, ('x', 'y'))} = {v}" for r, v in zip(A, b))
    return {"meta": {"A": A, "b": b}, "statement_vi": f"Giải hệ: {equations}",
            "answer": "vô nghiệm", "answer_type": "linear_system"}


@builder("system_underdetermined", 0.65, "Hệ vô số nghiệm: nghiệm tổng quát")
def _system_underdetermined(rng: random.Random):
    a, b, c = rng.randint(1, 3), rng.randint(1, 3), rng.randint(1, 3)
    factor = rng.choice([2, 3])
    total = rng.randint(2, 8)
    A = [[a, b, c], [a * factor, b * factor, c * factor]]
    values = [total, total * factor]
    equations = ", ".join(f"{equation(row, ('x', 'y', 'z'))} = {value}"
                          for row, value in zip(A, values))
    return {"meta": {"A": A, "b": values}, "statement_vi": f"Giải hệ: {equations}",
            "answer": [f"({total} - {b}*s - {c}*t)/{a}", "s", "t"],
            "answer_type": "linear_system"}


@builder("matrix_product", 0.35, "Nhân hai ma trận")
def _matrix_product(rng: random.Random):
    left = [[rng.randint(-4, 5), rng.randint(-4, 5)] for _ in range(2)]
    right = [[rng.randint(-4, 5), rng.randint(-4, 5)] for _ in range(2)]
    product = sp.Matrix(left) * sp.Matrix(right)
    return {"meta": {"task": "matrix_product", "left": left, "right": right},
            "statement_vi": (f"Tính tích AB với A = {show_matrix(left)}, "
                             f"B = {show_matrix(right)}"),
            "answer": as_rows(product), "answer_type": "matrix"}


# --------------------------------------------------------------------------

def register_all(registry: Registry, subject: str, only: list[str] | None = None) -> None:
    """Gắn các dạng bài vào registry của một môn, với mã kỹ năng của môn đó."""
    skills = SKILL_MAP[subject]
    for name, (build, difficulty, method) in BUILDERS.items():
        if only is not None and name not in only:
            continue
        if name not in skills:
            continue
        registry.template(name, skills[name], difficulty, method)(build)


MAE101_LA = Registry(Subject.MAE101, "MAE101")
register_all(MAE101_LA, "MAE101")


def generate(count: int, seed: int = 20260927, validate: bool = True):
    return MAE101_LA.generate(count, seed=seed, validate=validate)


def template_ids() -> list[str]:
    return MAE101_LA.template_ids()
