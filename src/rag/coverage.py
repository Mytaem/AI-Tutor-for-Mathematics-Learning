"""Chương nào THỰC SỰ có giáo trình trong kho, chương nào không.

**Vì sao cần.** Hỏi "khoảng tin cậy là gì?" mà kho MAS291 không có chương
Khoảng tin cậy thì hệ thống vẫn trả về một đoạn của chương Xác suất — đúng môn,
sai chủ đề, và nghe như một câu trả lời thật. Với một gia sư thì đó là hành vi
tệ nhất: thà nói "chưa có tài liệu chương này" còn hơn trả lời trôi chảy mà sai.

**Cái bẫy khi đo.** Nhãn chương trong kho lấy từ tiêu đề file PDF ("Graph
Theory", "Chapter 2: Probability"), còn khoá chương trong ``data/skills`` là
"Ch6 Graph Theory", "Ch2 Probability". So chuỗi thẳng thì ba trong bốn môn báo
"thiếu toàn bộ" trong khi tài liệu nằm ngay đó. Phải chuẩn hoá hai bên về cùng
một dạng rồi mới so.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from src.core.itembank import ItemBank
from src.core.syllabus import chapters_of, subject_of

#: Tiền tố đánh số chương, cả hai cách viết: "Ch4 ", "Chapter 4: ".
_PREFIX = re.compile(r"^\s*(?:chapter|chuong|ch)\s*\d+\s*[:.\-]?\s*", re.IGNORECASE)
#: Từ nối, bỏ đi để "Sets, Functions, Sequences & Sums" khớp "sets functions sequences sums".
_NOISE = re.compile(r"\b(and|the|of|a|an|to|in|for|techniques|theory)\b")

#: Viết tắt trong tên chương của giáo trình ↔ chữ đầy đủ trên slide.
#: Thiếu bảng này thì "Ch4 Continuous RVs" không khớp "Chapter 4: Continuous
#: Random Variables", và hệ thống báo thiếu một chương đang có đủ tài liệu.
_ABBREV = {
    "rvs": "random variables",
    "rv": "random variable",
    "ci": "confidence interval",
    "pca": "principal component analysis",
    "svm": "support vector machine",
    "svd": "singular value decomposition",
}


def _words(text: str) -> set[str]:
    """Tách từ để so khớp: bỏ dấu, mở viết tắt, bỏ số nhiều.

    Bỏ số nhiều là cần thiết chứ không phải cho đẹp: kỹ năng tên "P-values" mà
    thuật ngữ là "p-value" thì không có một từ nào trùng, và cả phép khớp chương
    trượt sạch.
    """
    folded = unicodedata.normalize("NFD", text.lower())
    folded = "".join(c for c in folded if unicodedata.category(c) != "Mn")
    out: set[str] = set()
    for word in re.findall(r"[a-z]{2,}", folded):
        for piece in (_ABBREV.get(word) or word).split():
            if len(piece) < 3:
                continue
            # Số nhiều tiếng Anh: bỏ "s" cuối, trừ các từ vốn kết thúc bằng "ss".
            out.add(piece[:-1] if piece.endswith("s") and not piece.endswith("ss") else piece)
    return out


def normalise(label: str) -> set[str]:
    """Nhãn chương → tập từ khoá so sánh được.

    Bỏ dấu, bỏ tiền tố số chương, bỏ từ nối, tách thành tập từ. Trả về TẬP chứ
    không phải chuỗi vì thứ tự từ giữa hai nguồn không giống nhau.
    """
    folded = unicodedata.normalize("NFD", label.lower())
    folded = "".join(c for c in folded if unicodedata.category(c) != "Mn")
    folded = _PREFIX.sub("", folded.replace("&", " "))
    return _words(_NOISE.sub(" ", folded))


@dataclass(frozen=True)
class ChapterCoverage:
    chapter: str
    name_vi: str
    chunks: int
    sources: tuple[str, ...]

    @property
    def covered(self) -> bool:
        return self.chunks > 0


def _corpus_labels(index, subject: str) -> dict[str, tuple[int, set[str]]]:
    """Nhãn chương có trong kho cho một môn: nhãn -> (số đoạn, nguồn)."""
    out: dict[str, tuple[int, set[str]]] = {}
    for chunk in index.chunks:
        # Đoạn "taxonomy:*" là bảng bẫy viết tay, không phải giáo trình — đếm
        # chúng vào thì chương nào cũng trông như đã có tài liệu.
        if chunk.subject != subject or chunk.source.startswith("taxonomy:"):
            continue
        count, sources = out.get(chunk.chapter, (0, set()))
        out[chunk.chapter] = (count + 1, sources | {chunk.source})
    return out


def chapter_coverage(index, subject: str) -> list[ChapterCoverage]:
    """Từng chương của môn: có bao nhiêu đoạn giáo trình, từ nguồn nào."""
    bank = ItemBank.load(subject)
    labels = _corpus_labels(index, subject)
    normalised = {label: normalise(label) for label in labels}

    out: list[ChapterCoverage] = []
    for chapter in chapters_of(bank):
        wanted = normalise(chapter.chapter)
        total = 0
        sources: set[str] = set()
        for label, words in normalised.items():
            # Khớp khi tập từ của một bên nằm trong bên kia. Dùng bao hàm chứ
            # không dùng bằng nhau: tiêu đề slide hay dài hơn tên chương
            # ("Chapter 5: Vector Calculus" với "Vector Calculus").
            if wanted and words and (wanted <= words or words <= wanted):
                count, chunk_sources = labels[label]
                total += count
                sources |= chunk_sources
        out.append(ChapterCoverage(
            chapter=chapter.chapter,
            name_vi=chapter.name_vi,
            chunks=total,
            sources=tuple(sorted(sources)),
        ))
    return out


def missing_chapters(index, subject: str) -> list[ChapterCoverage]:
    return [row for row in chapter_coverage(index, subject) if not row.covered]


#: Dưới ngưỡng này thì coi như môn đó KHÔNG có sách giáo trình chung để bù.
#: Ba môn có sách thật đang ở mức hàng nghìn đoạn (OpenStax 3.083, Rosen 4.729,
#: Deisenroth 1.177), môn không có sách chỉ còn vài chục đoạn lẻ. Ngưỡng 300
#: nằm giữa hai mức đó, không cần tinh chỉnh.
TEXTBOOK_MIN_CHUNKS = 300


def general_material(index, subject: str) -> int:
    """Số đoạn KHÔNG gắn được vào chương nào — tức sách giáo trình chung.

    Sách giáo trình vào kho dưới một nhãn duy nhất là tên sách, nên không chia
    được theo chương. Nó vẫn truy xuất được bình thường, và với ba môn có sách
    thì đó là nguồn bù cho những chương chưa có slide. Phải tách con số này ra,
    nếu không ta sẽ báo "thiếu chương" cho một chương mà sách phủ đầy đủ.
    """
    attributed = {
        label
        for row in chapter_coverage(index, subject)
        for label in row.sources
    }
    return sum(
        1
        for chunk in index.chunks
        if chunk.subject == subject
        and not chunk.source.startswith("taxonomy:")
        and chunk.source not in attributed
    )


def has_material_for(index, subject: str, chapter: str | None) -> bool:
    """Có tài liệu nào để trả lời về chương này không?

    Đúng khi chương có slide riêng, HOẶC khi môn có sách giáo trình chung đủ
    lớn để bù. Sai thì tầng trên phải nói thẳng là chưa có tài liệu, chứ không
    được trả về một đoạn của chương khác.
    """
    if chapter is None:
        return True
    if general_material(index, subject) >= TEXTBOOK_MIN_CHUNKS:
        return True

    rows = chapter_coverage(index, subject)

    # Không một chương nào gắn được đoạn nào: kho này không mang nhãn chương,
    # nên ta KHÔNG BIẾT GÌ về độ phủ theo chương — và không biết thì không được
    # từ chối. Thiếu nhánh này thì một kho nạp mà quên gắn nhãn chương sẽ làm
    # MỌI câu hỏi bị trả "chưa có tài liệu", tức là hỏng toàn bộ.
    #
    # Chỉ dám kết luận "chương này thiếu" khi thấy các chương KHÁC có nhãn hẳn
    # hoi — lúc đó mới chứng tỏ việc gắn nhãn hoạt động và sự vắng mặt là thật.
    if not any(row.covered for row in rows):
        return True

    return any(row.covered for row in rows if row.chapter == chapter)


def chapter_for_terms(subject: str, terms: list[str]) -> str | None:
    """Chương của môn mà các thuật ngữ tiếng Anh này thuộc về.

    Dùng để biết câu hỏi đang nhắm chương nào, từ đó trả lời thẳng là chương đó
    chưa có tài liệu. Suy từ ``name_en`` của kỹ năng — cùng nguồn mà từ điển
    thuật ngữ dùng, nên hai bên nhất quán.
    """
    if not terms:
        return None
    bank = ItemBank.load(subject)
    words = _words(" ".join(terms))
    if not words:
        return None

    best, best_score, best_exact = None, 0, False
    for skill in bank.skills.values():
        own = _words(skill.name_en or "")
        if not own:
            continue
        score = len(words & own)
        if score > best_score:
            best, best_score, best_exact = skill.chapter, score, words == own

    # Trùng ĐÚNG MỘT từ thì không tính: "t distribution" khớp "Binomial
    # distribution" chỉ vì chữ "distribution", và tin vào đó thì có ngày ta từ
    # chối oan một câu hỏi mà giáo trình có đủ tài liệu. Thà bỏ sót một lần từ
    # chối đúng còn hơn chặn oan người học.
    #
    # Ngoại lệ: hai tập từ TRÙNG KHÍT. "p-value" và tên kỹ năng "P-values" đều
    # rút về đúng {"value"} — một từ, nhưng là toàn bộ cả hai bên, nên đó là
    # khớp chắc chứ không phải trùng hú hoạ một từ chung.
    return best if best_score >= 2 or best_exact else None


def report(index) -> str:
    """Bảng độ phủ cho cả bốn môn, in ra cho người đọc."""
    lines = []
    for subject in ("MAE101", "MAD101", "MAI391", "MAS291"):
        rows = chapter_coverage(index, subject)
        gaps = [row for row in rows if not row.covered]
        lines.append(f"=== {subject} — {len(rows) - len(gaps)}/{len(rows)} chương có giáo trình ===")
        for row in rows:
            mark = "  ok " if row.covered else "THIẾU"
            lines.append(f"  {mark}  {row.name_vi:40} {row.chunks:>5} đoạn")
        if gaps:
            lines.append(f"  → cần bổ sung: {', '.join(row.name_vi for row in gaps)}")
    return "\n".join(lines)
