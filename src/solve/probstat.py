"""Giải từng bước MAS291 — xác suất và thống kê.

Dùng lại đúng các hàm của bộ chấm (``_critical``, ``_p_value``) để con số trong
lời giải trùng với con số bộ chấm dùng, không lệch ở chữ số thứ tư.
"""

from __future__ import annotations

import math

import numpy as np
from scipy import stats

from src.core.schema import Item
from src.solve.base import Solution, Step, num, solver
from src.verify.probstat import _critical, _f, _p_value

ALT_VI = {"two-sided": "hai phía", "greater": "một phía bên phải", "less": "một phía bên trái"}


@solver("union")
def _union(item: Item) -> Solution:
    m = item.meta
    pa, pb, pab = _f(m["pa"]), _f(m["pb"]), _f(m["pab"])
    value = pa + pb - pab
    return Solution(
        theory="Quy tắc cộng: cộng hai xác suất thì phần giao A ∩ B bị đếm hai lần, phải trừ đi một lần.",
        formula="P(A ∪ B) = P(A) + P(B) − P(A ∩ B)",
        steps=[
            Step("Xác định dữ kiện đề cho", "", f"P(A) = {num(pa)}, P(B) = {num(pb)}, P(A ∩ B) = {num(pab)}"),
            Step("Áp dụng quy tắc cộng", "P(A ∪ B) = P(A) + P(B) − P(A ∩ B)",
                 f"P(A ∪ B) = {num(pa)} + {num(pb)} − {num(pab)}", f"P(A ∪ B) = {num(value)}"),
        ],
        answer=num(value),
    )


@solver("conditional")
def _conditional(item: Item) -> Solution:
    m = item.meta
    pb, pab = _f(m["pb"]), _f(m["pab"])
    value = pab / pb
    return Solution(
        theory="Xác suất có điều kiện: biết B đã xảy ra thì không gian mẫu thu về B.",
        formula="P(A | B) = P(A ∩ B) / P(B)",
        steps=[
            Step("Xác định đề hỏi xác suất của A khi BIẾT B, tức P(A | B)", "",
                 f"P(A ∩ B) = {num(pab)}, P(B) = {num(pb)}"),
            Step("Áp dụng công thức xác suất có điều kiện", "P(A | B) = P(A ∩ B) / P(B)",
                 f"P(A | B) = {num(pab)} / {num(pb)}", f"P(A | B) = {num(value)}"),
        ],
        answer=num(value),
    )


@solver("indep_and")
def _indep_and(item: Item) -> Solution:
    m = item.meta
    pa, pb = _f(m["pa"]), _f(m["pb"])
    value = pa * pb
    return Solution(
        theory="Hai biến cố độc lập: xảy ra biến cố này không làm thay đổi xác suất của biến cố kia.",
        formula="A, B độc lập ⇒ P(A ∩ B) = P(A)·P(B)",
        steps=[
            Step("Nhận ra đề cho A, B độc lập nên được nhân trực tiếp", "P(A ∩ B) = P(A)·P(B)"),
            Step("Thay số", "", f"P(A ∩ B) = {num(pa)} · {num(pb)}", f"P(A ∩ B) = {num(value)}"),
        ],
        answer=num(value),
    )


def _machines(m) -> tuple[list[float], list[float], list[float]]:
    prior = [_f(p) for p in m["prior"]]
    likelihood = [_f(x) for x in m["likelihood"]]
    return prior, likelihood, [p * x for p, x in zip(prior, likelihood)]


@solver("total_prob")
def _total_prob(item: Item) -> Solution:
    prior, likelihood, joint = _machines(item.meta)
    total = sum(joint)
    terms = " + ".join(f"{num(p)}·{num(x)}" for p, x in zip(prior, likelihood))
    return Solution(
        theory="Công thức xác suất toàn phần: chia theo các trường hợp loại trừ nhau và phủ hết (từng máy).",
        formula="P(L) = Σ P(Máy i)·P(L | Máy i)",
        steps=[
            Step("Lập hệ đầy đủ: mỗi sản phẩm do đúng một máy làm",
                 "P(Máy 1) + P(Máy 2) = 1",
                 ", ".join(f"P(Máy {i}) = {num(p)}, P(L | Máy {i}) = {num(x)}"
                           for i, (p, x) in enumerate(zip(prior, likelihood), start=1))),
            Step("Áp dụng công thức xác suất toàn phần", "P(L) = Σ P(Máy i)·P(L | Máy i)",
                 f"P(L) = {terms}", f"P(L) = {num(total)}"),
        ],
        answer=num(total),
    )


@solver("bayes")
def _bayes(item: Item) -> Solution:
    m = item.meta
    prior, likelihood, joint = _machines(m)
    index = m["index"]
    total = sum(joint)
    value = joint[index] / total
    machine = index + 1
    return Solution(
        theory="Định lý Bayes: đảo chiều điều kiện — biết sản phẩm lỗi, hỏi khả năng nó đến từ máy nào.",
        formula="P(Máy i | L) = P(Máy i)·P(L | Máy i) / P(L)",
        steps=[
            Step("Tính mẫu số P(L) bằng xác suất toàn phần", "P(L) = Σ P(Máy i)·P(L | Máy i)",
                 "P(L) = " + " + ".join(f"{num(p)}·{num(x)}" for p, x in zip(prior, likelihood)),
                 f"P(L) = {num(total)}"),
            Step(f"Tính tử số: xác suất vừa do máy {machine} làm vừa lỗi",
                 f"P(Máy {machine})·P(L | Máy {machine})",
                 f"{num(prior[index])}·{num(likelihood[index])}", num(joint[index])),
            Step("Áp dụng định lý Bayes", f"P(Máy {machine} | L) = tử số / P(L)",
                 f"P(Máy {machine} | L) = {num(joint[index])} / {num(total)}",
                 f"P(Máy {machine} | L) = {num(value)}"),
        ],
        answer=num(value),
    )


@solver("binom_pmf")
def _binom_pmf(item: Item) -> Solution:
    m = item.meta
    n, k, p = m["n"], m["k"], _f(m["p"])
    combos = math.comb(n, k)
    value = float(stats.binom.pmf(k, n, p))
    return Solution(
        theory="Phân phối nhị thức B(n, p): số lần thành công trong n phép thử độc lập, mỗi lần xác suất p.",
        formula="P(X = k) = C(n, k)·pᵏ·(1 − p)ⁿ⁻ᵏ",
        steps=[
            Step("Xác định tham số", "X ~ B(n, p)", f"n = {n}, p = {num(p)}, k = {k}"),
            Step("Tính số tổ hợp C(n, k)", "C(n, k) = n! / (k!(n − k)!)", f"C({n}, {k})", str(combos)),
            Step("Thay vào công thức nhị thức", "P(X = k) = C(n, k)·pᵏ·(1 − p)ⁿ⁻ᵏ",
                 f"P(X = {k}) = {combos}·{num(p)}^{k}·{num(1 - p)}^{n - k}", f"P(X = {k}) = {num(value)}"),
        ],
        answer=num(value),
    )


@solver("binom_cdf")
def _binom_cdf(item: Item) -> Solution:
    m = item.meta
    n, k, p = m["n"], m["k"], _f(m["p"])
    terms = [float(stats.binom.pmf(i, n, p)) for i in range(k + 1)]
    value = float(stats.binom.cdf(k, n, p))
    return Solution(
        theory="'Nhiều nhất k' với biến rời rạc là cộng dồn mọi giá trị từ 0 đến k, KỂ CẢ k.",
        formula="P(X ≤ k) = Σᵢ₌₀ᵏ C(n, i)·pⁱ·(1 − p)ⁿ⁻ⁱ",
        steps=[
            Step("Xác định tham số và các giá trị cần cộng", "X ~ B(n, p)",
                 f"n = {n}, p = {num(p)}; cần P(X = 0), …, P(X = {k})"),
            Step("Tính từng xác suất bằng công thức nhị thức", "P(X = i) = C(n, i)·pⁱ·(1 − p)ⁿ⁻ⁱ",
                 "; ".join(f"P(X = {i}) = {num(t)}" for i, t in enumerate(terms))),
            Step("Cộng dồn", "P(X ≤ k) = P(X = 0) + … + P(X = k)",
                 " + ".join(num(t) for t in terms), f"P(X ≤ {k}) = {num(value)}"),
        ],
        answer=num(value),
    )


@solver("binom_var")
def _binom_var(item: Item) -> Solution:
    m = item.meta
    n, p = m["n"], _f(m["p"])
    value = n * p * (1 - p)
    return Solution(
        theory="Với X ~ B(n, p): E[X] = np và Var(X) = np(1 − p).",
        formula="Var(X) = n·p·(1 − p)",
        steps=[
            Step("Xác định tham số", "X ~ B(n, p)", f"n = {n}, p = {num(p)}"),
            Step("Áp dụng công thức phương sai của nhị thức", "Var(X) = n·p·(1 − p)",
                 f"Var(X) = {n}·{num(p)}·{num(1 - p)}", f"Var(X) = {num(value)}"),
        ],
        answer=num(value),
    )


@solver("poisson_pmf")
def _poisson_pmf(item: Item) -> Solution:
    m = item.meta
    lam, k = _f(m["lam"]), m["k"]
    value = float(stats.poisson.pmf(k, lam))
    return Solution(
        theory="Phân phối Poisson(λ): số sự kiện trong một khoảng thời gian, λ là số trung bình.",
        formula="P(X = k) = e^(−λ)·λᵏ / k!",
        steps=[
            Step("Xác định tham số", "X ~ Poisson(λ)", f"λ = {num(lam)}, k = {k}"),
            Step("Thay vào công thức Poisson", "P(X = k) = e^(−λ)·λᵏ / k!",
                 f"P(X = {k}) = e^(−{num(lam)})·{num(lam)}^{k} / {k}!", f"P(X = {k}) = {num(value)}"),
        ],
        answer=num(value),
    )


@solver("normal_prob")
def _normal_prob(item: Item) -> Solution:
    m = item.meta
    mu, sigma = _f(m["mu"]), _f(m["sigma"])
    a = _f(m["a"]) if m.get("a") is not None else None
    b = _f(m["b"]) if m.get("b") is not None else None
    steps = [Step("Xác định tham số", "X ~ N(μ, σ)", f"μ = {num(mu)}, σ = {num(sigma)}")]
    za = (a - mu) / sigma if a is not None else None
    zb = (b - mu) / sigma if b is not None else None
    zs = "; ".join(f"z = ({num(v)} − {num(mu)}) / {num(sigma)} = {num(z, 4)}"
                   for v, z in ((a, za), (b, zb)) if v is not None)
    steps.append(Step("Chuẩn hoá về Z ~ N(0, 1)", "z = (x − μ) / σ", zs))
    low = float(stats.norm.cdf(za)) if za is not None else 0.0
    high = float(stats.norm.cdf(zb)) if zb is not None else 1.0
    value = high - low
    if a is None:
        work, label = f"P(X < {num(b)}) = Φ({num(zb, 4)})", f"P(X < {num(b)})"
    elif b is None:
        work, label = f"P(X > {num(a)}) = 1 − Φ({num(za, 4)}) = 1 − {num(low, 5)}", f"P(X > {num(a)})"
    else:
        work = f"Φ({num(zb, 4)}) − Φ({num(za, 4)}) = {num(high, 5)} − {num(low, 5)}"
        label = f"P({num(a)} < X < {num(b)})"
    steps.append(Step("Tra bảng phân phối chuẩn Φ(z) rồi tính xác suất",
                      "P(a < X < b) = Φ(z_b) − Φ(z_a)", work, f"{label} = {num(value)}"))
    return Solution(
        theory="Mọi phân phối chuẩn đưa được về chuẩn tắc N(0, 1) bằng phép chuẩn hoá z, rồi tra bảng Φ.",
        formula="z = (x − μ)/σ; P(X < x) = Φ(z)",
        steps=steps, answer=num(value),
    )


@solver("exp_prob")
def _exp_prob(item: Item) -> Solution:
    m = item.meta
    mean, t = _f(m["mean"]), _f(m["t"])
    lam = 1 / mean
    value = math.exp(-t / mean)
    return Solution(
        theory="Phân phối mũ với trung bình μ có tham số λ = 1/μ; xác suất 'sống quá t' là e^(−λt).",
        formula="P(X > t) = e^(−λt), λ = 1/μ",
        steps=[
            Step("Đổi trung bình thành tham số λ", "λ = 1 / μ", f"λ = 1 / {num(mean)}", f"λ = {num(lam)}"),
            Step("Áp dụng công thức hàm sống sót", "P(X > t) = e^(−λt)",
                 f"P(X > {num(t)}) = e^(−{num(lam)}·{num(t)})", f"P(X > {num(t)}) = {num(value)}"),
        ],
        answer=num(value),
    )


@solver("sample_mean")
def _sample_mean(item: Item) -> Solution:
    data = item.meta["data"]
    value = float(np.mean(data))
    return Solution(
        theory="Trung bình mẫu là tổng các giá trị chia cho cỡ mẫu.",
        formula="x̄ = (Σ xᵢ) / n",
        steps=[
            Step("Tính tổng các giá trị và đếm cỡ mẫu", "Σ xᵢ, n",
                 " + ".join(map(str, data)), f"Σ xᵢ = {sum(data)}, n = {len(data)}"),
            Step("Chia tổng cho cỡ mẫu", "x̄ = (Σ xᵢ) / n", f"x̄ = {sum(data)} / {len(data)}", f"x̄ = {num(value)}"),
        ],
        answer=num(value),
    )


@solver("sample_var")
def _sample_var(item: Item) -> Solution:
    data = item.meta["data"]
    n = len(data)
    mean = float(np.mean(data))
    squares = [(x - mean) ** 2 for x in data]
    value = float(np.var(data, ddof=1))
    return Solution(
        theory="Phương sai MẪU chia cho n − 1 (không phải n) để là ước lượng không chệch của phương sai tổng thể.",
        formula="s² = Σ(xᵢ − x̄)² / (n − 1)",
        steps=[
            Step("Tính trung bình mẫu", "x̄ = (Σ xᵢ) / n", f"x̄ = {sum(data)} / {n}", f"x̄ = {num(mean)}"),
            Step("Tính tổng bình phương độ lệch", "Σ(xᵢ − x̄)²",
                 " + ".join(num(s, 4) for s in squares), f"Σ(xᵢ − x̄)² = {num(sum(squares))}"),
            Step("Chia cho n − 1", "s² = Σ(xᵢ − x̄)² / (n − 1)",
                 f"s² = {num(sum(squares))} / {n - 1}", f"s² = {num(value)}"),
        ],
        answer=num(value),
    )


@solver("median")
def _median(item: Item) -> Solution:
    data = sorted(item.meta["data"])
    n = len(data)
    value = float(np.median(data))
    if n % 2:
        middle = f"n = {n} lẻ: lấy giá trị thứ {(n + 1) // 2}"
        work = f"trung vị = {data[n // 2]}"
    else:
        middle = f"n = {n} chẵn: lấy trung bình giá trị thứ {n // 2} và {n // 2 + 1}"
        work = f"trung vị = ({data[n // 2 - 1]} + {data[n // 2]}) / 2"
    return Solution(
        theory="Trung vị là giá trị đứng giữa SAU KHI sắp xếp dữ liệu tăng dần.",
        formula="n lẻ: x₍₍ₙ₊₁₎/₂₎; n chẵn: trung bình hai giá trị giữa",
        steps=[
            Step("Sắp xếp dữ liệu tăng dần", "", ", ".join(map(str, data))),
            Step("Chọn vị trí giữa theo n chẵn hay lẻ", "", middle),
            Step("Lấy giá trị trung vị", "", work, f"trung vị = {num(value)}"),
        ],
        answer=num(value),
    )


@solver("ci_mean")
def _ci_mean(item: Item) -> Solution:
    m = item.meta
    xbar, sd, n, conf = _f(m["xbar"]), _f(m["sd"]), m["n"], _f(m["conf"])
    known = bool(m.get("sigma_known"))
    dist = "z" if known else "t"
    critical = _critical(conf, dist, n - 1)
    se = sd / math.sqrt(n)
    half = critical * se
    low, high = xbar - half, xbar + half
    crit_name = "z_{α/2}" if known else "t_{α/2, n−1}"
    spread = "σ" if known else "s"
    return Solution(
        theory=("σ đã biết thì dùng phân phối z; σ chưa biết (chỉ có s) thì dùng phân phối t với n − 1 bậc tự do."),
        formula=f"x̄ ± {crit_name}·{spread}/√n",
        steps=[
            Step("Chọn phân phối và tra giá trị tới hạn",
                 "σ đã biết → z; σ chưa biết → t(n − 1)",
                 f"độ tin cậy {num(conf * 100)}% → {'z' if known else f't({n - 1})'} = {num(critical, 4)}"),
            Step("Tính sai số chuẩn", f"SE = {spread} / √n", f"SE = {num(sd)} / √{n}", f"SE = {num(se, 4)}"),
            Step("Tính sai số biên", "E = giá trị tới hạn · SE",
                 f"E = {num(critical, 4)} · {num(se, 4)}", f"E = {num(half, 4)}"),
            Step("Lập khoảng tin cậy", "[x̄ − E, x̄ + E]",
                 f"[{num(xbar)} − {num(half, 4)}, {num(xbar)} + {num(half, 4)}]",
                 f"[{num(low, 4)}, {num(high, 4)}]"),
        ],
        answer=f"[{num(low, 4)}, {num(high, 4)}]",
    )


@solver("ci_prop")
def _ci_prop(item: Item) -> Solution:
    m = item.meta
    p, n, conf = _f(m["phat"]), m["n"], _f(m["conf"])
    critical = _critical(conf, "z")
    se = math.sqrt(p * (1 - p) / n)
    half = critical * se
    low, high = p - half, p + half
    return Solution(
        theory="Khoảng tin cậy cho tỉ lệ dùng xấp xỉ chuẩn: p̂ ± z·√(p̂(1 − p̂)/n).",
        formula="p̂ ± z_{α/2}·√(p̂(1 − p̂)/n)",
        steps=[
            Step("Tính tỉ lệ mẫu p̂", "p̂ = số người đồng ý / n", "", f"p̂ = {num(p, 4)}"),
            Step("Tra giá trị tới hạn z", "", f"độ tin cậy {num(conf * 100)}% → z = {num(critical, 4)}"),
            Step("Tính sai số chuẩn", "SE = √(p̂(1 − p̂)/n)",
                 f"SE = √({num(p, 4)}·{num(1 - p, 4)} / {n})", f"SE = {num(se, 4)}"),
            Step("Lập khoảng tin cậy", "[p̂ − z·SE, p̂ + z·SE]",
                 f"[{num(p, 4)} − {num(critical, 4)}·{num(se, 4)}, {num(p, 4)} + {num(critical, 4)}·{num(se, 4)}]",
                 f"[{num(low, 4)}, {num(high, 4)}]"),
        ],
        answer=f"[{num(low, 4)}, {num(high, 4)}]",
    )


@solver("z_stat", "t_stat")
def _test_stat(item: Item) -> Solution:
    m = item.meta
    xbar, mu0, sd, n = _f(m["xbar"]), _f(m["mu0"]), _f(m["sd"]), m["n"]
    letter = "t" if m["task"] == "t_stat" else "z"
    se = sd / math.sqrt(n)
    value = (xbar - mu0) / se
    spread = "s" if letter == "t" else "σ"
    return Solution(
        theory=f"Thống kê kiểm định đo x̄ cách μ₀ bao nhiêu lần sai số chuẩn ({letter} dùng {spread}).",
        formula=f"{letter} = (x̄ − μ₀) / ({spread}/√n)",
        steps=[
            Step("Xác định dữ kiện", "", f"x̄ = {num(xbar)}, μ₀ = {num(mu0)}, {spread} = {num(sd)}, n = {n}"),
            Step("Tính sai số chuẩn", f"SE = {spread} / √n", f"SE = {num(sd)} / √{n}", f"SE = {num(se, 4)}"),
            Step("Tính thống kê kiểm định", f"{letter} = (x̄ − μ₀) / SE",
                 f"{letter} = ({num(xbar)} − {num(mu0)}) / {num(se, 4)}", f"{letter} = {num(value)}"),
        ],
        answer=num(value),
    )


@solver("p_value")
def _p_value_solver(item: Item) -> Solution:
    m = item.meta
    stat, dist, alt = _f(m["stat"]), m["dist"], m.get("alternative", "two-sided")
    value = _p_value(stat, dist, m.get("df"), alt)
    formula = {"two-sided": "p = 2·P(Z > |z|)", "greater": "p = P(Z > z)", "less": "p = P(Z < z)"}[alt]
    if alt == "two-sided":
        work = f"p = 2·(1 − Φ({num(abs(stat))}))"
    elif alt == "greater":
        work = f"p = 1 − Φ({num(stat)})"
    else:
        work = f"p = Φ({num(stat)})"
    return Solution(
        theory="p-value là xác suất, VỚI ĐIỀU KIỆN H₀ đúng, quan sát được thống kê cực đoan như vậy hoặc hơn.",
        formula=formula,
        steps=[
            Step("Xác định loại kiểm định từ giả thuyết đối", "≠ → hai phía; > → phía phải; < → phía trái",
                 f"kiểm định {ALT_VI[alt]}, {dist} = {num(stat)}"),
            Step("Tính p-value theo đúng số đuôi", formula, work, f"p = {num(value)}"),
        ],
        answer=num(value),
    )


@solver("decision")
def _decision(item: Item) -> Solution:
    m = item.meta
    alpha = _f(m["alpha"])
    steps = []
    if "p_value" in m:
        p = _f(m["p_value"])
    else:
        alt = m.get("alternative", "two-sided")
        p = _p_value(_f(m["stat"]), m["dist"], m.get("df"), alt)
        steps.append(Step("Tính p-value từ thống kê kiểm định theo đúng số đuôi",
                          "hai phía: p = 2·P(Z > |z|)", f"{m['dist']} = {m['stat']}, kiểm định {ALT_VI[alt]}",
                          f"p = {num(p)}"))
    reject = p < alpha
    conclusion = "bác bỏ H0" if reject else "không bác bỏ H0"
    return Solution(
        theory="Quy tắc quyết định: p-value < α thì bác bỏ H₀; ngược lại chỉ nói CHƯA ĐỦ CƠ SỞ để bác bỏ, "
               "không nói 'chấp nhận H₀'.",
        formula="p < α ⇒ bác bỏ H₀",
        steps=[
            *steps,
            Step("So sánh p-value với mức ý nghĩa α", "p < α ?",
                 f"{num(p)} {'<' if reject else '≥'} {num(alpha)}"),
            Step("Kết luận", "",
                 "", "Bác bỏ H₀" if reject else "Chưa đủ cơ sở để bác bỏ H₀"),
        ],
        answer=conclusion,
    )


@solver("two_sample_z")
def _two_sample_z(item: Item) -> Solution:
    m = item.meta
    x1, x2, s1, s2, n1, n2 = (_f(m["x1"]), _f(m["x2"]), _f(m["s1"]), _f(m["s2"]), m["n1"], m["n2"])
    variance = s1 ** 2 / n1 + s2 ** 2 / n2
    se = math.sqrt(variance)
    value = (x1 - x2) / se
    return Solution(
        theory="So sánh hai trung bình độc lập: hiệu x̄₁ − x̄₂ chia cho sai số chuẩn của hiệu.",
        formula="z = (x̄₁ − x̄₂) / √(s₁²/n₁ + s₂²/n₂)",
        steps=[
            Step("Tính sai số chuẩn của hiệu hai trung bình", "SE = √(s₁²/n₁ + s₂²/n₂)",
                 f"SE = √({num(s1)}²/{n1} + {num(s2)}²/{n2})", f"SE = {num(se, 4)}"),
            Step("Tính thống kê z", "z = (x̄₁ − x̄₂) / SE",
                 f"z = ({num(x1)} − {num(x2)}) / {num(se, 4)}", f"z = {num(value)}"),
        ],
        answer=num(value),
    )


@solver("reg_slope", "reg_intercept", "correlation")
def _regression(item: Item) -> Solution:
    m = item.meta
    task = m["task"]
    x, y = np.array(m["x"], float), np.array(m["y"], float)
    xm, ym = float(x.mean()), float(y.mean())
    sxy = float(((x - xm) * (y - ym)).sum())
    sxx = float(((x - xm) ** 2).sum())
    syy = float(((y - ym) ** 2).sum())
    slope = sxy / sxx
    intercept = ym - slope * xm
    r = sxy / math.sqrt(sxx * syy)
    steps = [
        Step("Tính trung bình của x và y", "x̄ = Σx/n, ȳ = Σy/n", "", f"x̄ = {num(xm)}, ȳ = {num(ym)}"),
        Step("Tính các tổng độ lệch", "Sxy = Σ(x − x̄)(y − ȳ), Sxx = Σ(x − x̄)²" +
             (", Syy = Σ(y − ȳ)²" if task == "correlation" else ""),
             "", f"Sxy = {num(sxy)}, Sxx = {num(sxx)}" + (f", Syy = {num(syy)}" if task == "correlation" else "")),
    ]
    if task == "correlation":
        steps.append(Step("Tính hệ số tương quan", "r = Sxy / √(Sxx·Syy)",
                          f"r = {num(sxy)} / √({num(sxx)}·{num(syy)})", f"r = {num(r)}"))
        value, theory, formula = r, "r đo mức độ quan hệ TUYẾN TÍNH giữa x và y, nằm trong [−1, 1].", \
            "r = Sxy / √(Sxx·Syy)"
    else:
        steps.append(Step("Tính hệ số góc", "b₁ = Sxy / Sxx", f"b₁ = {num(sxy)} / {num(sxx)}", f"b₁ = {num(slope)}"))
        if task == "reg_intercept":
            steps.append(Step("Tính hệ số chặn", "b₀ = ȳ − b₁·x̄",
                              f"b₀ = {num(ym)} − {num(slope)}·{num(xm)}", f"b₀ = {num(intercept)}"))
        value = slope if task == "reg_slope" else intercept
        theory = "Đường hồi quy bình phương tối thiểu ŷ = b₀ + b₁x đi qua điểm (x̄, ȳ)."
        formula = "b₁ = Sxy/Sxx, b₀ = ȳ − b₁x̄"
    return Solution(theory=theory, formula=formula, steps=steps, answer=num(value))
