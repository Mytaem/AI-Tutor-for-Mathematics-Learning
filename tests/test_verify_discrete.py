"""Test bộ chấm Toán rời rạc (MAD101).

Test quan trọng nhất là ``TestIndependentCrossCheck``: đáp án chuẩn của bài đếm
được xác nhận bằng LIỆT KÊ VÉT CẠN, của bài truy hồi bằng TÍNH LẶP — hai cách
không dùng công thức nào.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.itembank import ItemBank  # noqa: E402
from src.core.schema import Submission  # noqa: E402
from src.tutor.guardrail import check_leak  # noqa: E402
from src.tutor.hint_policy import HintLevel  # noqa: E402
from src.verify import discrete as D  # noqa: E402
from src.verify.equivalence import ParseError  # noqa: E402
from src.verify.registry import verifier_for  # noqa: E402


@pytest.fixture(scope="module")
def bank() -> ItemBank:
    return ItemBank.load("MAD101")


@pytest.fixture(scope="module")
def verifier():
    return verifier_for("MAD101")


def check(verifier, bank, item_id: str, answer: str):
    return verifier.verify(bank.get(item_id), Submission(item_id=item_id, final_answer=answer))


class TestIndependentCrossCheck:
    def test_moi_bai_dem_va_truy_hoi_deu_khop(self, bank: ItemBank) -> None:
        checked = [i for i in bank.items.values() if i.meta["task"] in ("count", "recurrence")]
        assert len(checked) >= 8
        bad = [f"{i.item_id}: {D.cross_check(i)}" for i in checked if not D.cross_check(i)["agree"]]
        assert bad == [], "\n".join(bad)

    def test_vet_can_bat_duoc_cong_thuc_dem_sai(self, bank: ItemBank, monkeypatch) -> None:
        """Nếu công thức đếm viết sai (ở đây: tổ hợp mà dùng chỉnh hợp), liệt kê vét cạn phải lệch."""
        item = bank.get("MAD101-COUNT-002")
        monkeypatch.setattr(D, "count_formula", lambda kind, m: D.count_brute_force("permutation", m))
        assert D.cross_check(item)["agree"] is False

    def test_tinh_lap_bat_duoc_cong_thuc_truy_hoi_sai(self, bank: ItemBank) -> None:
        item = bank.get("MAD101-REC-002").model_copy(update={"answer": "3*2**n - 3**n"})
        assert D.cross_check(item)["agree"] is False


class TestLogicParser:
    @pytest.mark.parametrize("text, expected", [
        ("p -> q | r", "Implies(p, q | r)"),          # → có độ ưu tiên THẤP nhất
        ("p -> q -> r", "Implies(p, Implies(q, r))"),  # → kết hợp phải
        ("~(p -> q)", "~Implies(p, q)"),
    ])
    def test_do_uu_tien_dung_quy_uoc_logic(self, text: str, expected: str) -> None:
        import sympy as sp

        assert D.parse_logic(text) == sp.sympify(expected, locals={"p": sp.Symbol("p"), "q": sp.Symbol("q"),
                                                                    "r": sp.Symbol("r")})

    @pytest.mark.parametrize("bad", ["p &", "(p", "p q", "& q", "p $ q"])
    def test_cong_thuc_hong_thi_bao_loi(self, bad: str) -> None:
        with pytest.raises(ParseError):
            D.parse_logic(bad)


class TestLogic:
    @pytest.mark.parametrize("answer", ["¬p ∨ ¬q", "~q | ~p", "not p or not q", "(~p) | (~q)"])
    def test_moi_cach_viet_tuong_duong(self, verifier, bank, answer: str) -> None:
        assert check(verifier, bank, "MAD101-LOGIC-001", answer).is_correct, answer

    def test_nop_lai_nguyen_de_khong_duoc_tinh(self, verifier, bank) -> None:
        """¬(p ∧ q) tương đương chính nó — nhưng đề yêu cầu đưa ¬ vào trong."""
        result = check(verifier, bank, "MAD101-LOGIC-001", "¬(p ∧ q)")
        assert result.final_answer_correct is False

    def test_sai_de_morgan(self, verifier, bank) -> None:
        assert D.ERR_DEMORGAN in check(verifier, bank, "MAD101-LOGIC-001", "¬p ∧ ¬q").candidate_error_codes

    def test_phu_dinh_cua_keo_theo(self, verifier, bank) -> None:
        assert check(verifier, bank, "MAD101-LOGIC-003", "p ∧ ¬q").is_correct
        assert D.ERR_INVERSE in check(verifier, bank, "MAD101-LOGIC-003", "¬p → ¬q").candidate_error_codes

    def test_phan_biet_dao_va_nghich_du_chung_tuong_duong_logic(self, verifier, bank) -> None:
        """q → p và ¬p → ¬q tương đương logic, nên chỉ phân biệt được qua CÁCH VIẾT."""
        assert D.ERR_CONVERSE in check(verifier, bank, "MAD101-LOGIC-006", "q → p").candidate_error_codes
        assert D.ERR_INVERSE in check(verifier, bank, "MAD101-LOGIC-006", "¬p → ¬q").candidate_error_codes
        assert check(verifier, bank, "MAD101-LOGIC-006", "¬q → ¬p").is_correct
        assert check(verifier, bank, "MAD101-LOGIC-006", "q ∨ ¬p").is_correct  # tương đương, viết khác

    def test_hang_dung(self, verifier, bank) -> None:
        assert check(verifier, bank, "MAD101-LOGIC-008", "có").is_correct
        assert check(verifier, bank, "MAD101-LOGIC-009", "không").is_correct


class TestNumbers:
    @pytest.mark.parametrize("item_id, answer", [
        ("MAD101-INT-005", "5"), ("MAD101-INT-005", "12"), ("MAD101-INT-005", "-2"),  # mọi giá trị đồng dư
        ("MAD101-INT-003", "4"), ("MAD101-INT-003", "11"),
        ("MAD101-INT-007", "1101"), ("MAD101-INT-007", "0b1101"), ("MAD101-INT-007", "1101₂"),
        ("MAD101-SUM-001", "n(n+1)/2"), ("MAD101-SUM-001", "(n^2 + n)/2"),
        ("MAD101-SUM-003", "2^(n+1) - 1"),
        ("MAD101-REC-001", "a_n = 2^n - 1"),
        ("MAD101-REC-004", "2^n + n*2^n"),
    ])
    def test_dang_viet_khac_van_dung(self, verifier, bank, item_id: str, answer: str) -> None:
        result = check(verifier, bank, item_id, answer)
        assert result.is_correct, f"{item_id} «{answer}»: {result.notes}"

    def test_viet_nguoc_chu_so_nhi_phan(self, verifier, bank) -> None:
        assert D.ERR_BASE_REVERSED in check(verifier, bank, "MAD101-INT-007", "1011").candidate_error_codes

    def test_sai_hang_so_truy_hoi(self, verifier, bank) -> None:
        """2ⁿ⁺¹ − 1 thoả aₙ = 2aₙ₋₁ + 1 nhưng a₀ = 1 ≠ 0."""
        assert D.ERR_REC_INITIAL in check(verifier, bank, "MAD101-REC-001", "2^(n+1) - 1").candidate_error_codes

    def test_lech_mot_so_hang_o_tong(self, verifier, bank) -> None:
        assert D.ERR_SUM_OFFBYONE in check(verifier, bank, "MAD101-SUM-001", "n(n-1)/2").candidate_error_codes

    @pytest.mark.parametrize("item_id, answer, code", [
        ("MAD101-COUNT-002", "30", D.ERR_ORDER),
        ("MAD101-COUNT-006", "53", D.ERR_NOSUB),
        ("MAD101-GRAPH-001", "12", D.ERR_HANDSHAKE),
        ("MAD101-GRAPH-006", "6", D.ERR_CHROMATIC_BOUND),
        ("MAD101-GRAPH-008", "6", D.ERR_UNWEIGHTED),
        ("MAD101-TREE-003", "6", D.ERR_MST_CYCLE),
        ("MAD101-GRAPH-003", "có", D.ERR_EULER),
    ])
    def test_chan_doan(self, verifier, bank, item_id: str, answer: str, code: str) -> None:
        assert code in check(verifier, bank, item_id, answer).candidate_error_codes

    @pytest.mark.parametrize("item_id, answer", [("MAD101-COUNT-001", "42"), ("MAD101-TREE-003", "9")])
    def test_sai_tuy_y_khong_bia_chan_doan(self, verifier, bank, item_id: str, answer: str) -> None:
        result = check(verifier, bank, item_id, answer)
        assert result.final_answer_correct is False and result.candidate_error_codes == []


class TestGuardrailOnLogic:
    def test_chan_goi_y_noi_thang_cong_thuc(self, bank) -> None:
        item = bank.get("MAD101-LOGIC-001")
        assert check_leak("Đáp án là ¬p ∨ ¬q nhé", item, HintLevel.PITFALL).leaked
        assert check_leak("Kết quả: ~q | ~p", item, HintLevel.PITFALL).leaked

    def test_khong_chan_goi_y_hop_le(self, bank) -> None:
        item = bank.get("MAD101-LOGIC-001")
        assert not check_leak("Em thử dùng luật De Morgan xem", item, HintLevel.PITFALL).leaked
        assert not check_leak("Em xét ¬(p ∧ q) trước", item, HintLevel.PITFALL).leaked
