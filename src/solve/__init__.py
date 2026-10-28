"""Giải từng bước có kiểm chứng. Điểm vào duy nhất: ``solve(item)``."""

from __future__ import annotations

import logging
from functools import lru_cache

from src.core.schema import Item, Submission
from src.solve.base import SOLVERS, Solution, Step

# Đăng ký hàm giải của từng mảng kiến thức.
from src.solve import calculus, discrete, linalg, mml, probstat  # noqa: F401,E402

__all__ = ["Solution", "Step", "solve", "solve_unchecked", "solver_key"]

log = logging.getLogger(__name__)


def solver_key(item: Item) -> str | None:
    """Khoá chọn hàm giải: ``meta.task`` trước, rồi mã template, rồi kiểu đáp án."""
    meta = item.meta
    for key in (meta.get("task"), meta.get("template")):
        if key and key in SOLVERS:
            return key
    if item.integrand:
        return "integral"
    if "matrix" in meta and "eigenvalue" in meta:
        return "eigenvector"
    if "A" in meta and "b" in meta:
        return "linear_system"
    return None


def solve_unchecked(item: Item) -> Solution | None:
    key = solver_key(item)
    if key is None:
        return None
    try:
        return SOLVERS[key](item)
    except Exception:                       # hàm giải lỗi thì coi như không có lời giải
        log.exception("Hàm giải %s lỗi trên %s", key, item.item_id)
        return None


@lru_cache(maxsize=8192)
def _verified(item_json: str) -> Solution | None:
    from src.verify.registry import verifier_for

    item = Item.model_validate_json(item_json)
    solution = solve_unchecked(item)
    if solution is None or not solution.steps:
        return None
    try:
        result = verifier_for(item.subject.value).verify(
            item, Submission(item_id=item.item_id, final_answer=solution.answer)
        )
    except Exception:
        return None
    if result.final_answer_correct is not True:
        # Lời giải không ra đúng đáp án của đề: KHÔNG đưa cho người học.
        log.warning("Lời giải của %s không qua bộ chấm: %r", item.item_id, solution.answer)
        return None
    return solution


def solve(item: Item) -> Solution | None:
    """Lời giải từng bước, chỉ khi bộ chấm xác nhận bước cuối ra đúng đáp án."""
    return _verified(item.model_dump_json())
