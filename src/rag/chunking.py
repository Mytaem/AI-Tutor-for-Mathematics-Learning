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


def classify_marker(marker: str) -> ChunkType:
    """Mốc này mở đầu loại nội dung nào?"""
    for chunk_type, pattern in _MARKERS:
        if re.fullmatch(pattern, marker.strip(), flags=re.IGNORECASE):
            return chunk_type
    return ChunkType.PROSE


def _split_long(text: str, limit: int = MAX_CHARS) -> list[str]:
    """Cắt một khối quá dài theo ranh giới đoạn văn, không cắt giữa câu."""
    if len(text) <= limit:
        return [text]

    pieces: list[str] = []
    current: list[str] = []
    length = 0

    for paragraph in re.split(r"\n\s*\n", text):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if length + len(paragraph) > limit and current:
            pieces.append("\n\n".join(current))
            current, length = [], 0
        current.append(paragraph)
        length += len(paragraph)

    if current:
        pieces.append("\n\n".join(current))
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
            Chunk(piece, ChunkType.PROSE, subject, chapter, source=source, page=page)
            for piece in _split_long(text)
            if len(piece.strip()) >= MIN_CHARS
        ]

    chunks: list[Chunk] = []

    # Phần đứng trước mốc đầu tiên vẫn có thể là nội dung có ích.
    preamble = text[: matches[0].start()].strip()
    if len(preamble) >= MIN_CHARS:
        for piece in _split_long(preamble):
            chunks.append(Chunk(piece, ChunkType.PROSE, subject, chapter, source=source, page=page))

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
