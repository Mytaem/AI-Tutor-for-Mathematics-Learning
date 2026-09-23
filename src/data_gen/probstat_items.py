"""Sinh đề MAS291 theo template có tham số.

Đáp án lấy từ chính hàm ``probstat.analytic()`` của bộ chấm, rồi bài sinh ra
phải qua hai cửa mới được nhận: verifier chấm lại, và **đối chứng Monte Carlo**
mà verifier tự chạy. Nhờ cửa thứ hai, một template đặt tham số phi lý (xác suất
giao lớn hơn xác suất lề chẳng hạn) không thể lọt vào ngân hàng đề.

Tham số cố ý gieo ở dạng "đẹp" như đề thi thật: xác suất một hoặc hai chữ số
thập phân, cỡ mẫu tròn, độ tin cậy 90/95/99%. Sinh viên tra bảng bằng tay được
thì đề mới dùng để dạy được.
"""

from __future__ import annotations

import random
from types import SimpleNamespace

from src.core.schema import Subject
from src.data_gen.bank_builder import Registry
from src.verify import probstat as P

MAS291 = Registry(Subject.MAS291, "MAS291")
template = MAS291.template

CONFIDENCES = ["0.90", "0.95", "0.99"]


def analytic_of(meta: dict):
    return P.analytic(SimpleNamespace(meta=meta))


def number(value: float) -> str:
    """Làm tròn 6 chữ số thập phân — đủ chặt để chấm, đủ ngắn để đọc."""
    rounded = round(float(value), 6)
    return str(int(rounded)) if rounded == int(rounded) else f"{rounded:g}"


def draft(meta: dict, statement_vi: str, **extra) -> dict:
    """Đáp án tính từ ``analytic``; kiểu đáp án suy ra từ giá trị trả về."""
    value = analytic_of(meta)
    if isinstance(value, bool):
        return {"meta": meta, "statement_vi": statement_vi, "answer_type": "boolean",
                "answer": "bác bỏ H0" if value else "không bác bỏ H0", **extra}
    if isinstance(value, tuple):
        return {"meta": meta, "statement_vi": statement_vi, "answer_type": "matrix",
                "answer": [f"{value[0]:.4f}", f"{value[1]:.4f}"], **extra}
    return {"meta": meta, "statement_vi": statement_vi, "answer_type": "number",
            "answer": number(value), **extra}


def probability(rng: random.Random, low: int = 10, high: int = 90, step: int = 5) -> str:
    return f"{rng.randrange(low, high + 1, step) / 100:g}"


# --------------------------------------------------------------------------
# Xác suất cơ bản và Bayes
# --------------------------------------------------------------------------

@template("union", ["MAS.PROB.BASIC"], 0.3, "Quy tắc cộng")
def _union(rng: random.Random):
    pa, pb = float(probability(rng, 20, 60)), float(probability(rng, 20, 60))
    pab = round(rng.uniform(0.05, min(pa, pb) - 0.02), 2)
    if pab <= 0:
        return None
    meta = {"task": "union", "pa": f"{pa:g}", "pb": f"{pb:g}", "pab": f"{pab:g}"}
    return draft(meta, f"P(A) = {pa:g}, P(B) = {pb:g}, P(A ∩ B) = {pab:g}. Tính P(A ∪ B)")


@template("conditional", ["MAS.PROB.COND"], 0.4, "Xác suất có điều kiện")
def _conditional(rng: random.Random):
    pa, pb = float(probability(rng, 25, 70)), float(probability(rng, 25, 70))
    pab = round(rng.uniform(0.05, min(pa, pb) - 0.02), 2)
    if pab <= 0:
        return None
    meta = {"task": "conditional", "pa": f"{pa:g}", "pb": f"{pb:g}", "pab": f"{pab:g}"}
    return draft(meta, f"P(A) = {pa:g}, P(B) = {pb:g}, P(A ∩ B) = {pab:g}. Tính P(A | B)")


@template("indep_and", ["MAS.PROB.BASIC"], 0.25, "Biến cố độc lập")
def _indep_and(rng: random.Random):
    pa, pb = probability(rng, 10, 80), probability(rng, 10, 80)
    meta = {"task": "indep_and", "pa": pa, "pb": pb}
    return draft(meta, f"A, B độc lập với P(A) = {pa}, P(B) = {pb}. Tính P(A ∩ B)")


def _two_machines(rng: random.Random) -> tuple[dict, str, str]:
    share = rng.randrange(40, 71, 5) / 100
    rate1 = rng.randrange(1, 5) / 100
    rate2 = rng.randrange(4, 10) / 100
    meta = {"prior": [f"{share:g}", f"{1 - share:g}"], "likelihood": [f"{rate1:g}", f"{rate2:g}"]}
    context = (f"Máy 1 làm {share:.0%} sản phẩm, tỉ lệ lỗi {rate1:.0%}; "
               f"máy 2 làm {1 - share:.0%}, tỉ lệ lỗi {rate2:.0%}")
    return meta, context, f"{rate2:g}"


@template("total_prob", ["MAS.PROB.BAYES"], 0.45, "Công thức xác suất đầy đủ")
def _total_prob(rng: random.Random):
    base, context, _ = _two_machines(rng)
    meta = {"task": "total_prob", **base}
    return draft(meta, f"{context}. Tính xác suất một sản phẩm bị lỗi")


@template("bayes", ["MAS.PROB.BAYES"], 0.6, "Công thức Bayes")
def _bayes(rng: random.Random):
    base, context, _ = _two_machines(rng)
    index = rng.randint(0, 1)
    meta = {"task": "bayes", **base, "index": index}
    return draft(meta, f"{context}. Một sản phẩm bị lỗi — tính xác suất nó do máy {index + 1} làm")


# --------------------------------------------------------------------------
# Phân phối
# --------------------------------------------------------------------------

@template("binom_pmf", ["MAS.DIST.BINOM"], 0.4, "Phân phối nhị thức")
def _binom_pmf(rng: random.Random):
    n, p = rng.choice([8, 10, 12, 15, 20]), probability(rng, 10, 70, 5)
    k = rng.randint(1, min(6, n - 1))
    meta = {"task": "binom_pmf", "n": n, "p": p, "k": k}
    return draft(meta, f"X ~ B(n = {n}, p = {p}). Tính P(X = {k})")


@template("binom_cdf", ["MAS.DIST.BINOM"], 0.5, "Hàm phân phối tích luỹ nhị thức")
def _binom_cdf(rng: random.Random):
    n, p = rng.choice([8, 10, 12, 15, 20]), probability(rng, 10, 70, 5)
    k = rng.randint(1, min(6, n - 1))
    meta = {"task": "binom_cdf", "n": n, "p": p, "k": k}
    return draft(meta, f"X ~ B(n = {n}, p = {p}). Tính P(X ≤ {k})")


@template("binom_var", ["MAS.DIST.BINOM"], 0.3, "Phương sai np(1−p)")
def _binom_var(rng: random.Random):
    n, p = rng.choice([16, 20, 25, 30, 40]), probability(rng, 10, 80, 5)
    meta = {"task": "binom_var", "n": n, "p": p}
    return draft(meta, f"X ~ B(n = {n}, p = {p}). Tính Var(X)")


@template("poisson_pmf", ["MAS.DIST.POIS"], 0.45, "Phân phối Poisson")
def _poisson_pmf(rng: random.Random):
    lam = rng.choice(["1.5", "2", "2.5", "3", "4", "5"])
    k = rng.randint(0, 5)
    meta = {"task": "poisson_pmf", "lam": lam, "k": k}
    return draft(meta, f"Số cuộc gọi trong một giờ X ~ Poisson(λ = {lam}). Tính P(X = {k})")


@template("normal_prob", ["MAS.DIST.NORMAL"], 0.5, "Chuẩn hoá về Z")
def _normal_prob(rng: random.Random):
    mu, sigma = rng.randrange(50, 210, 10), rng.choice([5, 8, 10, 12, 15, 20])
    kind = rng.choice(["below", "above", "between"])
    if kind == "below":
        b = mu + sigma * rng.choice([1, 1.5, 2])
        meta = {"task": "normal_prob", "mu": str(mu), "sigma": str(sigma), "a": None, "b": f"{b:g}"}
        question = f"Tính P(X < {b:g})"
    elif kind == "above":
        a = mu + sigma * rng.choice([-1, 1, 1.5])
        meta = {"task": "normal_prob", "mu": str(mu), "sigma": str(sigma), "a": f"{a:g}", "b": None}
        question = f"Tính P(X > {a:g})"
    else:
        a = mu - sigma
        b = mu + sigma * rng.choice([1, 2])
        meta = {"task": "normal_prob", "mu": str(mu), "sigma": str(sigma), "a": f"{a:g}", "b": f"{b:g}"}
        question = f"Tính P({a:g} < X < {b:g})"
    return draft(meta, f"X ~ N(μ = {mu}, σ = {sigma}). {question}")


@template("exp_prob", ["MAS.DIST.EXP"], 0.45, "Phân phối mũ")
def _exp_prob(rng: random.Random):
    mean, t = rng.choice([2, 3, 4, 5]), rng.choice([1, 2, 3, 6])
    meta = {"task": "exp_prob", "mean": str(mean), "t": str(t)}
    return draft(meta, f"Tuổi thọ linh kiện có phân phối mũ, trung bình {mean} năm. "
                       f"Tính xác suất linh kiện dùng được quá {t} năm")


# --------------------------------------------------------------------------
# Thống kê mô tả
# --------------------------------------------------------------------------

def _sample(rng: random.Random, size: int | None = None) -> list[int]:
    return sorted(rng.randint(1, 20) for _ in range(size or rng.choice([5, 6, 7, 8])))


@template("descriptive", ["MAS.DESC"], 0.25, "Thống kê mô tả")
def _descriptive(rng: random.Random):
    data = _sample(rng)
    task = rng.choice(["sample_mean", "sample_var", "median"])
    meta = {"task": task, "data": data}
    question = {"sample_mean": "Tính trung bình mẫu",
                "sample_var": "Tính phương sai mẫu s²",
                "median": "Tìm trung vị"}[task]
    return draft(meta, f"Mẫu: {', '.join(map(str, data))}. {question}")


# --------------------------------------------------------------------------
# Ước lượng khoảng
# --------------------------------------------------------------------------

@template("ci_mean", ["MAS.CI.MEAN"], 0.55, "Khoảng tin cậy cho trung bình")
def _ci_mean(rng: random.Random):
    xbar = rng.randrange(20, 120, 5)
    sd = rng.choice([4, 5, 8, 10, 12])
    n = rng.choice([16, 25, 36, 49, 64, 100])
    conf = rng.choice(CONFIDENCES)
    known = rng.random() < 0.5
    meta = {"task": "ci_mean", "xbar": str(xbar), "sd": str(sd), "n": n,
            "conf": conf, "sigma_known": known}
    symbol = f"σ = {sd} đã biết" if known else f"s = {sd} (σ chưa biết)"
    return draft(meta, f"x̄ = {xbar}, {symbol}, n = {n}. "
                       f"Tìm khoảng tin cậy {float(conf):.0%} cho μ")


@template("ci_prop", ["MAS.CI.PROP"], 0.55, "Khoảng tin cậy cho tỉ lệ")
def _ci_prop(rng: random.Random):
    n = rng.choice([80, 100, 120, 150, 200])
    successes = rng.randint(int(n * 0.2), int(n * 0.8))
    phat = successes / n
    conf = rng.choice(CONFIDENCES)
    meta = {"task": "ci_prop", "phat": f"{phat:g}", "n": n, "conf": conf}
    return draft(meta, f"Trong mẫu {n} người có {successes} người đồng ý. "
                       f"Tìm khoảng tin cậy {float(conf):.0%} cho tỉ lệ đồng ý")


# --------------------------------------------------------------------------
# Kiểm định giả thuyết
# --------------------------------------------------------------------------

@template("test_stat", ["MAS.HYP.STAT"], 0.5, "Thống kê kiểm định")
def _test_stat(rng: random.Random):
    mu0 = rng.randrange(10, 100, 5)
    diff = rng.choice([-3, -2, -1.5, 1, 1.5, 2, 3])
    xbar = mu0 + diff
    sd = rng.choice([1.2, 2, 4, 5, 8, 10])
    n = rng.choice([16, 25, 36, 49, 64])
    task = rng.choice(["z_stat", "t_stat"])
    meta = {"task": task, "xbar": f"{xbar:g}", "mu0": str(mu0), "sd": f"{sd:g}", "n": n}
    symbol = "σ" if task == "z_stat" else "s"
    name = "z" if task == "z_stat" else "t"
    return draft(meta, f"H₀: μ = {mu0}, {symbol} = {sd:g}, n = {n}, x̄ = {xbar:g}. "
                       f"Tính thống kê kiểm định {name}")


@template("p_value", ["MAS.HYP.PVALUE"], 0.6, "p-value một phía và hai phía")
def _p_value(rng: random.Random):
    stat = round(rng.uniform(1.2, 3.2), 1)
    alternative = rng.choice(["two-sided", "greater", "less"])
    if alternative == "less":
        stat = -stat
    meta = {"task": "p_value", "stat": f"{stat:g}", "dist": "z", "alternative": alternative}
    side = {"two-sided": "hai phía", "greater": "một phía (bên phải)", "less": "một phía (bên trái)"}
    return draft(meta, f"Kiểm định {side[alternative]}, thống kê z = {stat:g}. Tính p-value")


@template("decision", ["MAS.HYP.DECISION"], 0.35, "So p-value với α")
def _decision(rng: random.Random):
    alpha = rng.choice(["0.01", "0.05", "0.1"])
    p_value = round(rng.uniform(0.001, 0.2), 3)
    meta = {"task": "decision", "p_value": f"{p_value:g}", "alpha": alpha}
    return draft(meta, f"p-value = {p_value:g}, mức ý nghĩa α = {alpha}. Kết luận gì về H₀?")


@template("two_sample_z", ["MAS.TWO"], 0.6, "So sánh hai trung bình")
def _two_sample_z(rng: random.Random):
    x1 = rng.randrange(50, 120, 5)
    x2 = x1 - rng.choice([2, 3, 4, 5, 8])
    s1, s2 = rng.choice([8, 10, 12]), rng.choice([8, 10, 12, 15])
    n1, n2 = rng.choice([40, 50, 60]), rng.choice([40, 50, 60, 80])
    meta = {"task": "two_sample_z", "x1": str(x1), "x2": str(x2), "s1": str(s1), "s2": str(s2),
            "n1": n1, "n2": n2}
    return draft(meta, f"Mẫu 1: x̄₁ = {x1}, s₁ = {s1}, n₁ = {n1}. Mẫu 2: x̄₂ = {x2}, s₂ = {s2}, "
                       f"n₂ = {n2}. Tính thống kê z cho H₀: μ₁ = μ₂")


# --------------------------------------------------------------------------
# Hồi quy tuyến tính
# --------------------------------------------------------------------------

@template("regression", ["MAS.REG"], 0.6, "Hồi quy tuyến tính đơn")
def _regression(rng: random.Random):
    size = rng.choice([5, 6, 7])
    x = list(range(1, size + 1))
    slope, intercept = rng.choice([0.5, 1, 1.5, 2, -1]), rng.randint(1, 5)
    y = [max(1, round(intercept + slope * value + rng.choice([-1, 0, 0, 1]))) for value in x]
    if len(set(y)) == 1:
        return None
    task = rng.choice(["reg_slope", "reg_intercept", "correlation"])
    meta = {"task": task, "x": x, "y": y}
    question = {"reg_slope": "Tính hệ số góc b₁ của đường hồi quy y theo x",
                "reg_intercept": "Tính hệ số chặn b₀ của đường hồi quy y theo x",
                "correlation": "Tính hệ số tương quan r"}[task]
    return draft(meta, f"Dữ liệu x = ({', '.join(map(str, x))}), y = ({', '.join(map(str, y))}). {question}")


def generate(count: int, seed: int = 20260923, validate: bool = True):
    return MAS291.generate(count, seed=seed, validate=validate)


def template_ids() -> list[str]:
    return MAS291.template_ids()
