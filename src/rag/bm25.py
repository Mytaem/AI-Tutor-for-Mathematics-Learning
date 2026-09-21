"""BM25 cho tiếng Việt và ký hiệu toán.

Vì sao tự cài thay vì dùng thư viện: điểm quyết định chất lượng của BM25 trên
kho tài liệu toán nằm ở khâu TÁCH TOKEN, mà thư viện có sẵn chỉ nhận danh sách
token do ta đưa vào — phần khó vẫn phải tự làm. Cài luôn cả phần tính điểm thì
bớt được một dependency và kiểm soát được hoàn toàn.

Vì sao vẫn cần BM25 khi đã có embedding: truy vấn toán đầy ký hiệu và thuật ngữ
hiếm ("tích phân từng phần", "∫", "dx", "Newton–Leibniz"). Embedding đa ngôn ngữ
hay làm nhoè đúng những token đặc hiệu đó, trong khi khớp từ khoá thì bắt chính
xác. Hai nhánh bù khuyết cho nhau — đây là lý do dùng hybrid chứ không phải làm
cho có.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field

#: Giữ lại ký hiệu toán như những token độc lập — chúng là tín hiệu truy xuất
#: rất mạnh mà cách tách token thông thường sẽ vứt đi.
_MATH_SYMBOLS = "∫∑∏√π∞≤≥≠±→↔∈⊂∪∩"
_TOKEN_PATTERN = re.compile(rf"\w+|[{_MATH_SYMBOLS}]", re.UNICODE)

#: Từ quá phổ biến trong văn bản giảng dạy tiếng Việt, gần như không mang thông tin.
STOPWORDS = frozenset("""
là và của có các một những cho với được trong khi thì mà này đó ta em ở
từ đến về như sau khi nếu hoặc hay cũng đã sẽ rất nên vì do bởi
the a an of and or to in is are for with be this that it we you
""".split())


def tokenize(text: str, remove_stopwords: bool = True) -> list[str]:
    """Tách văn bản thành token, giữ nguyên ký hiệu toán."""
    tokens = _TOKEN_PATTERN.findall(text.lower())
    if remove_stopwords:
        # Token một ký tự vẫn giữ nếu là ký hiệu toán hoặc biến (x, y, n).
        return [t for t in tokens if t not in STOPWORDS]
    return tokens


@dataclass
class BM25:
    """Okapi BM25.

    ``k1`` điều chỉnh mức bão hoà theo tần suất, ``b`` mức chuẩn hoá theo độ dài
    tài liệu. Giá trị mặc định là giá trị chuẩn trong literature.
    """

    k1: float = 1.5
    b: float = 0.75

    documents: list[list[str]] = field(default_factory=list)
    _term_frequencies: list[Counter] = field(default_factory=list)
    _document_frequency: Counter = field(default_factory=Counter)
    _lengths: list[int] = field(default_factory=list)
    _average_length: float = 0.0

    def fit(self, texts: list[str]) -> BM25:
        self.documents = [tokenize(text) for text in texts]
        self._term_frequencies = [Counter(tokens) for tokens in self.documents]
        self._lengths = [len(tokens) for tokens in self.documents]
        self._average_length = (sum(self._lengths) / len(self._lengths)) if self._lengths else 0.0

        self._document_frequency = Counter()
        for frequencies in self._term_frequencies:
            self._document_frequency.update(frequencies.keys())
        return self

    def idf(self, term: str) -> float:
        """Nghịch đảo tần suất tài liệu, dạng có cộng 1 để không bao giờ âm."""
        total = len(self.documents)
        document_frequency = self._document_frequency.get(term, 0)
        return math.log(1 + (total - document_frequency + 0.5) / (document_frequency + 0.5))

    def score(self, query: str, index: int) -> float:
        if not self.documents:
            return 0.0

        frequencies = self._term_frequencies[index]
        length = self._lengths[index]
        normalizer = self.k1 * (1 - self.b + self.b * length / (self._average_length or 1))

        total = 0.0
        for term in tokenize(query):
            frequency = frequencies.get(term, 0)
            if frequency == 0:
                continue
            total += self.idf(term) * (frequency * (self.k1 + 1)) / (frequency + normalizer)
        return total

    def search(
        self, query: str, top_k: int = 10, candidates: set[int] | None = None
    ) -> list[tuple[int, float]]:
        """Trả về ``(chỉ_số, điểm)`` của các tài liệu khớp nhất, đã bỏ điểm 0.

        ``candidates`` giới hạn phạm vi xếp hạng (dùng khi đã lọc theo môn học
        hoặc theo loại nội dung). IDF vẫn tính trên TOÀN BỘ kho — độ hiếm của
        một từ là thuộc tính của kho tài liệu, không phụ thuộc vào bộ lọc đang
        áp dụng.
        """
        indices = range(len(self.documents)) if candidates is None else sorted(candidates)
        hits = [
            (index, score)
            for index in indices
            if (score := self.score(query, index)) > 0
        ]
        hits.sort(key=lambda pair: pair[1], reverse=True)
        return hits[:top_k]
