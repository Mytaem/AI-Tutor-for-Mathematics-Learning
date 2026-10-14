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


def no_material(chapter_vi: str) -> str:
    """Câu hỏi ĐÚNG chủ đề nhưng kho chưa có tài liệu chương đó.

    Phải phân biệt hẳn với "ngoài phạm vi": câu hỏi này nằm trong chương trình,
    lỗi ở phía dữ liệu của hệ thống chứ không phải ở người hỏi. Nói sai chỗ đó
    là đẩy lỗi của mình sang cho sinh viên.

    Và tuyệt đối không được trả về một đoạn của chương khác cho qua chuyện: với
    một gia sư, trả lời trôi chảy mà sai chủ đề là hành vi tệ nhất — người học
    không có cách nào biết mà đề phòng.
    """
    return (
        f"Câu hỏi này thuộc chương «{chapter_vi}», nhưng kho giáo trình của hệ thống "
        "hiện CHƯA có tài liệu của chương đó, nên thầy không trả lời chắc chắn được. "
        "Đây là thiếu sót của hệ thống, không phải em hỏi sai. Em hỏi thầy cô hoặc "
        "xem trực tiếp slide của chương này nhé."
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
    from src.rag.glossary import english_terms

    # Nối thuật ngữ tiếng Anh vào truy vấn TRƯỚC khi làm bất cứ việc gì khác.
    # Giáo trình là tiếng Anh, câu hỏi là tiếng Việt: không có bước này thì
    # BM25 đóng góp đúng bằng không và chỉ còn vector dày gánh — mà vector đa
    # ngữ cho điểm na ná nhau với mọi đoạn cùng môn, nên kết quả là "đúng môn,
    # sai chủ đề". Đo được: 40% dùng được trước bước này.
    terms = english_terms(question)
    query = f"{question} {' '.join(terms)}" if terms else question

    # Và phải NÓI RÕ dùng hybrid khi đã mở rộng được.
    #
    # ``_fusion_mode`` tự chọn theo ngôn ngữ, mà truy vấn mở rộng vẫn còn tiếng
    # Việt ở đầu nên nó ép về dense và BỎ HẲN BM25 — đúng những từ tiếng Anh
    # vừa nối vào lại không được dùng. Quy tắc đó đo ở EXP-4 trên truy vấn CHƯA
    # mở rộng, khi BM25 thật sự không có gì để khớp; giờ nó có, nên quy tắc cũ
    # không còn áp dụng. Không nhận ra thuật ngữ nào thì vẫn để dense như cũ.
    fusion = "hybrid" if terms else "auto"

    similarity = index.best_similarity(query, subject)
    if similarity is not None and similarity < MIN_SIMILARITY:
        return []
    types = [kind for kind in ChunkType if kind not in EXCLUDED]
    if skill_ids:
        narrowed = index.search(
            query, top_k=top_k, subject=subject, types=types,
            skill_ids=skill_ids, fusion=fusion,
        )
        if narrowed:
            return narrowed
    return index.search(query, top_k=top_k, subject=subject, types=types, fusion=fusion)


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

    # Kiểm TRƯỚC khi truy xuất: nếu câu hỏi nhắm một chương mà kho không có tài
    # liệu, thì mọi đoạn tìm được đều là của chương khác. Trả chúng ra là trả
    # lời trôi chảy mà sai chủ đề — chính cái làm buổi demo thất bại.
    if subject:
        from src.core.syllabus import display_name
        from src.rag.coverage import chapter_for_terms, has_material_for
        from src.rag.glossary import english_terms

        target = chapter_for_terms(subject, english_terms(question))
        if target and not has_material_for(index, subject, target):
            return Answer(no_material(display_name(subject, target)), in_scope=True)

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
