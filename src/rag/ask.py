"""Hỏi đáp lý thuyết dựa trên giáo trình.

Khác hẳn phần sinh gợi ý: ở đây sinh viên hỏi tự do ("định lý giới hạn trung tâm
là gì?"), không gắn với bài tập nào, nên không có đáp án để giấu và không cần
guardrail. Cái cần canh là chuyện KHÁC: mô hình bịa ra kiến thức không có trong
giáo trình.

Ba ràng buộc chống bịa:

1. **Không tìm được đoạn nào đủ liên quan thì từ chối**, không đoán. Câu hỏi
   ngoài phạm vi 4 môn phải nhận được câu trả lời "ngoài phạm vi", chứ không phải
   một đoạn văn nghe có vẻ đúng.
2. **Prompt chỉ chứa đoạn trích**, và nói rõ chỉ được trả lời dựa trên đó.
3. **Luôn kèm nguồn** (tên file, chương, trang) để người đọc tự kiểm.

Không có model thì vẫn trả lời được: trả thẳng các đoạn trích kèm nguồn. Xấu hơn
nhưng vẫn đúng, và đây là đường dự phòng lúc bảo vệ.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.rag.chunking import ChunkType
from src.rag.store import RagIndex

#: Dưới mức tương đồng này coi như câu hỏi ngoài phạm vi.
#:
#: Đo trên kho hiện tại: câu hỏi trong phạm vi cho cosine 0,54–0,60 ("chu trình
#: Euler là gì" 0,60; "định lý giới hạn trung tâm" 0,54), câu ngoài phạm vi cho
#: 0,43–0,46 ("cách nấu phở bò" 0,45; "Messi ghi bao nhiêu bàn" 0,46). Khoảng
#: cách khá hẹp vì bge-m3 nén thang tương đồng, nên ngưỡng này sẽ phải chỉnh lại
#: nếu đổi bộ mã hoá — và đó là lý do nó nằm ở đây kèm số đo, không phải một
#: hằng số vô danh.
MIN_SIMILARITY = 0.50

#: Không lấy đề bài và bẫy thường gặp làm nguồn trả lời lý thuyết.
EXCLUDED = {ChunkType.EXERCISE, ChunkType.PITFALL}

OUT_OF_SCOPE = (
    "Câu này nằm ngoài phần giáo trình mà hệ thống có (MAE101, MAD101, MAI391, MAS291). "
    "Em thử hỏi lại bằng thuật ngữ trong môn, hoặc hỏi thầy cô nhé."
)

SYSTEM_PROMPT = (
    "Bạn là trợ giảng toán đại học, trả lời bằng tiếng Việt, ngắn gọn, chính xác. "
    "CHỈ được dùng thông tin trong các đoạn trích giáo trình được cung cấp. "
    "Không có trong đoạn trích thì nói thẳng là giáo trình không nhắc tới, "
    "TUYỆT ĐỐI không bịa thêm. Trả lời tối đa 5 câu."
)


@dataclass
class Answer:
    text: str
    sources: list[str] = field(default_factory=list)
    passages: list[str] = field(default_factory=list)
    in_scope: bool = True
    used_llm: bool = False


def retrieve(
    index: RagIndex,
    question: str,
    subject: str | None = None,
    top_k: int = 3,
    skill_ids: list[str] | None = None,
):
    """Các đoạn liên quan, đã bỏ đề bài và bẫy thường gặp.

    Trả rỗng khi câu hỏi nằm ngoài phạm vi giáo trình. Kho chưa có embedding thì
    không chặn được gì (không có thang tương đồng), khi đó cứ trả kết quả BM25 —
    thà trả lời hơi lạc còn hơn từ chối mọi câu hỏi.

    ``skill_ids`` thu hẹp về đúng một chương. Nếu lọc chặt đến mức không còn
    đoạn nào thì **nới ra cả môn** rồi tìm lại: người học hỏi đúng chủ đề mà bị
    trả lời "ngoài phạm vi" chỉ vì đoạn tương ứng chưa gắn kỹ năng là sai — kho
    giáo trình gắn kỹ năng còn thưa, đó là hạn chế của dữ liệu chứ không phải
    câu hỏi của họ sai.
    """
    similarity = index.best_similarity(question, subject)
    if similarity is not None and similarity < MIN_SIMILARITY:
        return []
    types = [kind for kind in ChunkType if kind not in EXCLUDED]
    if skill_ids:
        narrowed = index.search(
            question, top_k=top_k, subject=subject, types=types, skill_ids=skill_ids
        )
        if narrowed:
            return narrowed
    return index.search(question, top_k=top_k, subject=subject, types=types)


def build_messages(question: str, hits) -> list[dict]:
    passages = "\n\n".join(
        f"[{position}] ({hit.source_label}) {' '.join(hit.chunk.text.split())[:700]}"
        for position, hit in enumerate(hits, start=1)
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": (
            f"ĐOẠN TRÍCH GIÁO TRÌNH:\n{passages}\n\n"
            f"CÂU HỎI: {question}\n\n"
            "Trả lời dựa trên các đoạn trích trên. Giáo trình bằng tiếng Anh, "
            "hãy diễn đạt lại bằng tiếng Việt."
        )},
    ]


def answer_question(
    question: str,
    index: RagIndex | None,
    *,
    subject: str | None = None,
    skill_ids: list[str] | None = None,
    client=None,
    top_k: int = 3,
) -> Answer:
    if index is None:
        return Answer("Kho giáo trình chưa được dựng — chạy scripts/build_rag_index.py.",
                      in_scope=False)

    hits = retrieve(index, question, subject, top_k, skill_ids)
    if not hits:
        return Answer(OUT_OF_SCOPE, in_scope=False)

    sources = [hit.source_label for hit in hits]
    passages = [" ".join(hit.chunk.text.split())[:700] for hit in hits]

    if client is None:
        # Không có model: trả nguyên đoạn trích. Kém mượt nhưng không bao giờ bịa.
        body = "\n\n".join(f"• ({source}) {text[:400]}" for source, text in zip(sources, passages))
        return Answer(f"Giáo trình có mấy đoạn liên quan sau:\n\n{body}",
                      sources=sources, passages=passages)

    from src.llm.client import LLMError

    try:
        reply = client.chat(build_messages(question, hits), temperature=0.2, max_tokens=320)
    except LLMError:
        body = "\n\n".join(f"• ({source}) {text[:400]}" for source, text in zip(sources, passages))
        return Answer(f"Model đang không trả lời được. Đoạn giáo trình liên quan:\n\n{body}",
                      sources=sources, passages=passages)

    return Answer(reply.text.strip(), sources=sources, passages=passages, used_llm=True)
