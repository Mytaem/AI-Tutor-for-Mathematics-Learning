"""Bộ sinh lỗi có nhãn cho Toán rời rạc (MAD101).

Phần lớn kiểu sai lấy từ ``discrete.mistakes`` — cùng hàm bộ chấm dùng để chẩn
đoán. Ba nhóm cần dựng riêng vì đáp án là một CÔNG THỨC chứ không phải con số:
lỗi logic (De Morgan, đảo, nghịch) và lỗi hằng số của nghiệm truy hồi.
"""

from __future__ import annotations

import sympy as sp

from src.core.schema import Item
from src.data_gen.error_injector import register
from src.verify import discrete as D


def render(value) -> str:
    if isinstance(value, bool):
        return "có" if value else "không"
    if isinstance(value, sp.Basic):
        return sp.sstr(value)
    return str(value)


def _from_mistakes(code: str):
    def inject(item: Item) -> str | None:
        if item.meta.get("task") not in D.DISCRETE_TASKS:
            return None
        for value, mistake in D.mistakes(item):
            if mistake == code:
                return render(value)
        return None

    inject.__name__ = f"inject_{code.replace('.', '_')}"
    return inject


for _code in (
    D.ERR_ORDER, D.ERR_REPETITION, D.ERR_NOSUB, D.ERR_GCD_LCM, D.ERR_BASE_REVERSED,
    D.ERR_SUM_OFFBYONE, D.ERR_HANDSHAKE, D.ERR_EULER, D.ERR_UNWEIGHTED, D.ERR_CHROMATIC_BOUND,
    D.ERR_TREE_EDGES, D.ERR_TREE_LEAVES, D.ERR_MST_CYCLE,
):
    register(_code)(_from_mistakes(_code))


# --------------------------------------------------------------------------
# Logic
# --------------------------------------------------------------------------

def _formula(item: Item) -> sp.Basic | None:
    if not item.meta.get("task", "").startswith("logic_") or "formula" not in item.meta:
        return None
    return D.parse_logic(item.meta["formula"])


@register(D.ERR_DEMORGAN)
def _de_morgan(item: Item) -> str | None:
    """Phủ định từng mệnh đề mà giữ nguyên ∧/∨."""
    formula, task = _formula(item), item.meta.get("task")
    if formula is None:
        return None
    if task == "logic_negate" and not isinstance(formula, sp.Implies):
        return D.logic_to_text(D.naive_negation(formula))
    if task == "logic_simplify" and isinstance(formula, sp.Not):
        return D.logic_to_text(D.naive_negation(formula.args[0]))
    return None


@register(D.ERR_CONVERSE)
def _converse(item: Item) -> str | None:
    formula = _formula(item)
    if formula is None or item.meta["task"] != "logic_contrapositive":
        return None
    p, q = formula.args
    return D.logic_to_text(sp.Implies(q, p))


@register(D.ERR_INVERSE)
def _inverse(item: Item) -> str | None:
    """¬p → ¬q — sai cho cả bài phản đảo lẫn bài phủ định của p → q."""
    formula = _formula(item)
    if formula is None or not isinstance(formula, sp.Implies):
        return None
    if item.meta["task"] not in ("logic_contrapositive", "logic_negate"):
        return None
    p, q = formula.args
    return D.logic_to_text(sp.Implies(sp.Not(p), sp.Not(q)))


# --------------------------------------------------------------------------
# Truy hồi
# --------------------------------------------------------------------------

@register(D.ERR_REC_INITIAL)
def _wrong_initial_condition(item: Item) -> str | None:
    """Giải lại hệ thức với điều kiện đầu LỆCH: kết quả vẫn thoả hệ thức nhưng sai hằng số."""
    if item.meta.get("task") != "recurrence":
        return None
    a, rhs, initial = D._recurrence(item)
    n = D.N
    shifted = {a(k): v + (1 if k == min(initial) else 0) for k, v in initial.items()}
    solution = sp.rsolve(a(n) - rhs, a(n), shifted)
    return sp.sstr(sp.simplify(solution)) if solution is not None else None
