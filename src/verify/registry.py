"""Tra bộ chấm theo môn học.

Mỗi môn là một cách GHÉP các bộ chấm mảng kiến thức (xem ``composite.py``),
theo đúng đề cương môn:

- MAE101 = đại số tuyến tính (ch7–10) + giải tích (ch1–6)
- MAI391 = Math for ML + đại số tuyến tính (định thức, trị riêng của ch4)
- MAS291 = xác suất – thống kê (kiểm chéo bằng Monte Carlo)

Thêm một môn mới = chọn các mảng cần ghép rồi đăng ký ở đây. Mọi tầng phía trên
(tutor engine, guardrail, API) chỉ gọi ``verifier_for`` nên không phải sửa gì.
"""

from __future__ import annotations

from typing import Callable

from src.core.schema import Subject
from src.verify.base import Verifier
from src.verify.calculus import CalculusVerifier
from src.verify.composite import CompositeVerifier
from src.verify.linalg import LinearAlgebraVerifier
from src.verify.mml import MMLVerifier
from src.verify.probstat import ProbStatVerifier

_FACTORIES: dict[Subject, Callable[[], Verifier]] = {
    # Thứ tự quan trọng: bộ chấm cuối là mặc định cho bài không bộ nào nhận.
    Subject.MAE101: lambda: CompositeVerifier(Subject.MAE101, [LinearAlgebraVerifier(), CalculusVerifier()]),
    Subject.MAI391: lambda: CompositeVerifier(Subject.MAI391, [MMLVerifier(), LinearAlgebraVerifier()]),
    Subject.MAS291: lambda: CompositeVerifier(Subject.MAS291, [ProbStatVerifier()]),
}


def supported_subjects() -> list[Subject]:
    return list(_FACTORIES)


def verifier_for(subject: Subject | str) -> Verifier:
    subject = Subject(subject)
    if subject not in _FACTORIES:
        raise KeyError(f"Chưa có bộ chấm cho môn {subject.value}")
    return _FACTORIES[subject]()
