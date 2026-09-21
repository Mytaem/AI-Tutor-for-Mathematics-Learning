"""Tra verifier theo môn học.

Thêm một môn mới = viết một lớp con của ``Verifier`` rồi đăng ký ở đây. Mọi tầng
phía trên (tutor engine, API) chỉ gọi ``verifier_for`` nên không phải sửa gì.
"""

from __future__ import annotations

from src.core.schema import Subject
from src.verify.base import Verifier
from src.verify.calculus import CalculusVerifier
from src.verify.linalg_ode import LinalgODEVerifier

_VERIFIERS: dict[Subject, type[Verifier]] = {
    Subject.MAE101: CalculusVerifier,
    Subject.MAI391: LinalgODEVerifier,
}


def supported_subjects() -> list[Subject]:
    return list(_VERIFIERS)


def verifier_for(subject: Subject | str) -> Verifier:
    subject = Subject(subject)
    if subject not in _VERIFIERS:
        raise KeyError(f"Chưa có verifier cho môn {subject.value}")
    return _VERIFIERS[subject]()
