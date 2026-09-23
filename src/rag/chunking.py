"""Chia tài liệu thành chunk theo CẤU TRÚC, không theo độ dài cố định.

Cắt giáo trình toán theo kiểu "mỗi 500 ký tự một chunk" là hỏng: một định nghĩa
bị cắt làm đôi thì cả hai nửa đều vô dụng, còn một công thức dính đuôi ví dụ
của mục khác thì gây nhiễu. Sách toán vốn đã có cấu trúc rõ — Định nghĩa, Định
lý, Ví dụ, Chú ý — nên ta cắt đúng theo các mốc đó.

Nhãn ``type`` của mỗi chunk không phải để trang trí. Hint mức 1 ("nhắc khái
niệm") chỉ truy xuất trong ``DEFINITION`` và ``FORMULA``; hint mức 2 ("cảnh báo
bẫy") chỉ truy xuất trong ``PITFALL``. Lọc theo nhãn trước khi tìm kiếm giúp
giảm nhiễu hơn hẳn so với việc tìm trên toàn bộ kho.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class ChunkType(str, Enum):
    DEFINITION = "definition"
    THEOREM = "theorem"
    FORMULA = "formula"
    EXAMPLE = "example"
    REMARK = "remark"
    PITFALL = "pitfall"      # bẫy thường gặp, viết tay theo taxonomy lỗi
    EXERCISE = "exercise"
    PROSE = "prose"          # văn xuôi không rơi vào loại nào ở trên


#: Các mốc mở đầu một đơn vị kiến thức, cả tiếng Việt lẫn tiếng Anh.
#: Thứ tự quan trọng: mẫu nào đặc hiệu hơn phải đứng trước.
_MARKERS: tuple[tuple[ChunkType, str], ...] = (
    (ChunkType.DEFINITION, r"Định\s*nghĩa|Definition"),
    (ChunkType.THEOREM, r"Định\s*l[ýi]|Theorem|Hệ\s*quả|Corollary|Bổ\s*đề|Lemma|Mệnh\s*đề|Proposition|Tính\s*chất"),
    (ChunkType.FORMULA, r"Công\s*thức|Formula|Quy\s*tắc|Rule|Bảng\s*nguyên\s*hàm"),
    (ChunkType.EXAMPLE, r"Ví\s*dụ|Example|Bài\s*giải|Lời\s*giải"),
    (ChunkType.PITFALL, r"Lưu\s*ý|Chú\s*ý|Cảnh\s*báo|Sai\s*lầm|Pitfall|Common\s*mistake"),
    (ChunkType.REMARK, r"Nhận\s*xét|Remark|Note"),
    (ChunkType.EXERCISE, r"Bài\s*tập|Exercise|Luyện\s*tập"),
)

#: Nhận mốc ở đầu dòng, cho phép có số thứ tự phía sau ("Ví dụ 2.3.", "Định lý 1:").
_MARKER_PATTERN = re.compile(
    r"^[ \t]*(?P<marker>" + "|".join(pattern for _, pattern in _MARKERS) + r")"
    r"(?P<number>[\s.:]*\d+(?:\.\d+)*)?[\s.:)-]*",
    re.MULTILINE | re.IGNORECASE,
)

_TYPE_BY_INDEX = [chunk_type for chunk_type, _ in _MARKERS]

#: Giới hạn độ dài để một chunk không phình quá to khi tài liệu thiếu mốc.
MAX_CHARS = 1200
MIN_CHARS = 40


@dataclass
class Chunk:
    """Một đơn vị kiến thức có thể truy xuất độc lập."""

    text: str
    chunk_type: ChunkType = ChunkType.PROSE
    subject: str = ""
    chapter: str = ""
    skill_ids: list[str] = field(default_factory=list)
    source: str = ""
    page: int | None = None
    chunk_id: str = ""

    def __post_init__(self) -> None:
        self.text = self.text.strip()

    @property
    def metadata(self) -> dict[str, object]:
        return {
            "chunk_id": self.chunk_id,
            "type": self.chunk_type.value,
            "subject": self.subject,
            "chapter": self.chapter,
            "skill_ids": list(self.skill_ids),
            "source": self.source,
            "page": self.page,
        }


#: Dấu hiệu NGAY TRONG CÂU của một định nghĩa, dùng khi không có mốc mở đầu.
#:
#: Cần thiết vì mốc ở trên chỉ nhận chữ "Definition"/"Định nghĩa" đứng đầu dòng —
#: đúng với sách, sai với slide. Slide MAS291 viết "Conditional Probability The
#: conditional probability of an event B given A, denoted as P(B|A), is ..." nên
#: cả môn thống kê không có lấy một chunk `definition` nào, và bộ lọc theo loại
#: của gợi ý mức 1 không còn gì để chọn.
_DEFINITION_CUES = re.compile(
    r"\bis defined (?:as|to be)\b|\bwe define\b|\bis called\b|\bare called\b"
    r"|\bdenoted (?:by|as)\b|\bif and only if\b"
    r"|được\s+gọi\s+là|được\s+định\s+nghĩa|k[ýy]\s*hiệu\s+là",
    re.IGNORECASE,
)


def classify_prose(text: str) -> ChunkType:
    """Phân loại đoạn không có mốc mở đầu — chỉ dám kết luận khi câu chữ nói rõ."""
    return ChunkType.DEFINITION if _DEFINITION_CUES.search(text) else ChunkType.PROSE


def classify_marker(marker: str) -> ChunkType:
    """Mốc này mở đầu loại nội dung nào?"""
    for chunk_type, pattern in _MARKERS:
        if re.fullmatch(pattern, marker.strip(), flags=re.IGNORECASE):
            return chunk_type
    return ChunkType.PROSE


#: Ranh giới cắt, từ "tự nhiên" nhất tới thô nhất: đoạn văn -> câu -> dòng.
_SEPARATORS = (r"\n\s*\n", r"(?<=[.!?:;])\s+", r"\n")


def _atoms(text: str, limit: int, level: int = 0) -> list[str]:
    """Chặt ``text`` thành các mẩu không mẩu nào dài quá ``limit``.

    Thử ranh giới tự nhiên nhất trước; chỉ mẩu nào VẪN quá dài mới bị chặt tiếp
    ở tầng thô hơn. Cuối cùng mới cắt theo từ — không bao giờ cắt giữa một từ,
    trừ khi bản thân từ đó dài hơn giới hạn.
    """
    if len(text) <= limit:
        return [text]
    if level < len(_SEPARATORS):
        parts = [p.strip() for p in re.split(_SEPARATORS[level], text) if p.strip()]
        if len(parts) > 1:
            return [atom for part in parts for atom in _atoms(part, limit, level + 1)]
        return _atoms(text, limit, level + 1)

    pieces: list[str] = []
    current = ""
    for word in text.split():
        while len(word) > limit:  # "từ" dài bất thường, ví dụ chữ dính liền khi trích PDF
            if current:
                pieces.append(current)
                current = ""
            pieces.append(word[:limit])
            word = word[limit:]
        if current and len(current) + 1 + len(word) > limit:
            pieces.append(current)
            current = word
        else:
            current = f"{current} {word}" if current else word
    if current:
        pieces.append(current)
    return pieces


def _split_long(text: str, limit: int = MAX_CHARS) -> list[str]:
    """Cắt một khối quá dài thành các chunk không vượt ``limit`` ký tự.

    Bản trước chỉ cắt tại dòng trống giữa các đoạn văn. PDF giáo trình thường
    chỉ xuống dòng đơn nên cả trang thành một khối không cắt được: đo trên kho
    thật, 23% chunk vượt giới hạn, dài nhất 6568 ký tự. Chunk dài làm vector
    embedding bị "pha loãng" nhiều chủ đề, và làm bge-m3 chậm đi theo bình
    phương độ dài.
    """
    if len(text) <= limit:
        return [text]

    pieces: list[str] = []
    current: list[str] = []
    length = 0
    for atom in _atoms(text, limit):
        if current and length + 1 + len(atom) > limit:
            pieces.append("\n".join(current))
            current, length = [], 0
        current.append(atom)
        length += len(atom) + (1 if length else 0)
    if current:
        pieces.append("\n".join(current))
    return pieces


def chunk_text(
    text: str,
    *,
    subject: str = "",
    chapter: str = "",
    source: str = "",
    page: int | None = None,
) -> list[Chunk]:
    """Chia một đoạn văn bản thành các chunk theo mốc cấu trúc."""
    if not text or not text.strip():
        return []

    matches = list(_MARKER_PATTERN.finditer(text))

    # Không tìm thấy mốc nào: rơi về cắt theo đoạn văn, nhãn PROSE.
    if not matches:
        return [
            Chunk(piece, classify_prose(piece), subject, chapter, source=source, page=page)
            for piece in _split_long(text)
            if len(piece.strip()) >= MIN_CHARS
        ]

    chunks: list[Chunk] = []

    # Phần đứng trước mốc đầu tiên vẫn có thể là nội dung có ích.
    preamble = text[: matches[0].start()].strip()
    if len(preamble) >= MIN_CHARS:
        for piece in _split_long(preamble):
            chunks.append(Chunk(piece, classify_prose(piece), subject, chapter, source=source, page=page))

    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.start():end].strip()
        if len(body) < MIN_CHARS:
            continue

        chunk_type = classify_marker(match.group("marker"))
        for piece in _split_long(body):
            chunks.append(Chunk(piece, chunk_type, subject, chapter, source=source, page=page))

    return chunks


def assign_ids(chunks: list[Chunk], prefix: str = "c") -> list[Chunk]:
    """Gán mã duy nhất cho từng chunk, để tham chiếu lại khi trích dẫn nguồn."""
    for index, chunk in enumerate(chunks):
        chunk.chunk_id = f"{prefix}-{index:05d}"
    return chunks
