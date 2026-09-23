"""Khung sinh đề dùng chung cho MAD101, MAS291 và MAI391.

``item_generator.py`` sinh đề MAE101 rất tốt nhưng gắn chặt vào tích phân: mỗi
template trả về (biểu thức dưới dấu tích phân, cận). Ba môn còn lại không có
"biểu thức dưới dấu tích phân" nào cả — đề của chúng là một bộ THAM SỐ trong
``item.meta`` (ma trận, danh sách cạnh, n và p của phân phối nhị thức...), nên
cần một khung khác.

Khung này chỉ lo phần chung: gieo tham số, khử trùng lặp, đánh số, và **bắt mọi
bài phải tự chấm được trước khi nhận**. Chính hàng rào cuối mới là điều đáng
nói: đáp án do máy tính ra vẫn có thể sai kiểu (đưa số thực trong khi verifier
chờ phân số), hoặc rơi vào ca verifier chưa phủ. Bài nào verifier không xác nhận
thì loại — ngân hàng đề vì thế luôn đúng, kể cả khi thêm template mới.

Với MAS291, hàng rào này còn mạnh hơn nữa: verifier của môn tự chạy đối chứng
Monte Carlo, nên đề sinh ra mà công thức giải tích lệch mô phỏng là bị loại ngay
tại đây, không lọt vào ngân hàng.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from typing import Any, Callable

from src.core.schema import AnswerType, Item, Subject

#: Builder nhận bộ sinh số ngẫu nhiên, trả về phần RIÊNG của một đề, hoặc None
#: khi bộ tham số vừa gieo không dùng được (ma trận suy biến, xác suất > 1...).
Draft = dict[str, Any]
Builder = Callable[[random.Random], Draft | None]


@dataclass
class Template:
    """Một *dạng* bài, sinh ra vô số biến thể bằng cách random hoá tham số."""

    template_id: str
    skills: list[str]
    difficulty: float
    build: Builder
    method_vi: str = ""


@dataclass
class Registry:
    """Tập template của một môn."""

    subject: Subject
    prefix: str
    templates: list[Template] = field(default_factory=list)

    def template(self, template_id: str, skills: list[str], difficulty: float, method_vi: str = ""):
        def decorator(function: Builder) -> Builder:
            self.templates.append(Template(template_id, skills, difficulty, function, method_vi))
            return function

        return decorator

    def template_ids(self) -> list[str]:
        return [spec.template_id for spec in self.templates]

    # ------------------------------------------------------------------

    def generate(self, count: int, seed: int = 20260923, validate: bool = True) -> list[Item]:
        """Sinh ``count`` đề khác nhau, chia đều qua các template."""
        from src.core.schema import Submission
        from src.verify.registry import verifier_for

        rng = random.Random(seed)
        verifier = verifier_for(self.subject.value) if validate else None

        items: list[Item] = []
        seen: set[str] = set()
        attempts = 0
        max_attempts = count * 60

        while len(items) < count and attempts < max_attempts:
            spec = self.templates[attempts % len(self.templates)]
            attempts += 1

            try:
                draft = spec.build(rng)
            except (ValueError, ZeroDivisionError, ArithmeticError, TypeError):
                continue
            if draft is None:
                continue

            fingerprint = f"{spec.template_id}|{json.dumps(draft['meta'], sort_keys=True, default=str)}"
            if fingerprint in seen:
                continue

            item = self._assemble(spec, draft, len(items) + 1)
            if verifier is not None:
                try:
                    result = verifier.verify(
                        item, Submission(item_id=item.item_id, final_answer=item.answer_text)
                    )
                except Exception:
                    continue
                if result.final_answer_correct is not True:
                    continue

            seen.add(fingerprint)
            items.append(item)

        return items

    def _assemble(self, spec: Template, draft: Draft, index: int) -> Item:
        meta = dict(draft["meta"])
        meta.setdefault("template", spec.template_id)
        if spec.method_vi:
            meta.setdefault("method", spec.method_vi)
        return Item(
            item_id=f"{self.prefix}-GEN-{spec.template_id}-{index:04d}",
            subject=self.subject,
            skills=list(draft.get("skills") or spec.skills),
            statement_vi=draft["statement_vi"],
            statement_latex=draft.get("statement_latex", ""),
            answer_type=AnswerType(draft["answer_type"]),
            answer=draft["answer"],
            difficulty=draft.get("difficulty", spec.difficulty),
            source="generated",
            meta=meta,
        )
