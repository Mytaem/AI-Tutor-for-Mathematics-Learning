"""Thẻ kiến thức: mỗi kỹ năng một thẻ — lý thuyết, công thức, lỗi hay gặp, ví dụ giải.

Không viết tay và không do mô hình sinh. Thẻ được GHÉP từ ba nguồn đã có kiểm chứng:

- bộ giải từng bước (``src/solve``): kiến thức nền và công thức của mỗi dạng bài,
  cùng một ví dụ giải mà bước cuối đã qua bộ chấm;
- bảng mã lỗi: những sai lầm có thật của môn, kèm câu gợi ý tự kiểm;
- bảng kỹ năng: tên, chương, kỹ năng cần biết trước.

Vì vậy thẻ luôn khớp với cách hệ thống chấm và gợi ý, và dùng được ngay lập tức —
không phải chờ mô hình như phần hỏi đáp.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from functools import lru_cache

from src.rag.glossary import _fold, english_terms

SUBJECTS = ("MAE101", "MAD101", "MAI391", "MAS291")


@dataclass
class Mistake:
    name: str
    description: str
    self_check: str


@dataclass
class Example:
    item_id: str
    statement: str
    steps: list[dict]
    answer: str


@dataclass
class Card:
    skill_id: str
    subject: str
    chapter_vi: str
    name_vi: str
    name_en: str
    theory: list[str] = field(default_factory=list)
    formulas: list[str] = field(default_factory=list)
    methods: list[str] = field(default_factory=list)
    mistakes: list[Mistake] = field(default_factory=list)
    prerequisites: list[str] = field(default_factory=list)
    example: Example | None = None
    item_count: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


def _unique(values) -> list[str]:
    seen, out = set(), []
    for value in values:
        value = (value or "").strip()
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out


def _sentences(texts, limit: int = 5) -> list[str]:
    """Bỏ trùng theo CÂU: nhiều dạng bài cùng kết bằng "Nguyên hàm là một HỌ hàm…"."""
    sentences = [part.strip() for text in texts for part in re.split(r"(?<=[.!?])\s+", text or "")]
    return _unique(sentences)[:limit]


@lru_cache(maxsize=8)
def cards_for(subject: str) -> tuple[Card, ...]:
    from src.api.app import _load_bank
    from src.core.itembank import load_course_error_codes
    from src.core.pretty import pretty_math
    from src.core.syllabus import TASK_NAMES_VI, display_name
    from src.solve import solve

    bank = _load_bank(subject)
    errors = load_course_error_codes(subject)

    # Mỗi kỹ năng: một đề đại diện cho MỖI dạng bài, ưu tiên đề dễ nhất — ví dụ
    # trên thẻ nên là bài mở đầu, không phải bài khó nhất.
    by_skill: dict[str, dict[str, object]] = {}
    counts: dict[str, int] = {}
    for item in sorted(bank.items.values(), key=lambda it: (it.difficulty, it.item_id)):
        if not item.skills:
            continue
        primary = item.skills[0]
        counts[primary] = counts.get(primary, 0) + 1
        kind = item.meta.get("template") or item.meta.get("task") or item.item_id
        by_skill.setdefault(primary, {}).setdefault(kind, item)

    cards: list[Card] = []
    for skill in bank.skills.values():
        representatives = list(by_skill.get(skill.skill_id, {}).values())
        solutions = [(item, solve(item)) for item in representatives]
        solutions = [(item, s) for item, s in solutions if s is not None]
        example = None
        if solutions:
            item, solution = solutions[0]
            example = Example(
                item_id=item.item_id,
                statement=pretty_math(item.statement_vi),
                steps=[asdict(step) for step in solution.steps],
                answer=pretty_math(item.answer_text),
            )
        cards.append(Card(
            skill_id=skill.skill_id,
            subject=subject,
            chapter_vi=display_name(subject, skill.chapter),
            name_vi=skill.name_vi,
            name_en=skill.name_en,
            theory=_sentences(s.theory for _, s in solutions),
            formulas=_unique(s.formula for _, s in solutions),
            methods=_unique(item.meta.get("method") or TASK_NAMES_VI.get(item.meta.get("task") or "", "")
                            for item in representatives),
            mistakes=[Mistake(e.name_vi, e.description_vi, e.hint_vi)
                      for e in errors.values() if e.skill_id == skill.skill_id],
            prerequisites=[bank.skills[p].name_vi for p in skill.prerequisites if p in bank.skills],
            example=example,
            item_count=counts.get(skill.skill_id, 0),
        ))
    return tuple(cards)


def all_cards(subject: str | None = None) -> list[Card]:
    subjects = [subject] if subject else SUBJECTS
    return [card for code in subjects for card in cards_for(code)]


def card_by_id(skill_id: str) -> Card | None:
    return next((c for c in all_cards() if c.skill_id == skill_id), None)


# --------------------------------------------------------------------------
# Tìm thẻ cho một câu hỏi tự do
# --------------------------------------------------------------------------

#: Từ chức năng của câu hỏi — xuất hiện ở mọi câu nên không nói gì về chủ đề.
_STOP = set(
    "la gi the nao nhu cach tinh tim lam sao khi nao dung cua va voi cho trong mot cac nhung "
    "em toi minh ban hay giai thich ve co khong duoc bang theo nao sao ra de bai dang".split()
)


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", _fold(text)) if len(w) > 1 and w not in _STOP}


def match_cards(question: str, subject: str | None = None, limit: int = 2) -> list[Card]:
    """Thẻ khớp nhất với câu hỏi, theo tên kỹ năng (Việt, Anh) và tên các dạng bài.

    Điểm = tỉ lệ từ của tên kỹ năng xuất hiện trong câu hỏi, cộng thêm nếu thuật ngữ
    tiếng Anh nhận ra từ câu hỏi trùng tên tiếng Anh của kỹ năng. Dưới ngưỡng thì
    KHÔNG trả thẻ nào — thẻ sai chủ đề tệ hơn không có thẻ.
    """
    asked = _words(question)
    english = [_fold(t) for t in english_terms(question)]
    if not asked and not english:
        return []
    scored = []
    for card in all_cards(subject):
        best = 0.0
        for label in [card.name_vi, card.name_en, *card.methods]:
            words = _words(label)
            hits = len(words & asked)
            if not hits:
                continue
            # Hai chiều: tên ngắn nằm trọn trong câu hỏi ("Gradient descent"), hoặc
            # câu hỏi ngắn nằm trọn trong tên dài ("định lý bayes" trong "Xác suất
            # toàn phần và định lý Bayes") — chiều sau cần >= 2 từ để không khớp bừa.
            best = max(best, hits / len(words), hits / len(asked) if hits >= 2 else 0.0)
        name_en = _fold(card.name_en)
        # "p-value" -> "P-values", "bayes theorem" -> "... Bayes' theorem": so gốc từ.
        if any(term and (term in name_en or term.rstrip("s") in name_en
                         or all(w in name_en for w in term.split())) for term in english):
            best += 0.7          # thuật ngữ nhận ra từ bảng song ngữ: tín hiệu mạnh
        if best >= 0.6:
            scored.append((best, card.item_count, card))
    scored.sort(key=lambda row: (-row[0], -row[1]))
    if not scored:
        return []
    # Thẻ phụ chỉ hiện khi liên quan gần ngang thẻ chính — thẻ lạc đề làm rối hơn giúp.
    top = scored[0][0]
    return [card for score, _, card in scored[:limit] if score >= 0.85 * top]
