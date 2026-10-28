"""Giải từng bước MAE101 phần giải tích: giới hạn, đạo hàm, tích phân."""

from __future__ import annotations

import sympy as sp

from src.core.schema import Item
from src.solve.base import Solution, Step, show, solver

X = sp.Symbol("x")
C = sp.Symbol("C")


def _expr(text: str) -> sp.Expr:
    return sp.sympify(text, locals={"x": X})


# --------------------------------------------------------------------------
# Giới hạn
# --------------------------------------------------------------------------

@solver("limit")
def _limit(item: Item) -> Solution:
    m = item.meta
    f = _expr(m["expr"])
    point = sp.oo if str(m["point"]) == "oo" else sp.sympify(m["point"])
    value = sp.limit(f, X, point)
    kind = m.get("indeterminate")
    where = "x → ∞" if point == sp.oo else f"x → {show(point)}"

    if kind == "oo/oo":
        numer, denom = sp.fraction(sp.together(f))
        degree = sp.degree(denom, X)
        top = sp.expand(numer / X ** degree)
        bottom = sp.expand(denom / X ** degree)
        steps = [
            Step("Thay thử: tử và mẫu cùng tiến ra vô cùng, dạng ∞/∞", "", f"{where}: dạng ∞/∞"),
            Step("Chia cả tử và mẫu cho luỹ thừa cao nhất của mẫu",
                 "chia cho xⁿ, n = bậc của mẫu", f"chia cho {show(X ** degree)}: ({show(top)}) / ({show(bottom)})"),
            Step("Cho x → ∞: các số hạng 1/xᵏ tiến về 0", "1/xᵏ → 0",
                 "", f"giới hạn = {show(value)}"),
        ]
        theory = "Giới hạn ở vô cùng của phân thức: so sánh bậc của tử và mẫu."
        formula = "bậc tử = bậc mẫu ⇒ giới hạn = tỉ số hệ số cao nhất"
    elif kind == "0/0":
        if f.has(sp.sqrt):
            numer, denom = sp.fraction(sp.together(f))
            conj = sp.Add(*(t if t.has(sp.sqrt) else -t for t in sp.Add.make_args(sp.expand(numer))))
            simplified = sp.simplify(f)
            steps = [
                Step("Thay x vào: tử và mẫu đều bằng 0, dạng vô định 0/0", "0/0 chưa phải là một giá trị",
                     f"{where}: dạng 0/0"),
                Step("Nhân cả tử và mẫu với biểu thức liên hợp để khử căn",
                     "(√a − b)(√a + b) = a − b²", f"liên hợp của tử: {show(conj)}"),
                Step("Rút gọn nhân tử gây ra 0/0", "", f"biểu thức sau rút gọn: {show(simplified)}"),
                Step("Thay x vào biểu thức đã rút gọn", "", f"{show(simplified.subs(X, point))}",
                     f"giới hạn = {show(value)}"),
            ]
            theory = "Dạng 0/0 có căn: nhân liên hợp để làm mất căn ở tử rồi rút gọn."
            formula = "(√a − b)(√a + b) = a − b²"
        else:
            numer, denom = sp.fraction(sp.together(f))
            simplified = sp.cancel(f)
            steps = [
                Step("Thay x vào: tử và mẫu đều bằng 0, dạng vô định 0/0", "0/0 chưa phải là một giá trị",
                     f"{where}: dạng 0/0"),
                Step("Phân tích tử và mẫu thành nhân tử", "",
                     f"({show(sp.factor(numer))}) / ({show(sp.factor(denom))})"),
                Step("Rút gọn nhân tử chung (x − a)", "", f"biểu thức sau rút gọn: {show(simplified)}"),
                Step("Thay x vào biểu thức đã rút gọn", "", show(simplified.subs(X, point)),
                     f"giới hạn = {show(value)}"),
            ]
            theory = "Dạng 0/0 của phân thức đa thức: tử và mẫu có chung nhân tử (x − a), rút gọn rồi thay số."
            formula = "lim f/g = lim (f/(x − a)) / (g/(x − a))"
    else:
        steps = [
            Step("Kiểm tra hàm liên tục tại điểm (mẫu khác 0)", "f liên tục tại a ⇒ lim f(x) = f(a)",
                 f"{where}"),
            Step("Thay trực tiếp x vào biểu thức", "lim f(x) = f(a)",
                 f"f({show(point)}) = {show(f.subs(X, point))}", f"giới hạn = {show(value)}"),
        ]
        theory = "Hàm sơ cấp liên tục trên miền xác định: giới hạn bằng giá trị của hàm tại điểm đó."
        formula = "lim_{x→a} f(x) = f(a)"
    return Solution(theory=theory, formula=formula, steps=steps, answer=sp.sstr(value))


# --------------------------------------------------------------------------
# Đạo hàm
# --------------------------------------------------------------------------

@solver("derivative")
def _derivative(item: Item) -> Solution:
    m = item.meta
    f = _expr(m["expr"])
    rule = m.get("rule")
    derivative = sp.simplify(sp.diff(f, X))
    steps: list[Step] = []

    if rule == "product":
        u, v = sp.Mul.make_args(f)[0], sp.Mul(*sp.Mul.make_args(f)[1:])
        steps = [
            Step("Nhận dạng tích của hai hàm u·v", "(u·v)' = u'·v + u·v'", f"u = {show(u)}, v = {show(v)}"),
            Step("Tính đạo hàm từng hàm", "", f"u' = {show(sp.diff(u, X))}, v' = {show(sp.diff(v, X))}"),
            Step("Ghép theo quy tắc tích", "(u·v)' = u'·v + u·v'",
                 f"({show(sp.diff(u, X))})·({show(v)}) + ({show(u)})·({show(sp.diff(v, X))})",
                 f"f'(x) = {show(sp.expand(sp.diff(f, X)))}"),
        ]
        theory, formula = "Đạo hàm của một tích KHÔNG phải tích các đạo hàm.", "(u·v)' = u'v + uv'"
    elif rule == "quotient":
        u, v = sp.fraction(sp.together(f))
        steps = [
            Step("Nhận dạng thương u/v", "(u/v)' = (u'v − uv') / v²", f"u = {show(u)}, v = {show(v)}"),
            Step("Tính đạo hàm từng hàm", "", f"u' = {show(sp.diff(u, X))}, v' = {show(sp.diff(v, X))}"),
            Step("Ghép theo quy tắc thương rồi rút gọn tử", "(u/v)' = (u'v − uv') / v²",
                 f"(({show(sp.diff(u, X))})({show(v)}) − ({show(u)})({show(sp.diff(v, X))})) / ({show(v)})²",
                 f"f'(x) = {show(derivative)}"),
        ]
        theory, formula = "Đạo hàm của thương: chú ý dấu trừ và mẫu bình phương.", "(u/v)' = (u'v − uv')/v²"
    elif rule == "chain":
        u = sp.Symbol("u")
        core = f
        scale = sp.Integer(1)
        if isinstance(f, sp.Mul):                      # 3·sin(...) : hằng số đứng ngoài
            scale, core = f.as_independent(X)
        inner = core.base if isinstance(core, sp.Pow) else core.args[0]
        outer_u = scale * core.subs(inner, u)
        steps = [
            Step("Nhận dạng hàm hợp f(g(x)): xác định hàm ngoài và hàm trong", "[f(g(x))]' = f'(g(x))·g'(x)",
                 f"hàm ngoài: {show(outer_u)}, hàm trong: u = {show(inner)}"),
            Step("Đạo hàm hàm ngoài theo u, giữ nguyên u", "",
                 f"d/du ({show(outer_u)}) = {show(sp.diff(outer_u, u))}"),
            Step("Đạo hàm hàm trong", "", f"u' = {show(sp.diff(inner, X))}"),
            Step("Nhân hai kết quả lại (quy tắc dây chuyền)", "[f(g(x))]' = f'(g(x))·g'(x)", "",
                 f"f'(x) = {show(derivative)}"),
        ]
        theory, formula = "Quy tắc dây chuyền: đạo hàm ngoài nhân đạo hàm trong — hay quên nhân g'(x).", \
            "[f(g(x))]' = f'(g(x))·g'(x)"
    else:
        terms = sp.Add.make_args(sp.expand(f))
        steps = [
            Step("Tách thành tổng các số hạng, đạo hàm từng số hạng", "(f + g)' = f' + g'",
                 " ; ".join(f"({show(t)})' = {show(sp.diff(t, X))}" for t in terms)),
            Step("Cộng các đạo hàm lại", "", "", f"f'(x) = {show(sp.expand(sp.diff(f, X)))}"),
        ]
        theory = "Đạo hàm các hàm sơ cấp: (xⁿ)' = nxⁿ⁻¹, (eˣ)' = eˣ, (ln x)' = 1/x, (sin x)' = cos x."
        formula = "(xⁿ)' = n·xⁿ⁻¹"

    answer = derivative
    if "point" in m:
        point = sp.sympify(m["point"])
        answer = sp.simplify(derivative.subs(X, point))
        steps.append(Step("Thay x vào f'(x)", "", f"f'({show(point)}) = {show(derivative.subs(X, point))}",
                          f"f'({show(point)}) = {show(answer)}"))
    return Solution(theory=theory, formula=formula, steps=steps, answer=sp.sstr(answer))


# --------------------------------------------------------------------------
# Tích phân
# --------------------------------------------------------------------------

INTEGRAL_THEORY = {
    "power": ("Quy tắc luỹ thừa: ∫ xⁿ dx = xⁿ⁺¹/(n + 1) + C, với n ≠ −1.", "∫ xⁿ dx = xⁿ⁺¹/(n + 1) + C"),
    "polynomial": ("Tích phân có tính tuyến tính: tách tổng, đưa hằng số ra ngoài, áp quy tắc luỹ thừa.",
                   "∫ (af + bg) dx = a∫f dx + b∫g dx"),
    "root": ("Viết căn dưới dạng luỹ thừa hữu tỉ √x = x^(1/2) rồi dùng quy tắc luỹ thừa.",
             "∫ xⁿ dx = xⁿ⁺¹/(n + 1) + C"),
    "negative_power": ("Viết 1/xⁿ = x⁻ⁿ rồi dùng quy tắc luỹ thừa (n ≠ 1).", "∫ xⁿ dx = xⁿ⁺¹/(n + 1) + C"),
    "exp_linear": ("Nguyên hàm của eˣ là chính nó.", "∫ eˣ dx = eˣ + C"),
    "trig_linear": ("Với hàm hợp tuyến tính sin(ax + b), nguyên hàm phải chia cho a.",
                    "∫ sin(ax + b) dx = −cos(ax + b)/a + C"),
    "reciprocal_linear": ("∫ 1/(ax + b) dx = ln|ax + b|/a + C — nhớ chia cho a.", "∫ dx/(ax + b) = ln|ax + b|/a + C"),
    "sec_squared": ("1/cos²u là đạo hàm của tan u.", "∫ dx/cos²x = tan x + C"),
    "subst_power": ("Đổi biến u = biểu thức bên trong, du = u'(x)dx.", "∫ f(g(x))g'(x) dx = ∫ f(u) du"),
    "subst_exp": ("Đổi biến u = số mũ, du = u'(x)dx.", "∫ f(g(x))g'(x) dx = ∫ f(u) du"),
    "subst_log": ("Tử là đạo hàm của mẫu: đổi biến u = mẫu.", "∫ g'(x)/g(x) dx = ln|g(x)| + C"),
    "parts_exp": ("Tích phân từng phần: chọn u là đa thức (đạo hàm làm nó đơn giản đi).", "∫ u dv = uv − ∫ v du"),
    "parts_trig": ("Tích phân từng phần: chọn u là đa thức, dv là phần lượng giác.", "∫ u dv = uv − ∫ v du"),
    "parts_log": ("Tích phân từng phần: chọn u = ln x (vì đạo hàm 1/x đơn giản).", "∫ u dv = uv − ∫ v du"),
    "partial_fractions": ("Tách phân thức thành tổng các phân thức đơn giản rồi lấy nguyên hàm từng phần.",
                          "A/(x − a) + B/(x − b)"),
}


def _integral_core(item: Item, f: sp.Expr, template: str) -> tuple[list[Step], sp.Expr]:
    """Các bước tìm nguyên hàm F(x) (chưa cộng C). Trả về (bước, F)."""
    F = sp.integrate(f, X)
    steps: list[Step] = []

    if template.startswith("subst"):
        inner = _substitution_inner(f)
        u = sp.Symbol("u")
        du = sp.diff(inner, X)
        in_u = sp.simplify((f / du).subs(inner, u))
        if in_u.has(X):
            in_u = None
        steps.append(Step("Chọn biến mới u là phần bên trong, tính du", "u = g(x), du = g'(x)dx",
                          f"u = {show(inner)}, du = {show(du)} dx"))
        if in_u is not None:
            Fu = sp.integrate(in_u, u)
            steps.append(Step("Viết lại tích phân theo u rồi lấy nguyên hàm", "∫ f(u) du",
                              f"∫ {show(in_u)} du = {show(Fu)}"))
        steps.append(Step("Thay u trở lại theo x", "", f"u = {show(inner)}", f"F(x) = {show(F)}"))
    elif template.startswith("parts"):
        u_part = sp.log(X) if template == "parts_log" else X
        dv = sp.simplify(f / u_part)
        v = sp.integrate(dv, X)
        rest = sp.integrate(sp.simplify(v * sp.diff(u_part, X)), X)
        steps += [
            Step("Chọn u và dv", "∫ u dv = uv − ∫ v du", f"u = {show(u_part)}, dv = {show(dv)} dx"),
            Step("Tính du và v", "", f"du = {show(sp.diff(u_part, X))} dx, v = {show(v)}"),
            Step("Áp dụng công thức từng phần", "∫ u dv = uv − ∫ v du",
                 f"{show(u_part * v)} − ∫ {show(sp.simplify(v * sp.diff(u_part, X)))} dx"),
            Step("Tính tích phân còn lại rồi gộp", "", f"∫ {show(sp.simplify(v * sp.diff(u_part, X)))} dx = {show(rest)}",
                 f"F(x) = {show(sp.simplify(u_part * v - rest))}"),
        ]
        F = sp.simplify(u_part * v - rest)
    elif template == "partial_fractions":
        parts = sp.apart(f, X)
        steps += [
            Step("Tách phân thức thành tổng các phân thức đơn giản", "A/(x − a) + B/(x − b)",
                 f"{show(f)} = {show(parts)}"),
            Step("Lấy nguyên hàm từng phân thức", "∫ dx/(x − a) = ln|x − a|",
                 " ; ".join(f"∫ {show(t)} dx = {show(sp.integrate(t, X))}" for t in sp.Add.make_args(parts)),
                 f"F(x) = {show(F)}"),
        ]
    else:
        terms = sp.Add.make_args(sp.expand(f)) if template == "polynomial" else (f,)
        if template in ("root", "negative_power"):
            steps.append(Step("Viết lại dưới dạng luỹ thừa xⁿ", "√x = x^(1/2), 1/xⁿ = x⁻ⁿ",
                              f"{show(f)} = {show(sp.powsimp(f, force=True))}"))
        steps.append(Step("Lấy nguyên hàm từng số hạng theo công thức cơ bản",
                          INTEGRAL_THEORY.get(template, ("", ""))[1],
                          " ; ".join(f"∫ {show(t)} dx = {show(sp.integrate(t, X))}" for t in terms),
                          f"F(x) = {show(F)}"))
    return steps, F


def _substitution_inner(f: sp.Expr) -> sp.Expr:
    for node in sp.preorder_traversal(f):
        if isinstance(node, sp.exp):
            return node.args[0]
        if isinstance(node, sp.Pow) and node.exp.is_Integer and node.exp > 1 and node.base.has(X) \
                and not node.base.is_Symbol:
            return node.base
    numer, denom = sp.fraction(sp.together(f))
    return denom


@solver("integral")
def _integral(item: Item) -> Solution:
    f = _expr(item.integrand)
    template = item.meta.get("template") or ""
    key = template.replace("definite_", "")
    if template == "definite_subst":
        key = "subst_exp"
    if template == "definite_exp":
        key = "exp_linear"
    theory, formula = INTEGRAL_THEORY.get(
        key, ("Tìm F sao cho F'(x) = f(x), rồi kiểm tra lại bằng cách lấy đạo hàm.", "∫ f(x) dx = F(x) + C ⇔ F'(x) = f(x)"))
    steps, F = _integral_core(item, f, key)

    if item.bounds:
        a, b = (sp.sympify(v) for v in item.bounds)
        value = sp.simplify(F.subs(X, b) - F.subs(X, a))
        steps.append(Step("Áp dụng công thức Newton–Leibniz", "∫ₐᵇ f(x) dx = F(b) − F(a)",
                          f"F({show(b)}) − F({show(a)}) = {show(F.subs(X, b))} − ({show(F.subs(X, a))})",
                          f"= {show(value)}"))
        return Solution(theory="Tích phân xác định: tìm một nguyên hàm F rồi lấy F(b) − F(a). " + theory,
                        formula="∫ₐᵇ f(x) dx = F(b) − F(a)", steps=steps, answer=sp.sstr(value))

    steps.append(Step("Cộng hằng số tích phân C và kiểm tra bằng đạo hàm", "(F(x) + C)' = f(x)",
                      f"({show(F)})' = {show(sp.simplify(sp.diff(F, X)))}", f"{show(F)} + C"))
    return Solution(theory=theory + " Nguyên hàm là một HỌ hàm, luôn có + C.", formula=formula,
                    steps=steps, answer=f"{sp.sstr(F)} + C")
