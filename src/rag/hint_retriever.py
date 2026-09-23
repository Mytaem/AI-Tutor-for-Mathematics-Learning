"""Lấy đoạn giáo trình cho gợi ý — cầu nối giữa kho RAG và bộ sinh gợi ý.

Ba quyết định ở đây đều rút ra từ đo đạc, không phải suy đoán:

1. **Truy vấn bằng TÊN TIẾNG ANH của kỹ năng, không bằng câu tiếng Việt.**
   Giáo trình của trường là tiếng Anh. Hỏi "tích phân từng phần" thì BM25 không
   có gì để khớp nên kéo về mấy trang có chú thích tiếng Việt lạc đề (trang định
   nghĩa "hàm xác định từng phần"), trong khi hỏi "integration by parts" trả đúng
   mục 3.1 Integration by Parts. bge-m3 đa ngữ có bắc cầu được, nhưng chỉ thắng
   khi BM25 không kéo ngược lại — mà mỗi đề đều đã gắn sẵn skill, nên dùng luôn
   ``skill.name_en`` là chắc chắn nhất.

2. **Loại hẳn chunk ``pitfall``.** Chúng được sinh từ taxonomy lỗi, mà mô tả lỗi
   thì thường chứa chính đáp án ("Hệ vô nghiệm nhưng bài làm vẫn đưa ra nghiệm").
   Đưa vào prompt mức < 4 là làm lộ đáp án qua cửa sau. Phần chẩn đoán của prompt
   đã mang sẵn câu gợi ý của mã lỗi rồi, nên không mất gì.

3. **Đoạn lấy về vẫn phải qua guardrail.** Sách có ví dụ mẫu, và ví dụ mẫu có thể
   chính là bài đang hỏi kèm lời giải. Đoạn nào nộp lên mà verifier chấm đúng thì
   bỏ, y như với câu gợi ý do LLM sinh.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from src.core.schema import Item, Skill
from src.rag.chunking import ChunkType
from src.rag.store import RagIndex
from src.tutor.guardrail import check_leak
from src.tutor.hint_policy import HintLevel

#: Mức 1 cần định nghĩa/công thức; mức 2 cần lời bàn và ví dụ chỉ ra chỗ dễ sai.
#:
#: Mỗi mức là một DANH SÁCH TẦNG: hết tầng đầu không đủ đoạn thì hạ xuống tầng
#: sau. Cần thế vì bộ phân loại loại chunk bám vào chữ "Definition"/"Theorem"
#: trong sách, mà tài liệu MAS291 là slide nên gần như không có chữ đó — lọc
#: cứng theo định nghĩa/định lý thì cả môn thống kê không lấy được đoạn nào.
#: ``exercise`` và ``pitfall`` không bao giờ có mặt: một bên là đề bài, một bên
#: là mô tả lỗi có thể chứa đáp án.
LEVEL_TYPES: dict[HintLevel, list[list[ChunkType]]] = {
    HintLevel.CONCEPT: [
        [ChunkType.DEFINITION, ChunkType.THEOREM, ChunkType.FORMULA],
        [ChunkType.REMARK, ChunkType.PROSE],
        [ChunkType.EXAMPLE],
    ],
    HintLevel.PITFALL: [
        [ChunkType.REMARK, ChunkType.THEOREM, ChunkType.EXAMPLE],
        [ChunkType.PROSE, ChunkType.DEFINITION, ChunkType.FORMULA],
    ],
}

#: Độ dài đoạn đưa vào prompt. Dài hơn thì model nhỏ bắt đầu chép nguyên văn.
MAX_CHARS = 600


def make_hint_retriever(index: RagIndex, skills: dict[str, Skill], *, top_k: int = 2):
    """Dựng hàm ``(item, level) -> [(nội dung, nhãn nguồn)]`` cho ``LLMHintGenerator``."""

    def retrieve(item: Item, level: HintLevel) -> list[tuple[str, str]]:
        tiers = LEVEL_TYPES.get(level)
        if tiers is None:
            return []

        query = _query_for(item, skills)
        if not query:
            return []

        passages: list[tuple[str, str]] = []
        seen: set[str] = set()
        for types in tiers:
            for hit in index.search(query, top_k=top_k * 3, subject=item.subject.value, types=types):
                text = " ".join(hit.chunk.text.split())[:MAX_CHARS]
                if text in seen or check_leak(text, item, level).leaked:
                    continue
                seen.add(text)
                passages.append((text, hit.source_label))
                if len(passages) == top_k:
                    return passages
        return passages

    return retrieve


def _query_for(item: Item, skills: dict[str, Skill]) -> str:
    """Tên tiếng Anh của các kỹ năng gắn với đề; không có thì đành dùng tên tiếng Việt."""
    parts: list[str] = []
    for skill_id in item.skills[:2]:
        skill = skills.get(skill_id)
        if skill is None:
            continue
        parts.append(skill.name_en or skill.name_vi)
    return " ".join(parts)


@lru_cache(maxsize=1)
def load_index(directory: str | Path | None = None) -> RagIndex | None:
    """Nạp kho một lần cho cả tiến trình; chưa dựng kho thì trả None."""
    from src.core.config import ROOT

    path = Path(directory) if directory else ROOT / "data" / "rag_index"
    if not path.exists():
        return None
    return RagIndex.load(path)


def default_hint_retriever(skills: dict[str, Skill], *, top_k: int = 2):
    """Bộ truy xuất dùng kho mặc định; chưa có kho thì trả về hàm rỗng.

    Hệ thống phải chạy được khi chưa dựng index — gợi ý vẫn có, chỉ là không
    kèm trích dẫn giáo trình.
    """
    index = load_index()
    if index is None:
        return lambda item, level: []
    return make_hint_retriever(index, skills, top_k=top_k)
