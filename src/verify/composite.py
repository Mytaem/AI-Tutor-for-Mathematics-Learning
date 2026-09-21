"""Ghép nhiều bộ chấm mảng kiến thức thành bộ chấm của một môn.

Môn học không trùng với mảng kiến thức: MAE101 gồm cả giải tích lẫn đại số
tuyến tính, còn MAI391 dùng lại đại số tuyến tính cho chương phân rã ma trận.
Tổ chức bộ chấm theo MẢNG rồi ghép lại giúp phần đại số tuyến tính viết một
lần, dùng cho cả hai môn — và thêm môn mới chỉ là chọn các mảng cần ghép.

Mỗi bài được giao cho bộ chấm ĐẦU TIÊN nhận nó (``handles``); bộ chấm cuối
danh sách là mặc định cho mọi bài không ai nhận.
"""

from __future__ import annotations

from src.core.schema import Item, StepCheck, Subject, Submission, VerificationResult
from src.verify.base import Verifier
from src.verify.equivalence import EquivalenceResult


class CompositeVerifier(Verifier):
    def __init__(self, subject: Subject, parts: list[Verifier]) -> None:
        if not parts:
            raise ValueError("Cần ít nhất một bộ chấm thành phần")
        self.subject = subject
        self.parts = list(parts)
        self.name = "+".join(part.name for part in self.parts)
        self.verbal_answers = frozenset().union(*(part.verbal_answers for part in self.parts))

    def part_for(self, item: Item) -> Verifier:
        return next((part for part in self.parts if part.handles(item)), self.parts[-1])

    def handles(self, item: Item) -> bool:
        return any(part.handles(item) for part in self.parts)

    def verify(self, item: Item, submission: Submission) -> VerificationResult:
        return self.part_for(item).verify(item, submission)

    def check(self, item: Item, answer: str) -> tuple[EquivalenceResult, list[str]]:
        return self.part_for(item).check(item, answer)

    def check_steps(self, item: Item, steps: list[str]) -> list[StepCheck]:
        return self.part_for(item).check_steps(item, steps)
