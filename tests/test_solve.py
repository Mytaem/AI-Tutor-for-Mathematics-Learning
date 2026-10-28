"""Bộ giải từng bước: mỗi dạng bài phải có lời giải QUA BỘ CHẤM.

Chạy đủ 4.955 đề mất vài phút nên để ở ``scripts/audit_solutions.py``; ở đây lấy
MỘT đề cho mỗi dạng bài của mỗi môn — đủ để bắt hàm giải hỏng hay dạng bài mới
chưa có hàm giải.
"""

import pytest

from src.api.app import _load_bank
from src.solve import base, solve, solver_key
from src.solve.base import Solution, Step

SUBJECTS = ("MAE101", "MAD101", "MAI391", "MAS291")


def _one_per_kind(subject: str):
    picked = {}
    for item in _load_bank(subject).items.values():
        kind = item.meta.get("template") or item.meta.get("task") or item.item_id
        picked.setdefault(kind, item)
    return list(picked.values())


@pytest.mark.parametrize("subject", SUBJECTS)
def test_moi_dang_bai_co_loi_giai_da_kiem(subject):
    missing = [item.item_id for item in _one_per_kind(subject) if solve(item) is None]
    assert missing == [], f"{subject}: chưa có lời giải qua bộ chấm cho {missing}"


@pytest.mark.parametrize("subject", SUBJECTS)
def test_moi_buoc_co_viec_can_lam(subject):
    for item in _one_per_kind(subject)[:10]:
        solution = solve(item)
        assert solution.steps and all(step.action for step in solution.steps)
        assert solution.theory and solution.formula


def test_loi_giai_sai_khong_bao_gio_den_tay_nguoi_hoc(monkeypatch):
    item = _one_per_kind("MAS291")[0]
    key = solver_key(item)
    monkeypatch.setitem(base.SOLVERS, key, lambda _: Solution([Step("bịa")], answer="0.123456789"))
    from src.solve import _verified
    _verified.cache_clear()
    try:
        assert solve(item) is None
    finally:
        _verified.cache_clear()


def test_dap_an_gioi_han_trong_ngan_hang_dung_bang_sympy():
    """17 đề lim(x→∞) bậc 1 từng có đáp án sai: sinh viên trả lời đúng bị chấm sai."""
    import sympy as sp

    x = sp.Symbol("x")
    wrong = []
    for item in _load_bank("MAE101").items.values():
        if item.meta.get("task") != "limit":
            continue
        point = sp.oo if str(item.meta["point"]) == "oo" else sp.sympify(item.meta["point"])
        if sp.simplify(sp.limit(sp.sympify(item.meta["expr"]), x, point) - sp.sympify(item.answer_text)) != 0:
            wrong.append(item.item_id)
    assert wrong == []
