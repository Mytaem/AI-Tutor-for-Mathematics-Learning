"""Mở rộng truy vấn tiếng Việt sang thuật ngữ tiếng Anh trước khi truy xuất.

**Vì sao cần.** Giáo trình của bốn môn phần lớn là tiếng Anh, còn sinh viên hỏi
bằng tiếng Việt. "Chu trình Euler" không bao giờ khớp từ nào trong "Euler
circuit", nên BM25 đóng góp đúng bằng không, và chỉ còn vector dày gánh. Vector
đa ngữ thì cho điểm *na ná nhau* với mọi đoạn cùng môn, nên hệ thống trả về một
đoạn đúng môn nhưng sai chủ đề — nghe có vẻ liên quan mà vô dụng.

Đo được trên 20 câu hỏi thật, trước khi có file này: **40% dùng được**, 45% lệch
chủ đề, 10% bị chặn oan là "ngoài phạm vi".

**Cách làm.** Tìm thuật ngữ tiếng Việt trong câu hỏi rồi NỐI THÊM bản tiếng Anh
vào truy vấn, giữ nguyên câu gốc. Nối thêm chứ không thay thế: câu gốc vẫn cần
cho vector dày, còn từ tiếng Anh mới là thứ BM25 khớp được vào giáo trình.

**Nguồn từ điển** có hai phần, và phần lớn hơn KHÔNG phải viết tay:

1. ``data/skills/*.json`` đã có sẵn cả ``name_vi`` lẫn ``name_en`` cho 70 kỹ
   năng — đó là một từ điển song ngữ do chính đồ án dựng, dùng lại được ngay.
2. ``TERMS`` bên dưới: thuật ngữ nhỏ hơn tên kỹ năng, thứ sinh viên thật sự gõ
   ("p-value", "quy tắc hàm hợp", "cây khung nhỏ nhất").
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

#: Thuật ngữ Việt → Anh. Chép theo đúng chữ dùng trong giáo trình, vì mục đích
#: duy nhất của bảng này là để BM25 khớp được vào trang giáo trình.
#:
#: Một khoá có thể trỏ tới NHIỀU cách viết, cách nhau bởi khoảng trắng — giáo
#: trình không thống nhất ("2-colorable" với "bipartite"), nối cả hai thì khớp
#: được quyển nào cũng được.
TERMS: dict[str, str] = {
    # --- giải tích (MAE101)
    "giới hạn": "limit",
    "liên tục": "continuity continuous",
    "dạng vô định": "indeterminate form",
    "đạo hàm": "derivative differentiation",
    "quy tắc hàm hợp": "chain rule",
    "quy tắc tích": "product rule",
    "quy tắc thương": "quotient rule",
    "đạo hàm cấp hai": "second derivative",
    "cực trị": "extrema maximum minimum",
    "điểm uốn": "inflection point",
    "tiệm cận": "asymptote",
    "nguyên hàm": "antiderivative indefinite integral",
    "tích phân": "integral integration",
    "tích phân xác định": "definite integral",
    "tích phân bất định": "indefinite integral",
    "tích phân từng phần": "integration by parts",
    "đổi biến": "substitution change of variable",
    "phân tích thành phân thức": "partial fractions",
    "diện tích hình phẳng": "area between curves",
    "chuỗi": "series sequence",
    "hội tụ": "convergence converges",
    "phân kỳ": "divergence diverges",

    # --- đại số tuyến tính (MAE101 + MAI391)
    "ma trận": "matrix",
    "ma trận nghịch đảo": "inverse matrix",
    "nghịch đảo": "inverse",
    "định thức": "determinant",
    "hạng": "rank",
    "vết": "trace",
    "ma trận chuyển vị": "transpose",
    "hệ phương trình tuyến tính": "system of linear equations",
    "khử gauss": "gaussian elimination row reduction",
    "ma trận mở rộng": "augmented matrix",
    "dạng bậc thang": "row echelon form reduced row echelon",
    "trị riêng": "eigenvalue",
    "vector riêng": "eigenvector",
    "chéo hoá": "diagonalization diagonalizable",
    "đa thức đặc trưng": "characteristic polynomial",
    "không gian vector": "vector space",
    "độc lập tuyến tính": "linearly independent linear independence",
    "cơ sở": "basis",
    "số chiều": "dimension",
    "không gian nghiệm": "null space kernel",
    "chuẩn": "norm",
    "tích vô hướng": "inner product dot product",
    "trực giao": "orthogonal orthogonality",
    "phép chiếu": "projection",
    "phân tích svd": "singular value decomposition",
    "giá trị kỳ dị": "singular value",
    "phân tích ma trận": "matrix decomposition",
    "gradient": "gradient",
    "đạo hàm riêng": "partial derivative",
    "jacobian": "jacobian",
    "hessian": "hessian",
    "tối ưu": "optimization",
    "nhân tử lagrange": "lagrange multiplier",
    "hồi quy tuyến tính": "linear regression",
    "bình phương tối thiểu": "least squares",
    "phân tích thành phần chính": "principal component analysis",
    "máy vector hỗ trợ": "support vector machine",

    # --- toán rời rạc (MAD101)
    "mệnh đề": "proposition statement",
    "bảng chân trị": "truth table",
    "tương đương logic": "logical equivalence",
    "luật de morgan": "de morgan laws",
    "mệnh đề đảo": "converse",
    "mệnh đề phản đảo": "contrapositive",
    "phủ định": "negation",
    "lượng từ": "quantifier",
    "quy nạp": "induction mathematical induction",
    "đệ quy": "recursion recursive",
    "hệ thức truy hồi": "recurrence relation",
    "tập hợp": "set",
    "lực lượng": "cardinality",
    "hợp": "union",
    "giao": "intersection",
    "phần bù": "complement",
    "chỉnh hợp": "permutation",
    "hoán vị": "permutation",
    "tổ hợp": "combination binomial coefficient",
    "nguyên lý bù trừ": "inclusion exclusion principle",
    "nguyên lý chuồng bồ câu": "pigeonhole principle",
    "quy tắc cộng": "sum rule",
    "quy tắc nhân": "product rule multiplication rule",
    "ước chung lớn nhất": "greatest common divisor gcd",
    "bội chung nhỏ nhất": "least common multiple lcm",
    "thuật toán euclid": "euclidean algorithm",
    "đồng dư": "congruence modular arithmetic",
    "số nguyên tố": "prime number",
    "cơ số": "base radix binary representation",
    "đồ thị": "graph",
    "bậc của đỉnh": "degree of vertex",
    "định lý bắt tay": "handshaking theorem",
    "đường đi euler": "euler path",
    "chu trình euler": "euler circuit",
    "chu trình hamilton": "hamilton circuit hamiltonian",
    "đồ thị hai phía": "bipartite two-color graph",
    "tô màu": "coloring chromatic",
    "sắc số": "chromatic number",
    "cây": "tree",
    "cây khung": "spanning tree",
    "cây khung nhỏ nhất": "minimum spanning tree",
    "đường đi ngắn nhất": "shortest path dijkstra",
    "đẳng cấu": "isomorphism isomorphic",

    # --- xác suất thống kê (MAS291)
    "xác suất": "probability",
    "biến cố": "event",
    "không gian mẫu": "sample space",
    "độc lập": "independent independence",
    "xác suất có điều kiện": "conditional probability",
    "định lý bayes": "bayes theorem",
    "xác suất toàn phần": "total probability",
    "biến ngẫu nhiên": "random variable",
    "biến ngẫu nhiên rời rạc": "discrete random variable",
    "biến ngẫu nhiên liên tục": "continuous random variable",
    "hàm mật độ": "probability density function",
    "hàm phân phối": "cumulative distribution function",
    "kỳ vọng": "expected value expectation mean",
    "phương sai": "variance",
    "độ lệch chuẩn": "standard deviation",
    "phân phối nhị thức": "binomial distribution",
    "phân phối poisson": "poisson distribution",
    "phân phối chuẩn": "normal distribution gaussian",
    "phân phối chuẩn tắc": "standard normal",
    "phân phối đều": "uniform distribution",
    "phân phối mũ": "exponential distribution",
    "định lý giới hạn trung tâm": "central limit theorem",
    "trung bình mẫu": "sample mean",
    "phương sai mẫu": "sample variance",
    "trung vị": "median",
    "thống kê mô tả": "descriptive statistics",
    "khoảng tin cậy": "confidence interval",
    "mức ý nghĩa": "significance level alpha",
    "kiểm định giả thuyết": "hypothesis test hypothesis testing",
    "giả thuyết không": "null hypothesis",
    "giả thuyết đối": "alternative hypothesis",
    "kiểm định t": "t-test t distribution",
    "kiểm định z": "z-test z distribution",
    "p-value": "p-value",
    "giá trị p": "p-value",
    "sai số": "error margin of error",
    "hai mẫu": "two samples two-sample",
    "ghép cặp": "paired",
    "hồi quy": "regression",
    "hệ số tương quan": "correlation coefficient",
    "hệ số góc": "slope",
    "hệ số chặn": "intercept",
}

#: Từ hỏi và từ nối — bỏ đi khi so khớp để "Chu trình Euler là gì?" và "chu
#: trình euler" cùng khớp một mục.
_STOP = re.compile(
    r"\b(là|gì|thế|nào|sao|khi|dùng|để|làm|của|cho|có|các|một|và|hay|hoặc|"
    r"định|nghĩa|phát|biểu|tính|công|thức|em|thầy|cô|ạ|với|trong|về)\b"
)


def _fold(text: str) -> str:
    """Chuẩn hoá để so khớp: hạ chữ, bỏ dấu, gộp khoảng trắng.

    Bỏ dấu vì sinh viên gõ nhanh hay thiếu dấu ("chu trinh euler"), và vì bàn
    phím điện thoại tự sửa lung tung. Khoá trong bảng cũng bỏ dấu y như vậy
    nên hai bên vẫn gặp nhau.
    """
    lowered = unicodedata.normalize("NFD", text.lower())
    stripped = "".join(ch for ch in lowered if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", stripped.replace("đ", "d")).strip()


@lru_cache(maxsize=1)
def _table() -> list[tuple[str, str]]:
    """Từ điển đã gộp, sắp theo độ dài GIẢM DẦN.

    Dài trước là bắt buộc: "tích phân từng phần" phải khớp trước "tích phân",
    nếu không thì câu hỏi về integration by parts chỉ được mở rộng thành
    "integral" và lại trả về đúng cái đoạn sai như trước.
    """
    merged: dict[str, str] = {_fold(vi): en for vi, en in TERMS.items()}

    # Tên kỹ năng song ngữ do chính đồ án dựng — thêm vào nếu chưa có mục nào
    # phủ. Không ghi đè TERMS: tên kỹ năng là cả một cụm dài ("Quy tắc đạo hàm
    # tích và thương"), còn TERMS nhắm đúng thuật ngữ sinh viên gõ.
    try:
        from src.core.itembank import ItemBank

        for subject in ("MAE101", "MAD101", "MAI391", "MAS291"):
            for skill in ItemBank.load(subject).skills.values():
                key = _fold(skill.name_vi)
                if key and skill.name_en and key not in merged:
                    merged[key] = skill.name_en
    except Exception:
        # Thiếu dữ liệu kỹ năng thì vẫn chạy với TERMS — mở rộng truy vấn là
        # phần làm TỐT HƠN, không được phép làm sập việc hỏi đáp.
        pass

    return sorted(merged.items(), key=lambda kv: -len(kv[0]))


def english_terms(question: str) -> list[str]:
    """Các thuật ngữ tiếng Anh ứng với thuật ngữ Việt tìm thấy trong câu hỏi.

    Khớp xong thì XOÁ cụm đã khớp khỏi chuỗi đang xét, nên "tích phân từng
    phần" không bị đếm thêm một lần nữa thành "tích phân".
    """
    remaining = f" {_fold(question)} "
    found: list[str] = []
    for vi, en in _table():
        if f" {vi} " in remaining:
            found.append(en)
            remaining = remaining.replace(f" {vi} ", " ")
    return found


def expand(question: str) -> str:
    """Câu hỏi đã nối thêm thuật ngữ tiếng Anh. Không tìm thấy gì thì trả nguyên.

    Giữ câu gốc ở đầu: vector dày vẫn cần ngữ cảnh tiếng Việt, phần tiếng Anh
    nối sau là để BM25 có cái mà khớp.
    """
    terms = english_terms(question)
    if not terms:
        return question
    return f"{question} {' '.join(terms)}"


def coverage(question: str) -> bool:
    """Câu hỏi có nhận ra được thuật ngữ nào không — dùng để đo độ phủ từ điển."""
    return bool(english_terms(question))


#: Thuật ngữ mà model 3b hay dịch sai thành chữ nghe-như-tiếng-Việt nhưng sai
#: nghĩa chuyên môn. Quan sát thật từ bản trả lời trước khi có bảng này:
#:
#:   "null hypothesis"      -> "giả thuyết đầu tiên"        (phải là H₀)
#:   "significance level α" -> "mức độ không chắc chắn"     (phải là mức ý nghĩa)
#:   "error bound"          -> "độ tin cậy"                 (lẫn với confidence level)
#:
#: Dịch sai thuật ngữ nguy hiểm hơn dịch lủng củng: câu vẫn đọc trôi, mà sinh
#: viên học vào đúng cái sai. Bảng này được nhồi vào prompt để chốt cách gọi.
TERM_PINS: dict[str, str] = {
    "null hypothesis": "giả thuyết không (H₀)",
    "alternative hypothesis": "giả thuyết đối (H₁)",
    "significance level": "mức ý nghĩa (α)",
    "p-value": "giá trị p (p-value)",
    "confidence level": "độ tin cậy",
    "confidence interval": "khoảng tin cậy",
    "error bound": "sai số biên",
    "margin of error": "sai số biên",
    "point estimate": "ước lượng điểm",
    "population": "tổng thể",
    "sample": "mẫu",
    "sample mean": "trung bình mẫu",
    "sample size": "cỡ mẫu",
    "standard deviation": "độ lệch chuẩn",
    "standard error": "sai số chuẩn",
    "variance": "phương sai",
    "expected value": "kỳ vọng",
    "random variable": "biến ngẫu nhiên",
    "probability density function": "hàm mật độ xác suất",
    "cumulative distribution function": "hàm phân phối tích luỹ",
    "normal distribution": "phân phối chuẩn",
    "binomial distribution": "phân phối nhị thức",
    "central limit theorem": "định lý giới hạn trung tâm",
    "degrees of freedom": "số bậc tự do",
    "regression": "hồi quy",
    "correlation": "tương quan",
    "slope": "hệ số góc",
    "intercept": "hệ số chặn",
    "eigenvalue": "trị riêng",
    "eigenvector": "vector riêng",
    "determinant": "định thức",
    # Quan sát thật: model dịch "trace" thành "trắc phân thứ n-1" — vô nghĩa.
    "trace": "vết (trace)",
    "characteristic polynomial": "đa thức đặc trưng",
    "rank": "hạng",
    "transpose": "chuyển vị",
    "orthogonal": "trực giao",
    "inner product": "tích vô hướng",
    "spanning tree": "cây khung",
    "degree": "bậc của đỉnh",
    "derivative": "đạo hàm",
    "antiderivative": "nguyên hàm",
    "chain rule": "quy tắc hàm hợp",
    "integration by parts": "tích phân từng phần",
    "limit": "giới hạn",
    "euler circuit": "chu trình Euler",
    "spanning tree": "cây khung",
    "inclusion exclusion": "nguyên lý bù trừ",
    "pigeonhole": "nguyên lý chuồng bồ câu",
}


def pinned_terms(text: str, limit: int = 12) -> list[tuple[str, str]]:
    """Các cặp (thuật ngữ Anh, cách gọi tiếng Việt đúng) xuất hiện trong ``text``.

    Quét trên ĐOẠN TRÍCH chứ không trên câu hỏi: câu hỏi tiếng Việt vốn đã dùng
    đúng từ, còn chỗ model dịch sai là lúc nó đọc đoạn tiếng Anh.

    Giới hạn số cặp để prompt không phình: nhồi 40 thuật ngữ vào thì model 3b
    bắt đầu lạc, và phần đoạn trích bị đẩy ra xa khỏi câu hỏi.
    """
    lowered = text.lower()
    found = [(en, vi) for en, vi in TERM_PINS.items() if en in lowered]
    # Cụm dài trước: "sample mean" có nghĩa riêng, không phải "sample" + "mean".
    found.sort(key=lambda pair: -len(pair[0]))
    return found[:limit]
