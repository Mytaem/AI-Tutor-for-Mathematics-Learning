"""Bộ chấm Xác suất – Thống kê — MAS291 (Montgomery, Applied Statistics and Probability for Engineers).

Hai điểm khác hẳn các môn khác:

**1. Kiểm chéo bằng Monte Carlo.** Với mọi bài ra một xác suất, giá trị giải
tích (tính bằng công thức / scipy) được đối chiếu với một ước lượng MÔ PHỎNG
độc lập — gieo hàng trăm nghìn lần thí nghiệm ngẫu nhiên rồi đếm. Hai phương
pháp khác hẳn bản chất mà cùng ra một con số thì độ tin cậy của đáp án chuẩn cao
hơn hẳn việc chỉ tin một công thức. Kết quả nằm ở ``VerificationResult.cross_check``.

**2. Dung sai theo thói quen tra bảng.** Sinh viên tra bảng z, bảng t với 3–4
chữ số và làm tròn z về 2 chữ số, nên đáp án lệch vài phần nghìn là bình thường.
Dung sai ở đây: ``max(0.0015, 1% giá trị)`` — đủ rộng cho sai số tra bảng, đủ
hẹp để không nhận nhầm một đáp án sai cách (ví dụ quên nhân 2 ở p-value hai phía).
"""

from __future__ import annotations

import math

import numpy as np
import sympy as sp
from scipy import stats

from src.core.schema import Item, VerificationResult, Submission
from src.verify.base import Verifier, parse_matrix
from src.verify.equivalence import EquivalenceResult, ParseError, parse_math

ERR_UNION_NOSUB = "MAS.PROB.UNION_NOSUB"
ERR_COND_REVERSED = "MAS.PROB.COND_REVERSED"
ERR_JOINT_INSTEAD = "MAS.PROB.JOINT_INSTEAD"
ERR_BAYES_NONORM = "MAS.PROB.BAYES_NONORM"
ERR_CDF_PMF = "MAS.DIST.CDF_PMF"
ERR_OFFBYONE = "MAS.DIST.OFFBYONE"
ERR_TAIL = "MAS.DIST.TAIL"
ERR_NOCOMB = "MAS.BIN.NOCOMB"
ERR_VAR_MEAN = "MAS.BIN.VAR_MEAN"
ERR_NOSTANDARDIZE = "MAS.NORM.NOSTANDARDIZE"
ERR_VAR_AS_SD = "MAS.NORM.VAR_AS_SD"
ERR_RATE_MEAN = "MAS.EXP.RATE_MEAN"
ERR_VAR_N = "MAS.DESC.VAR_N"
ERR_STD_INSTEAD = "MAS.DESC.STD_INSTEAD"
ERR_Z_INSTEAD_T = "MAS.CI.Z_INSTEAD_T"
ERR_CI_NOSQRTN = "MAS.CI.NOSQRTN"
ERR_HYP_NOSQRTN = "MAS.HYP.NOSQRTN"
ERR_HYP_TAIL = "MAS.HYP.TAIL"
ERR_DECISION = "MAS.HYP.DECISION"
ERR_REG_SWAPPED = "MAS.REG.SWAPPED"

PROBSTAT_TASKS = {
    "union", "conditional", "indep_and", "total_prob", "bayes",
    "binom_pmf", "binom_cdf", "binom_var", "poisson_pmf", "normal_prob", "exp_prob",
    "sample_mean", "sample_var", "median", "ci_mean", "ci_prop",
    "z_stat", "t_stat", "p_value", "decision", "two_sample_z",
    "reg_slope", "reg_intercept", "correlation",
}

#: Bài ra một XÁC SUẤT — những bài này có thể và phải được kiểm chéo bằng mô phỏng.
MONTE_CARLO_TASKS = {
    "union", "conditional", "indep_and", "total_prob", "bayes",
    "binom_pmf", "binom_cdf", "poisson_pmf", "normal_prob", "exp_prob", "p_value",
}

MONTE_CARLO_SAMPLES = 400_000
ABS_TOL = 0.0015
REL_TOL = 0.01

REJECT_WORDS = ("bác bỏ", "bac bo", "reject")
KEEP_WORDS = ("không bác bỏ", "khong bac bo", "chưa đủ cơ sở", "chua du co so", "fail to reject",
              "do not reject", "don't reject", "chấp nhận h0", "chap nhan h0", "accept")


def _f(value) -> float:
    return float(sp.N(sp.sympify(value)))


def stat_close(given: float, reference: float) -> bool:
    return abs(given - reference) <= max(ABS_TOL, REL_TOL * abs(reference))


def _ok(detail: str) -> EquivalenceResult:
    return EquivalenceResult(True, "numeric", 0.99, detail)


def _wrong(detail: str) -> EquivalenceResult:
    return EquivalenceResult(False, "numeric", 1.0, detail)


def parse_decision(answer: str) -> bool | None:
    """True = bác bỏ H0, False = không bác bỏ, None = không hiểu. Xét cụm PHỦ ĐỊNH trước."""
    text = answer.strip().lower()
    if any(word in text for word in KEEP_WORDS):
        return False
    if any(word in text for word in REJECT_WORDS):
        return True
    return None


# --------------------------------------------------------------------------
# Giá trị giải tích và các kiểu sai kinh điển
# --------------------------------------------------------------------------

def _p_value(stat: float, dist: str, df: int | None, alternative: str) -> float:
    law = stats.norm if dist == "z" else stats.t(df)
    if alternative == "greater":
        return float(law.sf(stat))
    if alternative == "less":
        return float(law.cdf(stat))
    return float(2 * law.sf(abs(stat)))


def _critical(conf: float, dist: str, df: int | None = None) -> float:
    quantile = 1 - (1 - conf) / 2
    return float(stats.norm.ppf(quantile) if dist == "z" else stats.t.ppf(quantile, df))


def analytic(item: Item):
    """Giá trị đúng, tính lại từ dữ liệu của đề. Số thực, cặp số (khoảng tin cậy) hoặc bool (quyết định)."""
    m, task = item.meta, item.meta["task"]

    if task == "union":
        return _f(m["pa"]) + _f(m["pb"]) - _f(m["pab"])
    if task == "conditional":
        return _f(m["pab"]) / _f(m["pb"])
    if task == "indep_and":
        return _f(m["pa"]) * _f(m["pb"])
    if task == "total_prob":
        return sum(_f(p) * _f(l) for p, l in zip(m["prior"], m["likelihood"]))
    if task == "bayes":
        joint = [_f(p) * _f(l) for p, l in zip(m["prior"], m["likelihood"])]
        return joint[m["index"]] / sum(joint)
    if task == "binom_pmf":
        return float(stats.binom.pmf(m["k"], m["n"], _f(m["p"])))
    if task == "binom_cdf":
        return float(stats.binom.cdf(m["k"], m["n"], _f(m["p"])))
    if task == "binom_var":
        return m["n"] * _f(m["p"]) * (1 - _f(m["p"]))
    if task == "poisson_pmf":
        return float(stats.poisson.pmf(m["k"], _f(m["lam"])))
    if task == "normal_prob":
        law = stats.norm(_f(m["mu"]), _f(m["sigma"]))
        low = law.cdf(_f(m["a"])) if m.get("a") is not None else 0.0
        high = law.cdf(_f(m["b"])) if m.get("b") is not None else 1.0
        return float(high - low)
    if task == "exp_prob":
        return math.exp(-_f(m["t"]) / _f(m["mean"]))
    if task == "sample_mean":
        return float(np.mean(m["data"]))
    if task == "sample_var":
        return float(np.var(m["data"], ddof=1))
    if task == "median":
        return float(np.median(m["data"]))
    if task == "ci_mean":
        dist = "z" if m.get("sigma_known") else "t"
        half = _critical(_f(m["conf"]), dist, m["n"] - 1) * _f(m["sd"]) / math.sqrt(m["n"])
        return (_f(m["xbar"]) - half, _f(m["xbar"]) + half)
    if task == "ci_prop":
        p, n = _f(m["phat"]), m["n"]
        half = _critical(_f(m["conf"]), "z") * math.sqrt(p * (1 - p) / n)
        return (p - half, p + half)
    if task in ("z_stat", "t_stat"):
        return (_f(m["xbar"]) - _f(m["mu0"])) / (_f(m["sd"]) / math.sqrt(m["n"]))
    if task == "p_value":
        return _p_value(_f(m["stat"]), m["dist"], m.get("df"), m.get("alternative", "two-sided"))
    if task == "decision":
        p = _f(m["p_value"]) if "p_value" in m else _p_value(
            _f(m["stat"]), m["dist"], m.get("df"), m.get("alternative", "two-sided"))
        return p < _f(m["alpha"])
    if task == "two_sample_z":
        se = math.sqrt(_f(m["s1"]) ** 2 / m["n1"] + _f(m["s2"]) ** 2 / m["n2"])
        return (_f(m["x1"]) - _f(m["x2"])) / se
    if task in ("reg_slope", "reg_intercept", "correlation"):
        x, y = np.array(m["x"], float), np.array(m["y"], float)
        sxy = float(((x - x.mean()) * (y - y.mean())).sum())
        sxx = float(((x - x.mean()) ** 2).sum())
        syy = float(((y - y.mean()) ** 2).sum())
        slope = sxy / sxx
        if task == "reg_slope":
            return slope
        if task == "reg_intercept":
            return float(y.mean() - slope * x.mean())
        return sxy / math.sqrt(sxx * syy)
    raise KeyError(f"Chưa có công thức cho task {task!r}")


def mistakes(item: Item) -> list[tuple[object, str]]:
    """Giá trị mà mỗi kiểu sai kinh điển sẽ cho ra, kèm mã lỗi tương ứng."""
    m, task = item.meta, item.meta["task"]
    out: list[tuple[object, str]] = []

    if task == "union":
        out.append((_f(m["pa"]) + _f(m["pb"]), ERR_UNION_NOSUB))
    elif task == "conditional":
        if "pa" in m:
            out.append((_f(m["pab"]) / _f(m["pa"]), ERR_COND_REVERSED))
        out.append((_f(m["pab"]), ERR_JOINT_INSTEAD))
    elif task == "bayes":
        out.append((_f(m["likelihood"][m["index"]]), ERR_COND_REVERSED))
        out.append((_f(m["prior"][m["index"]]) * _f(m["likelihood"][m["index"]]), ERR_BAYES_NONORM))
    elif task == "binom_pmf":
        k, n, p = m["k"], m["n"], _f(m["p"])
        out.append((p**k * (1 - p) ** (n - k), ERR_NOCOMB))
        out.append((float(stats.binom.cdf(k, n, p)), ERR_CDF_PMF))
    elif task == "binom_cdf":
        k, n, p = m["k"], m["n"], _f(m["p"])
        out.append((float(stats.binom.pmf(k, n, p)), ERR_CDF_PMF))
        out.append((float(stats.binom.cdf(k - 1, n, p)), ERR_OFFBYONE))
    elif task == "binom_var":
        out.append((m["n"] * _f(m["p"]), ERR_VAR_MEAN))
    elif task == "poisson_pmf":
        out.append((float(stats.poisson.cdf(m["k"], _f(m["lam"]))), ERR_CDF_PMF))
    elif task == "normal_prob":
        value = analytic(item)
        out.append((1 - value, ERR_TAIL))
        mu, sigma = _f(m["mu"]), _f(m["sigma"])
        low = stats.norm.cdf(_f(m["a"])) if m.get("a") is not None else 0.0
        high = stats.norm.cdf(_f(m["b"])) if m.get("b") is not None else 1.0
        out.append((float(high - low), ERR_NOSTANDARDIZE))  # tra bảng thẳng bằng x, quên đổi sang z
        law = stats.norm(mu, sigma**2)
        low = law.cdf(_f(m["a"])) if m.get("a") is not None else 0.0
        high = law.cdf(_f(m["b"])) if m.get("b") is not None else 1.0
        out.append((float(high - low), ERR_VAR_AS_SD))
    elif task == "exp_prob":
        out.append((1 - analytic(item), ERR_TAIL))
        out.append((math.exp(-_f(m["t"]) * _f(m["mean"])), ERR_RATE_MEAN))
    elif task == "sample_var":
        out.append((float(np.var(m["data"], ddof=0)), ERR_VAR_N))
        out.append((float(np.std(m["data"], ddof=1)), ERR_STD_INSTEAD))
    elif task == "ci_mean":
        xbar, sd, n, conf = _f(m["xbar"]), _f(m["sd"]), m["n"], _f(m["conf"])
        if not m.get("sigma_known"):
            half = _critical(conf, "z") * sd / math.sqrt(n)
            out.append(((xbar - half, xbar + half), ERR_Z_INSTEAD_T))
        dist = "z" if m.get("sigma_known") else "t"
        half = _critical(conf, dist, n - 1) * sd
        out.append(((xbar - half, xbar + half), ERR_CI_NOSQRTN))
    elif task == "ci_prop":
        p, conf = _f(m["phat"]), _f(m["conf"])
        half = _critical(conf, "z") * math.sqrt(p * (1 - p))
        out.append(((p - half, p + half), ERR_CI_NOSQRTN))
    elif task in ("z_stat", "t_stat"):
        out.append(((_f(m["xbar"]) - _f(m["mu0"])) / _f(m["sd"]), ERR_HYP_NOSQRTN))
    elif task == "p_value":
        value = analytic(item)
        alternative = m.get("alternative", "two-sided")
        out.append((value / 2 if alternative == "two-sided" else min(1.0, 2 * value), ERR_HYP_TAIL))
        out.append((1 - value, ERR_TAIL))
    elif task == "decision":
        out.append((not analytic(item), ERR_DECISION))
    elif task in ("reg_slope", "reg_intercept"):
        x, y = np.array(m["x"], float), np.array(m["y"], float)
        sxy = float(((x - x.mean()) * (y - y.mean())).sum())
        syy = float(((y - y.mean()) ** 2).sum())
        swapped = sxy / syy  # hồi quy x theo y
        value = swapped if task == "reg_slope" else float(y.mean() - swapped * x.mean())
        out.append((value, ERR_REG_SWAPPED))
    return out


# --------------------------------------------------------------------------
# Monte Carlo
# --------------------------------------------------------------------------

def monte_carlo(item: Item, samples: int = MONTE_CARLO_SAMPLES, seed: int = 12345) -> tuple[float, float] | None:
    """Ước lượng xác suất bằng MÔ PHỎNG, độc lập với công thức. Trả ``(ước lượng, sai số chuẩn)``."""
    m, task = item.meta, item.meta["task"]
    if task not in MONTE_CARLO_TASKS:
        return None
    rng = np.random.default_rng(seed)

    def mean_and_se(hits: np.ndarray) -> tuple[float, float]:
        p = float(hits.mean())
        return p, math.sqrt(max(p * (1 - p), 1e-12) / len(hits))

    if task in ("union", "conditional"):
        # Bốn ô rời nhau: A∩B, A∖B, B∖A, phần còn lại.
        pa, pb, pab = _f(m.get("pa", m["pab"])), _f(m["pb"]), _f(m["pab"])
        cells = rng.choice(4, size=samples, p=[pab, pa - pab, pb - pab, 1 - pa - pb + pab])
        a, b = (cells == 0) | (cells == 1), (cells == 0) | (cells == 2)
        if task == "union":
            return mean_and_se(a | b)
        return mean_and_se(a[b])
    if task == "indep_and":
        a = rng.random(samples) < _f(m["pa"])
        b = rng.random(samples) < _f(m["pb"])
        return mean_and_se(a & b)
    if task in ("total_prob", "bayes"):
        prior = np.array([_f(p) for p in m["prior"]])
        likelihood = np.array([_f(l) for l in m["likelihood"]])
        hypothesis = rng.choice(len(prior), size=samples, p=prior / prior.sum())
        evidence = rng.random(samples) < likelihood[hypothesis]
        if task == "total_prob":
            return mean_and_se(evidence)
        return mean_and_se(hypothesis[evidence] == m["index"])
    if task == "binom_pmf":
        return mean_and_se(rng.binomial(m["n"], _f(m["p"]), samples) == m["k"])
    if task == "binom_cdf":
        return mean_and_se(rng.binomial(m["n"], _f(m["p"]), samples) <= m["k"])
    if task == "poisson_pmf":
        return mean_and_se(rng.poisson(_f(m["lam"]), samples) == m["k"])
    if task == "normal_prob":
        x = rng.normal(_f(m["mu"]), _f(m["sigma"]), samples)
        low = _f(m["a"]) if m.get("a") is not None else -np.inf
        high = _f(m["b"]) if m.get("b") is not None else np.inf
        return mean_and_se((x > low) & (x < high))
    if task == "exp_prob":
        return mean_and_se(rng.exponential(_f(m["mean"]), samples) > _f(m["t"]))
    if task == "p_value":
        # Phân phối của thống kê dưới H0, dựng bằng mô phỏng.
        null = rng.standard_normal(samples) if m["dist"] == "z" else rng.standard_t(m["df"], samples)
        stat, alternative = _f(m["stat"]), m.get("alternative", "two-sided")
        if alternative == "greater":
            return mean_and_se(null >= stat)
        if alternative == "less":
            return mean_and_se(null <= stat)
        return mean_and_se(np.abs(null) >= abs(stat))
    return None


def cross_check(item: Item) -> dict | None:
    """So giá trị giải tích với Monte Carlo. Lệch quá 4 sai số chuẩn là có vấn đề."""
    simulated = monte_carlo(item)
    if simulated is None:
        return None
    estimate, se = simulated
    exact = analytic(item)
    return {
        "analytic": round(exact, 6),
        "monte_carlo": round(estimate, 6),
        "standard_error": round(se, 6),
        "agree": abs(estimate - exact) <= 4 * se + 1e-4,
    }


# --------------------------------------------------------------------------
# Bộ chấm
# --------------------------------------------------------------------------

class ProbStatVerifier(Verifier):
    name = "probstat"
    verbal_answers = frozenset({"không bác bỏ h0", "bác bỏ h0", "reject h0", "fail to reject h0"})

    def handles(self, item: Item) -> bool:
        return item.meta.get("task") in PROBSTAT_TASKS

    def verify(self, item: Item, submission: Submission) -> VerificationResult:
        result = super().verify(item, submission)
        result.cross_check = cross_check(item)
        return result

    def check(self, item: Item, answer: str) -> tuple[EquivalenceResult, list[str]]:
        if not answer.strip():
            return _wrong("Chưa có đáp án"), []
        reference = analytic(item)

        if isinstance(reference, bool):
            given = parse_decision(answer)
            if given is None:
                raise ParseError(f"Không hiểu kết luận {answer!r} — hãy trả lời 'bác bỏ H0' hoặc 'không bác bỏ H0'")
            if given == reference:
                return _ok("Kết luận đúng"), []
            return _wrong("Kết luận ngược: so p-value với mức ý nghĩa α"), [ERR_DECISION]

        if isinstance(reference, tuple):
            return self._check_interval(item, answer, reference)

        given = parse_math(answer)
        if given.free_symbols:
            return _wrong("Đáp án phải là một con số"), []
        value = float(sp.N(given))
        if stat_close(value, reference):
            return _ok(f"≈ {reference:.4f} (sai số tra bảng cho phép)"), []
        for wrong_value, code in mistakes(item):
            if isinstance(wrong_value, float) and not stat_close(wrong_value, reference) and stat_close(value, wrong_value):
                return _wrong(f"Đáp án đúng ≈ {reference:.4f}; {value:g} ứng với một lỗi hay gặp"), [code]
        return _wrong(f"Đáp án đúng ≈ {reference:.4f}, bài làm ra {value:g}"), []

    @staticmethod
    def _check_interval(item: Item, answer: str, reference: tuple[float, float]):
        bounds = parse_matrix(answer)
        if len(bounds) != 2:
            return _wrong("Khoảng tin cậy phải có đúng hai đầu mút"), []
        given = tuple(sorted(float(sp.N(b)) for b in bounds))

        if intervals_close(given, reference):
            return _ok(f"≈ ({reference[0]:.4f}, {reference[1]:.4f})"), []
        for wrong_interval, code in mistakes(item):
            # Chỉ gán mã lỗi khi khoảng "sai kiểu đó" thật sự KHÁC khoảng đúng.
            if isinstance(wrong_interval, tuple) and not intervals_close(wrong_interval, reference) \
                    and intervals_close(given, wrong_interval):
                return _wrong(f"Khoảng đúng ≈ ({reference[0]:.4f}, {reference[1]:.4f})"), [code]
        return _wrong(f"Khoảng đúng ≈ ({reference[0]:.4f}, {reference[1]:.4f})"), []


def intervals_close(a: tuple[float, float], b: tuple[float, float]) -> bool:
    """Hai khoảng trùng nhau trong sai số tra bảng — dung sai theo độ rộng khoảng,
    vì sai số giá trị tới hạn làm lệch cả hai đầu mút như nhau."""
    tolerance = max(ABS_TOL, 0.01 * abs(b[1] - b[0]))
    return abs(a[0] - b[0]) <= tolerance and abs(a[1] - b[1]) <= tolerance
