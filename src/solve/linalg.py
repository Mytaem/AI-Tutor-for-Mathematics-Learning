"""Giải từng bước đại số tuyến tính — dùng chung cho MAE101 và MAI391."""

from __future__ import annotations

import sympy as sp

from src.core.schema import Item
from src.solve.base import Solution, Step, answer_list, mat, show, solver, sympy_matrix, vec

LAM = sp.Symbol("λ")


def _matrix(item: Item) -> sp.Matrix:
    return sympy_matrix(item.meta["matrix"])


def _det_steps(A: sp.Matrix) -> list[Step]:
    if A.shape == (2, 2):
        a, b, c, d = A
        return [Step("Áp dụng công thức định thức 2×2", "det [[a, b], [c, d]] = ad − bc",
                     f"det A = ({show(a)})·({show(d)}) − ({show(b)})·({show(c)})", f"det A = {show(A.det())}")]
    terms = " ".join(
        f"{'+' if j % 2 == 0 else '−'} {show(A[0, j])}·det(M₁{j + 1})" for j in range(A.cols))
    return [Step("Khai triển Laplace theo hàng 1", "det A = Σ (−1)¹⁺ʲ a₁ⱼ det(M₁ⱼ)", terms,
                 f"det A = {show(A.det())}")]


@solver("determinant")
def _determinant(item: Item) -> Solution:
    A = _matrix(item)
    return Solution(theory="Định thức 2×2 bằng tích đường chéo chính trừ tích đường chéo phụ.",
                    formula="det [[a, b], [c, d]] = ad − bc",
                    steps=[Step("Đọc các phần tử của ma trận", "", f"A = {mat(A.tolist())}"), *_det_steps(A)],
                    answer=sp.sstr(A.det()))


@solver("trace")
def _trace(item: Item) -> Solution:
    A = _matrix(item)
    diagonal = [A[i, i] for i in range(min(A.shape))]
    return Solution(theory="Vết là tổng các phần tử trên đường chéo chính (không nhân chéo như định thức).",
                    formula="tr(A) = Σ aᵢᵢ",
                    steps=[Step("Lấy các phần tử trên đường chéo chính", "aᵢᵢ", ", ".join(map(show, diagonal))),
                           Step("Cộng chúng lại", "tr(A) = Σ aᵢᵢ", " + ".join(f"({show(v)})" for v in diagonal),
                                f"tr(A) = {show(A.trace())}")],
                    answer=sp.sstr(A.trace()))


@solver("inverse")
def _inverse(item: Item) -> Solution:
    A = _matrix(item)
    det = A.det()
    steps = [Step("Tính định thức để kiểm tra A có khả nghịch", "A khả nghịch ⇔ det A ≠ 0"), *_det_steps(A)]
    theory = "Ma trận vuông khả nghịch khi và chỉ khi định thức khác 0."
    if det == 0:
        steps.append(Step("Kết luận", "det A = 0 ⇒ A không khả nghịch", "", "A không khả nghịch"))
        return Solution(theory=theory, formula="det A = 0 ⇒ không tồn tại A⁻¹", steps=steps,
                        answer="không khả nghịch")
    inverse = A.inv()
    if A.shape == (2, 2):
        a, b, c, d = A
        steps.append(Step("Lập ma trận phụ hợp: đổi chỗ đường chéo chính, đổi dấu đường chéo phụ",
                          "adj A = [[d, −b], [−c, a]]", f"adj A = {mat([[d, -b], [-c, a]])}"))
        steps.append(Step("Nhân ma trận phụ hợp với 1/det A", "A⁻¹ = (1/det A)·adj A",
                          f"A⁻¹ = (1/{show(det)})·{mat([[d, -b], [-c, a]])}", f"A⁻¹ = {mat(inverse.tolist())}"))
    else:
        steps.append(Step("Khử Gauss–Jordan trên [A | I] tới khi bên trái thành I", "[A | I] → [I | A⁻¹]",
                          "", f"A⁻¹ = {mat(inverse.tolist())}"))
    steps.append(Step("Kiểm tra lại", "A·A⁻¹ = I", "", "A·A⁻¹ = I ✓"))
    return Solution(theory=theory, formula="A⁻¹ = (1/det A)·adj A", steps=steps,
                    answer=answer_list([answer_list(row) for row in inverse.tolist()]).replace("'", ""))


@solver("rank")
def _rank(item: Item) -> Solution:
    A = _matrix(item)
    echelon = A.echelon_form()
    rank = A.rank()
    return Solution(theory="Hạng là số hàng khác 0 sau khi đưa ma trận về dạng bậc thang.",
                    formula="rank A = số hàng khác 0 của dạng bậc thang",
                    steps=[Step("Biến đổi sơ cấp hàng đưa A về dạng bậc thang",
                                "đổi chỗ hàng, nhân hàng với số ≠ 0, cộng bội hàng này vào hàng khác",
                                f"{mat(echelon.tolist())}"),
                           Step("Đếm số hàng khác 0", "", "", f"rank A = {rank}")],
                    answer=str(rank))


def _char_poly_steps(A: sp.Matrix) -> tuple[list[Step], list]:
    poly = sp.factor((A - LAM * sp.eye(A.rows)).det())
    roots = sorted(sp.roots(sp.Poly(poly, LAM)).keys(), key=lambda v: sp.re(sp.N(v)))
    return [
        Step("Lập phương trình đặc trưng", "det(A − λI) = 0",
             f"det({mat((A - LAM * sp.eye(A.rows)).tolist())}) = {show(sp.expand(poly))}"),
        Step("Giải phương trình đặc trưng", "", f"{show(poly)} = 0", f"λ = {', '.join(map(show, roots))}"),
    ], roots


@solver("eigenvalues")
def _eigenvalues(item: Item) -> Solution:
    A = _matrix(item)
    steps, roots = _char_poly_steps(A)
    return Solution(theory="Trị riêng là nghiệm của phương trình đặc trưng det(A − λI) = 0.",
                    formula="det(A − λI) = 0", steps=steps, answer=answer_list(roots))


def _eigenvector_steps(A: sp.Matrix, lam) -> tuple[list[Step], sp.Matrix]:
    shifted = A - lam * sp.eye(A.rows)
    basis = shifted.nullspace()[0]
    scale = next((v for v in basis if v != 0), 1)
    vector = sp.simplify(basis / scale) if all((v / scale).is_rational for v in basis) else basis
    return [
        Step("Lập ma trận A − λI", "A − λI", f"A − {show(lam)}I = {mat(shifted.tolist())}"),
        Step("Giải hệ thuần nhất (A − λI)v = 0", "(A − λI)v = 0",
             f"dạng bậc thang: {mat(shifted.rref()[0].tolist())}"),
        Step("Chọn một nghiệm khác 0 (mọi bội vô hướng đều đúng)", "v ≠ 0", "", f"v = {vec(vector)}"),
    ], vector


@solver("eigenvector", "pca_first")
def _eigenvector(item: Item) -> Solution:
    A = _matrix(item)
    lam = sp.nsimplify(sp.sympify(item.meta["eigenvalue"]))
    steps, vector = _eigenvector_steps(A, lam)
    theory = "Vector riêng ứng với λ là nghiệm khác 0 của (A − λI)v = 0."
    if item.meta.get("task") == "pca_first":
        steps = [Step("Thành phần chính thứ nhất là vector riêng ứng với trị riêng LỚN NHẤT của S",
                      "S·v = λ_max·v", f"λ_max = {show(lam)}"), *steps]
        theory = "PCA: hướng có phương sai lớn nhất là vector riêng của ma trận hiệp phương sai ứng với trị riêng lớn nhất."
    steps.append(Step("Kiểm tra", "A·v = λ·v", f"A·v = {vec(A * vector)}, λ·v = {vec(lam * vector)}", "khớp ✓"))
    return Solution(theory=theory, formula="(A − λI)v = 0", steps=steps, answer=answer_list(list(vector)))


@solver("diagonal_form")
def _diagonal_form(item: Item) -> Solution:
    A = _matrix(item)
    steps, roots = _char_poly_steps(A)
    D = sp.diag(*roots)
    steps.append(Step("Đặt các trị riêng lên đường chéo của D", "A = PDP⁻¹, D = diag(λ₁, …, λₙ)",
                      "", f"D = {mat(D.tolist())}"))
    return Solution(theory="Chéo hoá: D là ma trận chéo chứa các trị riêng, P có các cột là vector riêng tương ứng.",
                    formula="A = PDP⁻¹", steps=steps,
                    answer="[" + ", ".join(answer_list(row) for row in D.tolist()) + "]")


@solver("singular_values")
def _singular_values(item: Item) -> Solution:
    A = _matrix(item)
    AtA = A.T * A
    # Giữ cả bội: A = 4I có hai giá trị kỳ dị 4, 4 chứ không phải một.
    eig = sorted((v for v, mult in AtA.eigenvals().items() for _ in range(mult)), key=lambda v: -sp.N(v))
    sigmas = [sp.sqrt(v) for v in eig]
    return Solution(theory="Giá trị kỳ dị của A là căn bậc hai các trị riêng của AᵀA (luôn ≥ 0).",
                    formula="σᵢ = √λᵢ(AᵀA)",
                    steps=[Step("Tính AᵀA", "AᵀA", "", f"AᵀA = {mat(AtA.tolist())}"),
                           Step("Tìm trị riêng của AᵀA", "det(AᵀA − λI) = 0", "", f"λ = {', '.join(map(show, eig))}"),
                           Step("Lấy căn bậc hai", "σ = √λ", "", f"σ = {', '.join(map(show, sigmas))}")],
                    answer=answer_list(sigmas))


@solver("matrix_product")
def _matrix_product(item: Item) -> Solution:
    left, right = sympy_matrix(item.meta["left"]), sympy_matrix(item.meta["right"])
    product = left * right
    cells = "; ".join(
        f"c{i + 1}{j + 1} = " + " + ".join(f"({show(left[i, k])})({show(right[k, j])})" for k in range(left.cols))
        for i in range(product.rows) for j in range(product.cols))
    return Solution(theory="Phần tử (i, j) của AB là tích vô hướng hàng i của A với cột j của B.",
                    formula="(AB)ᵢⱼ = Σₖ aᵢₖ bₖⱼ",
                    steps=[Step("Kiểm tra kích thước: số cột của A bằng số hàng của B", "",
                                f"{left.rows}×{left.cols} nhân {right.rows}×{right.cols}"),
                           Step("Tính từng phần tử: hàng của A nhân cột của B", "(AB)ᵢⱼ = Σₖ aᵢₖ bₖⱼ", cells,
                                f"AB = {mat(product.tolist())}")],
                    answer="[" + ", ".join(answer_list(row) for row in product.tolist()) + "]")


@solver("linear_system")
def _linear_system(item: Item) -> Solution:
    A, b = sympy_matrix(item.meta["A"]), sp.Matrix([sp.sympify(v) for v in item.meta["b"]])
    names = sp.symbols("x y z")[: A.cols]
    augmented = A.row_join(b)
    reduced = augmented.rref()[0]
    rank_a, rank_ab = A.rank(), augmented.rank()
    steps = [
        Step("Lập ma trận mở rộng [A | b]", "", f"[A | b] = {mat(augmented.tolist())}"),
        Step("Khử Gauss đưa về dạng bậc thang rút gọn", "biến đổi sơ cấp hàng", f"{mat(reduced.tolist())}"),
        Step("So sánh hạng của A và của [A | b]", "Định lý Kronecker–Capelli",
             f"rank A = {rank_a}, rank [A | b] = {rank_ab}, số ẩn = {A.cols}"),
    ]
    theory = ("Định lý Kronecker–Capelli: rank A < rank [A|b] thì vô nghiệm; bằng nhau và bằng số ẩn thì "
              "nghiệm duy nhất; bằng nhau nhưng nhỏ hơn số ẩn thì vô số nghiệm.")
    if rank_a < rank_ab:
        steps.append(Step("Kết luận", "rank A < rank [A | b] ⇒ vô nghiệm", "", "Hệ vô nghiệm"))
        return Solution(theory=theory, formula="rank A < rank [A|b] ⇒ vô nghiệm", steps=steps, answer="vô nghiệm")
    if rank_a == A.cols:
        solution = list(A.LUsolve(b))
        steps.append(Step("Thế ngược để đọc nghiệm duy nhất", "",
                          ", ".join(f"{n} = {show(v)}" for n, v in zip(names, solution)),
                          f"nghiệm: {vec(solution)}"))
        return Solution(theory=theory, formula="rank A = rank [A|b] = n ⇒ nghiệm duy nhất", steps=steps,
                        answer=answer_list(solution))
    params = sp.symbols("s t u")[: A.cols - rank_a]
    general = list(sp.linsolve((A, b), *names))[0]
    free = [n for n in names if n in general[0].free_symbols or any(n in g.free_symbols for g in general)]
    mapping = dict(zip(free, params))
    general = [sp.simplify(g.subs(mapping)) for g in general]
    steps.append(Step("Chọn ẩn tự do làm tham số, biểu diễn ẩn chính theo tham số",
                      f"{A.cols - rank_a} ẩn tự do",
                      ", ".join(f"{n} = {show(p)}" for n, p in mapping.items()),
                      "nghiệm tổng quát: " + vec(general)))
    return Solution(theory=theory, formula="rank A = rank [A|b] < n ⇒ vô số nghiệm", steps=steps,
                    answer=answer_list(general))
