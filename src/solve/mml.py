"""Giải từng bước MAI391: hình học giải tích, giải tích vector, tối ưu, xác suất, PCA, SVM."""

from __future__ import annotations

import sympy as sp

from src.core.schema import Item
from src.solve.base import Solution, Step, answer_list, mat, show, solver, sympy_matrix, vec


def _vector(values) -> list:
    return [sp.nsimplify(sp.sympify(v)) for v in values]


def _function(item: Item) -> tuple[sp.Expr, list[sp.Symbol]]:
    names = sp.symbols(item.meta.get("vars") or ["x", "y"])
    return sp.sympify(item.meta["f"], locals={str(s): s for s in names}), list(names)


@solver("norm")
def _norm(item: Item) -> Solution:
    v = _vector(item.meta["vector"])
    order = item.meta.get("ord", 2)
    if order == 1:
        value = sum(abs(a) for a in v)
        return Solution(theory="Chuẩn L1 là tổng trị tuyệt đối các thành phần.", formula="‖x‖₁ = Σ|xᵢ|",
                        steps=[Step("Cộng trị tuyệt đối các thành phần", "‖x‖₁ = Σ|xᵢ|",
                                    " + ".join(f"|{show(a)}|" for a in v), f"‖x‖₁ = {show(value)}")],
                        answer=sp.sstr(value))
    squares = sum(a ** 2 for a in v)
    value = sp.sqrt(squares)
    return Solution(theory="Chuẩn Euclid (L2) là độ dài vector: căn của tổng bình phương các thành phần.",
                    formula="‖x‖₂ = √(Σ xᵢ²)",
                    steps=[Step("Bình phương từng thành phần rồi cộng lại", "Σ xᵢ²",
                                " + ".join(f"({show(a)})²" for a in v), f"Σ xᵢ² = {show(squares)}"),
                           Step("Lấy căn bậc hai", "‖x‖₂ = √(Σ xᵢ²)", f"√{show(squares)}", f"‖x‖₂ = {show(value)}")],
                    answer=sp.sstr(value))


@solver("inner_product")
def _inner_product(item: Item) -> Solution:
    u, v = _vector(item.meta["u"]), _vector(item.meta["v"])
    value = sum(a * b for a, b in zip(u, v))
    return Solution(theory="Tích vô hướng là tổng các tích thành phần tương ứng; bằng 0 thì hai vector trực giao.",
                    formula="⟨u, v⟩ = Σ uᵢvᵢ",
                    steps=[Step("Nhân các thành phần tương ứng rồi cộng", "⟨u, v⟩ = Σ uᵢvᵢ",
                                " + ".join(f"({show(a)})({show(b)})" for a, b in zip(u, v)), f"⟨u, v⟩ = {show(value)}"),
                           Step("Kết luận về tính trực giao", "⟨u, v⟩ = 0 ⇔ u ⊥ v", "",
                                "u ⊥ v" if value == 0 else "u, v không trực giao")],
                    answer=sp.sstr(value))


@solver("angle_cos")
def _angle_cos(item: Item) -> Solution:
    u, v = _vector(item.meta["u"]), _vector(item.meta["v"])
    dot = sum(a * b for a, b in zip(u, v))
    nu, nv = sp.sqrt(sum(a ** 2 for a in u)), sp.sqrt(sum(b ** 2 for b in v))
    value = sp.nsimplify(sp.simplify(dot / (nu * nv)))
    return Solution(theory="Góc giữa hai vector suy ra từ tích vô hướng chia cho tích hai độ dài.",
                    formula="cos θ = ⟨u, v⟩ / (‖u‖·‖v‖)",
                    steps=[Step("Tính tích vô hướng", "⟨u, v⟩ = Σ uᵢvᵢ", "", f"⟨u, v⟩ = {show(dot)}"),
                           Step("Tính độ dài hai vector", "‖u‖ = √(Σ uᵢ²)", "", f"‖u‖ = {show(nu)}, ‖v‖ = {show(nv)}"),
                           Step("Chia tích vô hướng cho tích hai độ dài", "cos θ = ⟨u, v⟩ / (‖u‖·‖v‖)",
                                f"cos θ = {show(dot)} / ({show(nu)}·{show(nv)})", f"cos θ = {show(value)}")],
                    answer=sp.sstr(value))


@solver("projection")
def _projection(item: Item) -> Solution:
    x, b = _vector(item.meta["x"]), _vector(item.meta["b"])
    dot = sum(p * q for p, q in zip(x, b))
    bb = sum(q ** 2 for q in b)
    coef = sp.Rational(dot, bb) if bb else 0
    proj = [coef * q for q in b]
    return Solution(theory="Hình chiếu của x lên đường thẳng sinh bởi b là bội của b sao cho phần dư vuông góc với b.",
                    formula="π(x) = (⟨x, b⟩ / ⟨b, b⟩)·b",
                    steps=[Step("Tính ⟨x, b⟩ và ⟨b, b⟩", "", "", f"⟨x, b⟩ = {show(dot)}, ⟨b, b⟩ = {show(bb)}"),
                           Step("Tính hệ số chiếu", "λ = ⟨x, b⟩ / ⟨b, b⟩", f"λ = {show(dot)} / {show(bb)}",
                                f"λ = {show(coef)}"),
                           Step("Nhân hệ số với b", "π(x) = λ·b", f"{show(coef)}·{vec(b)}", f"π(x) = {vec(proj)}")],
                    answer=answer_list(proj))


@solver("svm_margin")
def _svm_margin(item: Item) -> Solution:
    w = _vector(item.meta["w"])
    norm = sp.sqrt(sum(a ** 2 for a in w))
    value = sp.nsimplify(2 / norm)
    return Solution(theory="Với SVM lề cứng chuẩn hoá (wᵀx + b = ±1), độ rộng lề là khoảng cách giữa hai siêu phẳng lề.",
                    formula="lề = 2 / ‖w‖",
                    steps=[Step("Tính ‖w‖", "‖w‖ = √(Σ wᵢ²)", " + ".join(f"({show(a)})²" for a in w), f"‖w‖ = {show(norm)}"),
                           Step("Áp dụng công thức độ rộng lề", "lề = 2 / ‖w‖", f"2 / {show(norm)}",
                                f"lề = {show(value)}")],
                    answer=sp.sstr(value))


@solver("gradient")
def _gradient(item: Item) -> Solution:
    f, names = _function(item)
    grads = [sp.diff(f, n) for n in names]
    return Solution(theory="Gradient là vector các đạo hàm riêng; khi lấy đạo hàm theo một biến, coi các biến khác là hằng.",
                    formula="∇f = (∂f/∂x, ∂f/∂y)",
                    steps=[*(Step(f"Tính đạo hàm riêng theo {n}, coi các biến còn lại là hằng số", f"∂f/∂{n}", "",
                                  f"∂f/∂{n} = {show(g)}") for n, g in zip(names, grads)),
                           Step("Ghép thành vector gradient", "∇f = (∂f/∂x, ∂f/∂y)", "", f"∇f = {vec(grads)}")],
                    answer=answer_list(grads))


@solver("partial")
def _partial(item: Item) -> Solution:
    f, names = _function(item)
    var = sp.Symbol(item.meta["var"])
    value = sp.diff(f, var)
    others = ", ".join(str(n) for n in names if n != var)
    return Solution(theory="Đạo hàm riêng theo một biến: coi mọi biến khác như hằng số.",
                    formula=f"∂f/∂{var}",
                    steps=[Step(f"Coi {others} là hằng số", "", ""),
                           Step(f"Đạo hàm từng số hạng theo {var}", "(xⁿ)' = nxⁿ⁻¹",
                                " ; ".join(f"∂({show(t)})/∂{var} = {show(sp.diff(t, var))}" for t in sp.Add.make_args(f)),
                                f"∂f/∂{var} = {show(value)}")],
                    answer=sp.sstr(value))


@solver("jacobian")
def _jacobian(item: Item) -> Solution:
    names = sp.symbols(item.meta.get("vars") or ["x", "y"])
    F = sp.Matrix([sp.sympify(c, locals={str(s): s for s in names}) for c in item.meta["F"]])
    J = F.jacobian(names)
    return Solution(theory="Ma trận Jacobi: hàng i là gradient của thành phần thứ i (hàng = hàm, cột = biến).",
                    formula="Jᵢⱼ = ∂Fᵢ/∂xⱼ",
                    steps=[*(Step(f"Hàng {i + 1}: đạo hàm riêng của F{i + 1} = {show(F[i])} theo từng biến", "", "",
                                  vec(J.row(i))) for i in range(J.rows)),
                           Step("Xếp các hàng thành ma trận", "Jᵢⱼ = ∂Fᵢ/∂xⱼ", "", f"J = {mat(J.tolist())}")],
                    answer="[" + ", ".join(answer_list(row) for row in J.tolist()) + "]")


@solver("chain")
def _chain(item: Item) -> Solution:
    t, x, y = sp.symbols("t x y")
    f, xt, yt = x ** 2 + y ** 2, t, t ** 2
    value = sp.expand(sp.diff(f, x).subs({x: xt, y: yt}) * sp.diff(xt, t)
                      + sp.diff(f, y).subs({x: xt, y: yt}) * sp.diff(yt, t))
    return Solution(theory="Quy tắc dây chuyền nhiều biến: cộng các đường đi từ f qua từng biến trung gian.",
                    formula="df/dt = ∂f/∂x·dx/dt + ∂f/∂y·dy/dt",
                    steps=[Step("Tính các đạo hàm riêng của f", "", "", "∂f/∂x = 2x, ∂f/∂y = 2y"),
                           Step("Tính đạo hàm của các biến trung gian theo t", "", "", "dx/dt = 1, dy/dt = 2t"),
                           Step("Ghép theo quy tắc dây chuyền rồi thay x = t, y = t²",
                                "df/dt = ∂f/∂x·dx/dt + ∂f/∂y·dy/dt", "2t·1 + 2t²·2t", f"df/dt = {show(value)}")],
                    answer=sp.sstr(value))


def _moments(item: Item):
    values = [sp.nsimplify(v) for v in item.meta["values"]]
    probs = [sp.nsimplify(sp.sympify(p)) for p in item.meta["probs"]]
    mean = sum(v * p for v, p in zip(values, probs))
    second = sum(v ** 2 * p for v, p in zip(values, probs))
    return values, probs, mean, second


@solver("expectation")
def _expectation(item: Item) -> Solution:
    values, probs, mean, _ = _moments(item)
    return Solution(theory="Kỳ vọng là trung bình có trọng số: mỗi giá trị nhân với xác suất của nó.",
                    formula="E[X] = Σ xᵢ·pᵢ",
                    steps=[Step("Nhân từng giá trị với xác suất rồi cộng", "E[X] = Σ xᵢ·pᵢ",
                                " + ".join(f"{show(v)}·{show(p)}" for v, p in zip(values, probs)), f"E[X] = {show(mean)}")],
                    answer=sp.sstr(mean))


@solver("variance")
def _variance(item: Item) -> Solution:
    values, probs, mean, second = _moments(item)
    value = second - mean ** 2
    return Solution(theory="Phương sai đo độ phân tán quanh kỳ vọng.", formula="Var(X) = E[X²] − (E[X])²",
                    steps=[Step("Tính E[X]", "E[X] = Σ xᵢpᵢ",
                                " + ".join(f"{show(v)}·{show(p)}" for v, p in zip(values, probs)), f"E[X] = {show(mean)}"),
                           Step("Tính E[X²]", "E[X²] = Σ xᵢ²pᵢ",
                                " + ".join(f"{show(v)}²·{show(p)}" for v, p in zip(values, probs)), f"E[X²] = {show(second)}"),
                           Step("Áp dụng công thức phương sai", "Var(X) = E[X²] − (E[X])²",
                                f"{show(second)} − ({show(mean)})²", f"Var(X) = {show(value)}")],
                    answer=sp.sstr(value))


@solver("gd_step")
def _gd_step(item: Item) -> Solution:
    f, names = _function(item)
    x0 = _vector(item.meta["x0"])
    lr = sp.nsimplify(sp.sympify(item.meta["lr"]))
    grads = [sp.diff(f, n) for n in names]
    at = [g.subs(dict(zip(names, x0))) for g in grads]
    x1 = [a - lr * g for a, g in zip(x0, at)]
    return Solution(theory="Gradient descent đi NGƯỢC chiều gradient, bước dài η (tốc độ học).",
                    formula="x₁ = x₀ − η·∇f(x₀)",
                    steps=[Step("Tính gradient tổng quát", "∇f = (∂f/∂x, ∂f/∂y)", "", f"∇f = {vec(grads)}"),
                           Step("Thay x₀ vào gradient", "∇f(x₀)", f"x₀ = {vec(x0)}", f"∇f(x₀) = {vec(at)}"),
                           Step("Cập nhật theo công thức gradient descent", "x₁ = x₀ − η·∇f(x₀)",
                                f"{vec(x0)} − {show(lr)}·{vec(at)}", f"x₁ = {vec(x1)}")],
                    answer=answer_list(x1))


@solver("stationary")
def _stationary(item: Item) -> Solution:
    f, names = _function(item)
    grads = [sp.diff(f, n) for n in names]
    point = sp.solve(grads, names, dict=True)[0]
    values = [point[n] for n in names]
    return Solution(theory="Điểm dừng là nơi gradient bằng vector 0.", formula="∇f = 0",
                    steps=[Step("Tính các đạo hàm riêng", "∇f = (∂f/∂x, ∂f/∂y)", "", f"∇f = {vec(grads)}"),
                           Step("Cho từng đạo hàm riêng bằng 0 và giải hệ", "∇f = 0",
                                ", ".join(f"{show(g)} = 0" for g in grads),
                                ", ".join(f"{n} = {show(point[n])}" for n in names))],
                    answer=answer_list(values))


@solver("least_squares")
def _least_squares(item: Item) -> Solution:
    X = sympy_matrix(item.meta["X"])
    y = sp.Matrix(_vector(item.meta["y"]))
    XtX, Xty = X.T * X, X.T * y
    theta = XtX.LUsolve(Xty)
    return Solution(theory="Bình phương tối thiểu: θ làm nhỏ nhất ‖y − Xθ‖², thoả phương trình chuẩn.",
                    formula="XᵀXθ = Xᵀy",
                    steps=[Step("Tính XᵀX", "", "", f"XᵀX = {mat(XtX.tolist())}"),
                           Step("Tính Xᵀy", "", "", f"Xᵀy = {vec(list(Xty))}"),
                           Step("Giải phương trình chuẩn XᵀXθ = Xᵀy", "θ = (XᵀX)⁻¹Xᵀy", "", f"θ = {vec(list(theta))}")],
                    answer=answer_list(list(theta)))


@solver("pca_ratio")
def _pca_ratio(item: Item) -> Solution:
    S = sympy_matrix(item.meta["matrix"])
    k = item.meta.get("k", 1)
    eig = sorted((v for v, mult in S.eigenvals().items() for _ in range(mult)), key=lambda v: -sp.N(v))
    total = sum(eig)
    value = sp.nsimplify(sum(eig[:k]) / total)
    return Solution(theory="Mỗi thành phần chính giải thích một lượng phương sai bằng trị riêng tương ứng.",
                    formula="tỉ lệ = λ₁ / Σ λᵢ",
                    steps=[Step("Tìm các trị riêng của ma trận hiệp phương sai, xếp giảm dần", "det(S − λI) = 0", "",
                                f"λ = {', '.join(map(show, eig))}"),
                           Step("Lấy trị riêng lớn nhất chia cho tổng (= vết của S)", "λ₁ / Σ λᵢ",
                                f"{show(sum(eig[:k]))} / {show(total)}", f"tỉ lệ = {show(value)}")],
                    answer=sp.sstr(value))
