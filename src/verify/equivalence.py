"""So sánh tương đương biểu thức toán học — nền chung cho cả 4 verifier (Phần D0).

Chiến lược (thứ tự có chủ đích, khác với thứ tự "ngây thơ" simplify-trước):

1. So khớp cấu trúc      — nhanh nhất, bắt được trường hợp giống hệt.
2. Lấy mẫu số học        — CHỐT CHẶN CHÍNH. Nếu hai biểu thức khác nhau tại một
                           điểm mà cả hai đều xác định thì chắc chắn KHÔNG tương
                           đương. Rẻ (vài ms) và không bao giờ treo.
3. Xác nhận ký hiệu      — chỉ chạy khi bước 2 nói "bằng nhau", để nâng độ tin cậy
                           từ "gần như chắc" lên "chứng minh được". Bọc timeout.

Lý do đảo thứ tự: `simplify` có thể treo hàng chục giây với biểu thức rối, trong
khi lấy mẫu số học phủ định gần như tức thì. Ta để cái rẻ làm việc phủ định, cái
đắt chỉ làm việc khẳng định.

Cảnh báo về miền lấy mẫu: mặc định lấy mẫu trên số thực dương, nên `sqrt(x**2)` và
`x` sẽ được coi là tương đương. Với các bài cần phân biệt (ví dụ `ln|x|` và `ln x`
trong nguyên hàm), hãy gọi với `domain="real"`.
"""

from __future__ import annotations

import random
import re
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Literal, Sequence

import sympy as sp
from sympy.parsing.sympy_parser import (
    _token_splittable,
    convert_xor,
    function_exponentiation,
    implicit_application,
    implicit_multiplication,
    parse_expr,
    split_symbols_custom,
    standard_transformations,
)

Domain = Literal["positive", "real", "complex"]

DEFAULT_TIMEOUT = 5.0
#: Ngân sách riêng cho bước XÁC NHẬN ký hiệu, ngắn hơn hẳn DEFAULT_TIMEOUT.
#: Tới bước này lấy mẫu số học đã kết luận "bằng nhau" với độ tin cậy 0.99;
#: xác nhận chỉ để nâng lên 1.0. Đo thực tế: ``simplify`` có thể mất 8 giây với
#: nguyên hàm lượng giác dạng góc chia đôi — để nó chạy tới DEFAULT_TIMEOUT (hai
#: lần: simplify rồi equals) nghĩa là sinh viên bấm nộp bài phải chờ ~10 giây
#: cho một kết luận đã biết sẵn.
CONFIRM_TIMEOUT = 1.0
DEFAULT_SAMPLES = 30
DEFAULT_TOL = 1e-9


# --------------------------------------------------------------------------
# Parsing an toàn
# --------------------------------------------------------------------------

# Không dùng sympify() thẳng trên chuỗi người dùng nhập: nó gọi eval() và mở
# đường cho code injection khi hệ thống chạy dưới dạng web API. Thay vào đó ta
# parse với một namespace được liệt kê trắng.
_ALLOWED_NAMES: dict[str, Any] = {
    name: getattr(sp, name)
    for name in (
        # Các constructor bên dưới BẮT BUỘC phải có: transformation `auto_symbol`
        # và `auto_number` của SymPy sinh ra mã gọi thẳng Symbol(...)/Integer(...),
        # thiếu chúng thì mọi biểu thức đều không parse được.
        "Symbol", "Integer", "Float", "Rational", "Add", "Mul",
        "Abs", "acos", "acosh", "asin", "asinh", "atan", "atan2", "atanh",
        "binomial", "cbrt", "ceiling", "conjugate", "cos", "cosh", "cot",
        "csc", "Derivative", "diff", "E", "exp", "factorial", "floor",
        "gamma", "GoldenRatio", "I", "Integral", "integrate", "Interval",
        "log", "ln", "Matrix", "Max", "Min", "oo", "pi", "Piecewise", "Pow",
        "Rational", "re", "im", "root", "sec", "sign", "simplify", "sin",
        "sinh", "sqrt", "Sum", "symbols", "tan", "tanh", "zoo",
    )
    if hasattr(sp, name)
}
_ALLOWED_NAMES["Infinity"] = sp.oo
# Sinh viên viết "e^x" nhiều hơn "exp(x)". Đổi lại, không dùng được "e" làm tên
# biến — chấp nhận được trong ngữ cảnh toán đại cương.
_ALLOWED_NAMES["e"] = sp.E


def _splittable(token: str) -> bool:
    """Tên ký hiệu nhiều chữ cái có được tách thành tích không ("xy" -> x*y)?

    KHÔNG tách tên chứa chữ số hoặc gạch dưới: ``C1``, ``C2``, ``x1``, ``C_1``.
    Bộ tách mặc định của SymPy biến ``C1`` thành ``C*1``, khiến hai hằng số độc
    lập ``C1``, ``C2`` của nghiệm tổng quát ODE sập thành một — và một lời giải
    đúng bị chấm là thiếu hằng số.
    """
    if any(char.isdigit() for char in token) or "_" in token:
        return False
    return _token_splittable(token)


_TRANSFORMS = standard_transformations + (
    split_symbols_custom(_splittable),  # "xy" -> x*y, nhưng giữ nguyên "C1"
    implicit_multiplication,            # cho phép viết "2x" thay vì "2*x"
    implicit_application,
    function_exponentiation,
    convert_xor,                        # cho phép viết "x^2" thay vì "x**2"
)


class ParseError(ValueError):
    """Không parse được biểu thức người dùng nhập."""


def parse_math(text: str) -> sp.Expr:
    """Parse chuỗi toán học thành biểu thức SymPy, chỉ cho phép hàm trong danh sách trắng.

    Chấp nhận cả cách viết tự nhiên của sinh viên: ``2x^2`` -> ``2*x**2``.
    """
    if not isinstance(text, str) or not text.strip():
        raise ParseError("Biểu thức rỗng")

    cleaned = _normalize_input(text)
    try:
        expr = parse_expr(
            cleaned,
            local_dict={},
            global_dict=dict(_ALLOWED_NAMES),
            transformations=_TRANSFORMS,
            evaluate=True,
        )
    except Exception as exc:  # parse_expr ném đủ loại exception khác nhau
        raise ParseError(f"Không đọc được biểu thức {text!r}: {exc}") from exc

    if not isinstance(expr, (sp.Expr, sp.MatrixBase, sp.Set)):
        raise ParseError(f"{text!r} không phải là một biểu thức toán học hợp lệ")
    return expr


def _normalize_input(text: str) -> str:
    """Chuẩn hoá các cách viết hay gặp trong bài làm của sinh viên."""
    replacements = {
        "−": "-",      # dấu trừ Unicode khi copy từ Word/PDF
        "–": "-",
        "×": "*",
        "÷": "/",
        "π": "pi",
        "∞": "oo",
        "{": "(",
        "}": ")",
        "[": "(",
        "]": ")",
    }
    out = text.strip()
    for old, new in replacements.items():
        out = out.replace(old, new)

    # Dấu căn phải thành lời gọi hàm CÓ ngoặc. Nếu chỉ thay "√" -> "sqrt" thì
    # "√x" thành "sqrtx", và phép nhân ngầm sẽ âm thầm tách nó thành q*r*s*t*x —
    # sai hoàn toàn mà không báo lỗi.
    out = re.sub(r"√\s*\(", "sqrt(", out)
    out = re.sub(r"√\s*([A-Za-z0-9_.]+)", r"sqrt(\1)", out)
    return out


# --------------------------------------------------------------------------
# Timeout mềm
# --------------------------------------------------------------------------

def run_with_timeout(fn: Callable[[], Any], timeout: float = DEFAULT_TIMEOUT) -> tuple[bool, Any]:
    """Chạy ``fn`` với giới hạn thời gian. Trả về ``(hoàn_thành, kết_quả)``.

    Dùng daemon thread chứ không dùng ``signal.alarm`` vì alarm không có trên
    Windows. Python không kill được thread, nên khi quá hạn ta *bỏ mặc* nó —
    thread là daemon nên không chặn tiến trình thoát. Đây là đánh đổi có chủ ý:
    một lời gọi ``simplify`` treo sẽ ngốn một core cho tới khi nó tự xong, nhưng
    API vẫn phản hồi. Với khối lượng của đồ án thì chấp nhận được; nếu về sau cần
    cắt cứng, hãy chuyển sang ProcessPoolExecutor.
    """
    box: dict[str, Any] = {}

    def target() -> None:
        try:
            box["value"] = fn()
        except Exception as exc:
            box["error"] = exc

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(timeout)

    if thread.is_alive():
        return False, None
    if "error" in box:
        return False, None
    return True, box.get("value")


def tidy(expr: sp.Expr, timeout: float = CONFIRM_TIMEOUT) -> sp.Expr:
    """Rút gọn biểu thức để HIỂN THỊ, có giới hạn thời gian.

    Không bao giờ gọi ``sp.simplify`` trần chỉ để in thông báo cho đẹp: đo thực
    tế nó có thể mất 8 giây, và một câu thông báo không đáng để sinh viên phải
    chờ. Quá hạn thì in nguyên dạng chưa rút gọn.
    """
    done, value = run_with_timeout(lambda: sp.simplify(expr), timeout)
    return value if done and value is not None else expr


# --------------------------------------------------------------------------
# Kết quả so sánh
# --------------------------------------------------------------------------

@dataclass
class EquivalenceResult:
    """Kết quả so sánh hai biểu thức, kèm bằng chứng để log lại và debug."""

    equal: bool
    method: str            # structural | numeric | symbolic | trivial
    confidence: float      # 1.0 = chứng minh ký hiệu; ~0.99 = lấy mẫu số học
    detail: str = ""
    counterexample: dict[str, complex] | None = None
    samples_used: int = 0

    def __bool__(self) -> bool:
        return self.equal


# --------------------------------------------------------------------------
# Lấy mẫu số học
# --------------------------------------------------------------------------

def _sample_point(symbols: Sequence[sp.Symbol], domain: Domain, rng: random.Random) -> dict[sp.Symbol, complex]:
    point: dict[sp.Symbol, complex] = {}
    for sym in symbols:
        if domain == "positive":
            point[sym] = rng.uniform(0.15, 2.85)
        elif domain == "real":
            value = rng.uniform(0.15, 2.85)
            point[sym] = value if rng.random() < 0.5 else -value
        else:  # complex
            point[sym] = complex(rng.uniform(-2.0, 2.0), rng.uniform(-2.0, 2.0))
    return point


def _evaluate(expr: sp.Expr, point: dict[sp.Symbol, complex]) -> complex | None:
    """Tính giá trị số của biểu thức tại một điểm; trả None nếu không xác định."""
    try:
        value = complex(expr.evalf(subs=point, n=20))
    except (TypeError, ValueError, ZeroDivisionError, AttributeError):
        return None
    if value.real != value.real or value.imag != value.imag:  # NaN
        return None
    if abs(value.real) == float("inf") or abs(value.imag) == float("inf"):
        return None
    return value


def _close(a: complex, b: complex, tol: float) -> bool:
    scale = max(1.0, abs(a), abs(b))
    return abs(a - b) <= tol * scale


def numeric_equal(
    lhs: sp.Expr,
    rhs: sp.Expr,
    *,
    n_samples: int = DEFAULT_SAMPLES,
    tol: float = DEFAULT_TOL,
    domain: Domain = "positive",
    max_attempts: int = 400,
    seed: int | None = 12345,
) -> EquivalenceResult:
    """So sánh bằng cách thay số ngẫu nhiên vào cả hai biểu thức.

    Chỉ tính các điểm mà CẢ HAI biểu thức đều xác định và hữu hạn — điểm mà một
    bên không xác định không nói lên điều gì về tương đương.
    """
    free = sorted(lhs.free_symbols | rhs.free_symbols, key=str)
    rng = random.Random(seed)

    # Không có biến -> so sánh trực tiếp hai hằng số.
    if not free:
        va, vb = _evaluate(lhs, {}), _evaluate(rhs, {})
        if va is None or vb is None:
            return EquivalenceResult(False, "numeric", 0.0, "Không tính được giá trị số")
        ok = _close(va, vb, tol)
        return EquivalenceResult(
            ok, "numeric", 0.99 if ok else 1.0,
            f"{va:.10g} vs {vb:.10g}", samples_used=1,
        )

    matched = 0
    for _ in range(max_attempts):
        if matched >= n_samples:
            break
        point = _sample_point(free, domain, rng)
        va, vb = _evaluate(lhs, point), _evaluate(rhs, point)
        if va is None or vb is None:
            continue  # điểm nằm ngoài miền xác định, bỏ qua
        if not _close(va, vb, tol):
            return EquivalenceResult(
                False, "numeric", 1.0,
                f"Khác nhau tại điểm mẫu: {va:.10g} vs {vb:.10g}",
                counterexample={str(k): v for k, v in point.items()},
                samples_used=matched + 1,
            )
        matched += 1

    if matched == 0:
        return EquivalenceResult(
            False, "numeric", 0.0,
            "Không tìm được điểm nào cả hai biểu thức cùng xác định",
        )
    if matched < n_samples:
        return EquivalenceResult(
            True, "numeric", 0.90,
            f"Khớp trên {matched}/{n_samples} điểm (miền xác định hẹp)",
            samples_used=matched,
        )
    return EquivalenceResult(
        True, "numeric", 0.99,
        f"Khớp trên toàn bộ {matched} điểm mẫu", samples_used=matched,
    )


# --------------------------------------------------------------------------
# So sánh tổng hợp
# --------------------------------------------------------------------------

def expr_equal(
    lhs: sp.Expr | str,
    rhs: sp.Expr | str,
    *,
    domain: Domain = "positive",
    tol: float = DEFAULT_TOL,
    n_samples: int = DEFAULT_SAMPLES,
    timeout: float = DEFAULT_TIMEOUT,
) -> EquivalenceResult:
    """Kiểm tra hai biểu thức có tương đương không, theo chiến lược 3 tầng ở đầu file."""
    lhs = parse_math(lhs) if isinstance(lhs, str) else lhs
    rhs = parse_math(rhs) if isinstance(rhs, str) else rhs

    # Tầng 1: giống hệt về cấu trúc.
    if lhs == rhs:
        return EquivalenceResult(True, "structural", 1.0, "Hai biểu thức giống hệt nhau")

    # Tầng 2: lấy mẫu số học — dùng để PHỦ ĐỊNH.
    numeric = numeric_equal(lhs, rhs, n_samples=n_samples, tol=tol, domain=domain)
    if not numeric.equal:
        return numeric

    # Tầng 3: xác nhận bằng ký hiệu — dùng để KHẲNG ĐỊNH chắc chắn. Chỉ là nâng
    # độ tin cậy, không phải bước quyết định, nên dùng ngân sách ngắn.
    budget = min(timeout, CONFIRM_TIMEOUT)
    done, value = run_with_timeout(lambda: sp.simplify(lhs - rhs), budget)
    if done and value is not None and value == 0:
        return EquivalenceResult(True, "symbolic", 1.0, "simplify(lhs - rhs) = 0")

    # simplify đã quá hạn thì equals (cùng loại máy móc) gần như chắc cũng vậy —
    # không trả thêm một giây nữa cho một lần thử gần như chắc chắn thất bại.
    if done:
        done, value = run_with_timeout(lambda: lhs.equals(rhs), budget)
        if done and value is True:
            return EquivalenceResult(True, "symbolic", 1.0, "Expr.equals() xác nhận")

    # Ký hiệu không kết luận được (treo hoặc trả None) nhưng số học đã khớp.
    return EquivalenceResult(
        True, "numeric", numeric.confidence,
        numeric.detail + " (xác nhận ký hiệu không kết luận được)",
        samples_used=numeric.samples_used,
    )


def equal_up_to_constant(
    lhs: sp.Expr | str,
    rhs: sp.Expr | str,
    var: sp.Symbol | str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
) -> EquivalenceResult:
    """Hai biểu thức có sai khác nhau đúng một hằng số không?

    Dùng cho nguyên hàm: ``tan(x)`` và ``tan(x) + 5`` là hai đáp án đều đúng, và
    ``sin(x)**2`` với ``-cos(x)**2`` cũng vậy (sai khác hằng số 1) — so khớp
    biểu thức thuần sẽ báo sai, so khớp sau khi lấy đạo hàm thì đúng.
    """
    lhs = parse_math(lhs) if isinstance(lhs, str) else lhs
    rhs = parse_math(rhs) if isinstance(rhs, str) else rhs
    var = sp.Symbol(var) if isinstance(var, str) else var

    difference = lhs - rhs
    done, derivative = run_with_timeout(lambda: sp.diff(difference, var), timeout)
    if not done or derivative is None:
        return EquivalenceResult(False, "symbolic", 0.0, "Không lấy được đạo hàm của hiệu")

    zero = expr_equal(derivative, sp.Integer(0), timeout=timeout)
    if zero.equal:
        return EquivalenceResult(
            True, zero.method, zero.confidence,
            "Đạo hàm của hiệu bằng 0 → hai biểu thức chỉ lệch nhau một hằng số",
        )
    return EquivalenceResult(
        False, zero.method, zero.confidence,
        "Đạo hàm của hiệu khác 0 → lệch nhau nhiều hơn một hằng số",
        counterexample=zero.counterexample,
    )


def is_antiderivative_of(
    candidate: sp.Expr | str,
    integrand: sp.Expr | str,
    var: sp.Symbol | str,
    *,
    domain: Domain = "positive",
    timeout: float = DEFAULT_TIMEOUT,
) -> EquivalenceResult:
    """Kiểm tra nguyên hàm bằng cách LẤY ĐẠO HÀM NGƯỢC.

    Đây là cách chấm tích phân đúng đắn nhất: thay vì so đáp án của sinh viên với
    một dạng chuẩn (vốn có vô số dạng tương đương), ta đạo hàm đáp án của họ và
    đối chiếu với biểu thức dưới dấu tích phân. Mọi dạng đúng đều tự động được
    chấp nhận, không cần liệt kê trước.
    """
    candidate = parse_math(candidate) if isinstance(candidate, str) else candidate
    integrand = parse_math(integrand) if isinstance(integrand, str) else integrand
    var = sp.Symbol(var) if isinstance(var, str) else var

    done, derivative = run_with_timeout(lambda: sp.diff(candidate, var), timeout)
    if not done or derivative is None:
        return EquivalenceResult(False, "symbolic", 0.0, "Không lấy được đạo hàm của đáp án")

    result = expr_equal(derivative, integrand, domain=domain, timeout=timeout)
    if result.equal:
        return EquivalenceResult(
            True, result.method, result.confidence,
            f"d/d{var}({candidate}) = {tidy(derivative)} khớp với biểu thức dưới dấu tích phân",
        )
    return EquivalenceResult(
        False, result.method, result.confidence,
        f"d/d{var}(đáp án) = {derivative}, không khớp với {integrand}",
        counterexample=result.counterexample,
    )


# --------------------------------------------------------------------------
# So sánh theo loại đáp án
# --------------------------------------------------------------------------

def number_equal(lhs: Any, rhs: Any, *, rel_tol: float = 1e-6) -> EquivalenceResult:
    """So sánh hai giá trị số với dung sai tương đối.

    Dung sai nới rộng (1e-6 thay vì 1e-9) vì sinh viên tra bảng phân phối và làm
    tròn — quan trọng với MAS291.
    """
    try:
        a = complex(sp.sympify(lhs).evalf(n=20))
        b = complex(sp.sympify(rhs).evalf(n=20))
    except (TypeError, ValueError, sp.SympifyError):
        return EquivalenceResult(False, "numeric", 0.0, "Không chuyển được về dạng số")

    ok = _close(a, b, rel_tol)
    return EquivalenceResult(
        ok, "numeric", 1.0,
        f"{a:.10g} {'≈' if ok else '≠'} {b:.10g} (dung sai tương đối {rel_tol:g})",
    )


def set_equal(
    lhs: Sequence[Any],
    rhs: Sequence[Any],
    *,
    domain: Domain = "positive",
) -> EquivalenceResult:
    """So sánh hai tập nghiệm, KHÔNG quan tâm thứ tự.

    Dùng cho: tập nghiệm phương trình, trị riêng, nghiệm của hệ.
    """
    left = [parse_math(x) if isinstance(x, str) else sp.sympify(x) for x in lhs]
    right = [parse_math(x) if isinstance(x, str) else sp.sympify(x) for x in rhs]

    if len(left) != len(right):
        return EquivalenceResult(
            False, "structural", 1.0,
            f"Số phần tử khác nhau: {len(left)} và {len(right)}",
        )

    unmatched = list(right)
    for item in left:
        for index, other in enumerate(unmatched):
            if expr_equal(item, other, domain=domain).equal:
                unmatched.pop(index)
                break
        else:
            return EquivalenceResult(
                False, "numeric", 0.99,
                f"Không tìm thấy phần tử khớp với {item} trong đáp án còn lại",
            )
    return EquivalenceResult(True, "numeric", 0.99, f"Hai tập {len(left)} phần tử khớp nhau")


def matrix_equal(lhs: Any, rhs: Any, *, tol: float = DEFAULT_TOL) -> EquivalenceResult:
    """So sánh hai ma trận theo từng phần tử."""
    try:
        a, b = sp.Matrix(lhs), sp.Matrix(rhs)
    except (TypeError, ValueError, sp.SympifyError):
        return EquivalenceResult(False, "structural", 0.0, "Không dựng được ma trận")

    if a.shape != b.shape:
        return EquivalenceResult(
            False, "structural", 1.0, f"Kích thước khác nhau: {a.shape} và {b.shape}",
        )
    for i in range(a.rows):
        for j in range(a.cols):
            cell = expr_equal(a[i, j], b[i, j], tol=tol)
            if not cell.equal:
                return EquivalenceResult(
                    False, cell.method, cell.confidence,
                    f"Khác nhau tại phần tử ({i}, {j}): {a[i, j]} vs {b[i, j]}",
                )
    return EquivalenceResult(True, "numeric", 0.99, f"Hai ma trận {a.shape} khớp nhau")


def parallel_vectors(lhs: Any, rhs: Any) -> EquivalenceResult:
    """Hai vector có cùng phương không (khác nhau một bội vô hướng khác 0)?

    Dùng cho vector riêng MAI391: nếu ``v`` là vector riêng thì ``3v`` và ``-v``
    cũng vậy, nên so khớp từng phần tử là chấm sai.
    """
    try:
        a, b = sp.Matrix(lhs), sp.Matrix(rhs)
    except (TypeError, ValueError, sp.SympifyError):
        return EquivalenceResult(False, "structural", 0.0, "Không dựng được vector")

    if a.shape != b.shape:
        return EquivalenceResult(False, "structural", 1.0, f"Kích thước khác nhau: {a.shape} và {b.shape}")
    if a.norm() == 0 or b.norm() == 0:
        return EquivalenceResult(False, "structural", 1.0, "Vector riêng không được là vector 0")

    # Cùng phương <=> ma trận ghép [a | b] có hạng 1.
    stacked = a.row_join(b) if a.cols == 1 else a.col_join(b)
    done, rank = run_with_timeout(lambda: stacked.rank())
    if not done or rank is None:
        return EquivalenceResult(False, "symbolic", 0.0, "Không tính được hạng")

    if rank == 1:
        return EquivalenceResult(True, "symbolic", 1.0, "Hai vector cùng phương (hạng ghép = 1)")
    return EquivalenceResult(False, "symbolic", 1.0, f"Hai vector không cùng phương (hạng ghép = {rank})")
