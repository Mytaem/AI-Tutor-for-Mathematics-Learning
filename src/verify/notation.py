"""Chuẩn hoá cách sinh viên VIẾT toán trước khi đưa cho SymPy.

Sinh viên không gõ cú pháp Python. Họ chép ký hiệu từ đề (``x²``, ``x·eˣ``), viết
tắt theo thói quen (``sinx``, ``lnx``, ``tg x``) và viết bằng chữ (``căn x``,
``x bình phương``). SymPy không hiểu những thứ đó, và tệ hơn là nó KHÔNG báo lỗi:
``sinx`` thành ``s·i·n·x``, ``x²`` thành một biến tên "x²". Hậu quả là bài đúng bị
chấm sai mà không ai biết.

Mọi phép đổi ở đây chỉ là đổi CÁCH VIẾT sang cú pháp SymPy. Không đoán ý: cái gì
không chắc thì giữ nguyên, để bước kiểm cuối (``unreadable_symbols``) chặn lại và
hệ thống báo "chưa đọc được" thay vì chấm.
"""

from __future__ import annotations

import re
import unicodedata

import sympy as sp

_SUPERSCRIPT = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿˣ", "0123456789+-=()nx")
_SUBSCRIPT = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")
_SUPERSCRIPT_RUN = re.compile(r"[⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁽⁾ⁿˣ]+")

#: Tên hàm theo thói quen Việt Nam / máy tính -> tên SymPy. Dài trước, ngắn sau,
#: để "arctan" không bị "tan" ăn mất, "cotg" không bị "cot" ăn mất.
_FUNCTIONS = {
    "arcsin": "asin", "arccos": "acos", "arctan": "atan", "arctg": "atan",
    "arccot": "acot", "arccotg": "acot",
    "sinh": "sinh", "cosh": "cosh", "tanh": "tanh",
    "cotg": "cot", "cot": "cot", "tg": "tan", "tan": "tan",
    "sin": "sin", "cos": "cos", "sec": "sec", "csc": "csc",
    "ln": "log", "log": "log", "exp": "exp", "sqrt": "sqrt",
}
_FN = "|".join(sorted(_FUNCTIONS, key=len, reverse=True))

#: Đối số viết KHÔNG ngoặc sau tên hàm: "sin 2x", "lnx", "sin x^2".
_BARE_ARG = r"(\d+(?:\.\d+)?[a-zA-Z]?|[a-zA-Z])(\^(?:\d+|[a-zA-Z]|\([^()]*\)))?"

#: Chữ -> ký hiệu. Áp dụng trên chuỗi đã bỏ dấu và hạ chữ thường (chỉ để SO
#: KHỚP; phần còn lại của chuỗi giữ nguyên chữ hoa/thường).
_WORDS = [
    (r"can bac (?:hai|2) cua", "sqrt"),
    (r"can bac (?:ba|3) cua", "cbrt"),
    (r"can bac (?:hai|2)", "sqrt"),
    (r"can bac (?:ba|3)", "cbrt"),
    (r"can cua", "sqrt"),
    (r"can", "sqrt"),
    (r"binh phuong", "^2"),
    (r"lap phuong", "^3"),
    (r"mu", "^"),
    (r"nhan voi", "*"), (r"nhan", "*"),
    (r"chia cho", "/"), (r"chia", "/"),
    (r"cong", "+"), (r"tru", "-"),
    (r"phan", "/"),
    (r"hang so", ""),
    (r"vo cung|vo cuc", "oo"),
    (r"so pi", "pi"),
]


def _ascii_fold(text: str) -> str:
    text = text.replace("đ", "d").replace("Đ", "D")
    return "".join(c for c in unicodedata.normalize("NFD", text) if not unicodedata.combining(c))


def _replace_words(text: str) -> str:
    """Thay cụm chữ tiếng Việt bằng ký hiệu, giữ nguyên mọi ký tự khác.

    So khớp trên bản đã bỏ dấu (để "căn", "can", "Căn" như nhau) nhưng cắt ghép
    trên chuỗi gốc theo đúng vị trí, nên chữ hoa ở tên biến không bị đổi.
    """
    folded = _ascii_fold(text).lower()
    if len(folded) != len(text):          # ký tự lạ làm lệch vị trí: không đụng tới
        return text
    for pattern, symbol in _WORDS:
        regex = re.compile(rf"(?<![a-z]){pattern}(?![a-z])")
        while (match := regex.search(folded)) is not None:
            start, end = match.span()
            pad = " " if symbol not in ("", "^2", "^3", "^") else ""
            text = text[:start] + pad + symbol + pad + text[end:]
            folded = folded[:start] + pad + symbol + pad + folded[end:]
    return text


def normalize_notation(text: str) -> str:
    out = text.strip()

    # Một số duy nhất viết kiểu Việt Nam: "0,75" -> "0.75". Chỉ khi CẢ CHUỖI là
    # một số — "1,3" trong danh sách hay vector là dấu phân cách, không phải dấu thập phân.
    if re.fullmatch(r"-?\d+,\d+", out):
        return out.replace(",", ".")

    out = re.sub(r"[·⋅∙•∗]", "*", out)
    out = out.replace("∛", "cbrt")
    out = _SUPERSCRIPT_RUN.sub(lambda m: "^(" + m.group(0).translate(_SUPERSCRIPT) + ")", out)
    out = out.translate(_SUBSCRIPT)

    out = _replace_words(out)

    # |x| -> Abs(x). Chỉ cặp không lồng nhau; lồng nhau thì để nguyên cho lỗi.
    # Bọc thêm ngoặc để "ln|x|" thành "ln(Abs(x))", không thành "lnAbs(x)".
    out = re.sub(r"\|([^|]+)\|", r"(Abs(\1))", out)

    # sin^2(x) -> sin(x)^2 ; sin^2 x -> sin(x)^2
    out = re.sub(rf"\b({_FN})\s*\^\s*(\d+)\s*\(([^()]*)\)",
                 lambda m: f"{_FUNCTIONS[m.group(1).lower()]}({m.group(3)})^{m.group(2)}",
                 out, flags=re.IGNORECASE)
    out = re.sub(rf"\b({_FN})\s*\^\s*(\d+)\s*{_BARE_ARG}",
                 lambda m: f"{_FUNCTIONS[m.group(1).lower()]}({m.group(3)}{m.group(4) or ''})^{m.group(2)}",
                 out, flags=re.IGNORECASE)

    # Tên hàm có ngoặc: đổi về tên SymPy ("tg(x)" -> "tan(x)").
    out = re.sub(rf"\b({_FN})\s*\(", lambda m: _FUNCTIONS[m.group(1).lower()] + "(",
                 out, flags=re.IGNORECASE)
    # Tên hàm KHÔNG ngoặc: "sinx", "ln x", "sin 2x" -> "sin(x)", "log(x)", "sin(2x)".
    out = re.sub(rf"\b({_FN})\s*{_BARE_ARG}(?![\w(])",
                 lambda m: f"{_FUNCTIONS[m.group(1).lower()]}({m.group(2)}{m.group(3) or ''})",
                 out, flags=re.IGNORECASE)

    return re.sub(r"\s+", " ", out).strip()


def unreadable_symbols(expr) -> list[str]:
    """Ký hiệu chắc chắn sinh ra do đọc nhầm chữ, không phải biến toán học thật.

    Biến thật là chữ Latin (có thể kèm số hoặc gạch dưới: ``x``, ``C1``, ``x_1``).
    Chữ có dấu tiếng Việt hay ký tự lạ còn sót lại nghĩa là bộ chuẩn hoá không
    hiểu đoạn đó — phải báo "chưa đọc được", không được chấm như một biến.
    """
    free = getattr(expr, "free_symbols", set())
    return sorted(s.name for s in free
                  if isinstance(s, sp.Symbol) and not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", s.name))
