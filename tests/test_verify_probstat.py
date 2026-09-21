"""Test bộ chấm Xác suất – Thống kê (MAS291).

Test quan trọng nhất là ``test_moi_bai_xac_suat_khop_monte_carlo``: đáp án chuẩn
của mọi bài ra một xác suất được xác nhận bằng một phương pháp ĐỘC LẬP — mô
phỏng ngẫu nhiên — chứ không chỉ bằng chính công thức đã dùng để soạn đề.
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
from src.verify import probstat as P  # noqa: E402
from src.verify.registry import verifier_for  # noqa: E402


@pytest.fixture(scope="module")
def bank() -> ItemBank:
    return ItemBank.load("MAS291")


@pytest.fixture(scope="module")
def verifier():
    return verifier_for("MAS291")


def check(verifier, bank, item_id: str, answer: str):
    return verifier.verify(bank.get(item_id), Submission(item_id=item_id, final_answer=answer))


class TestMonteCarlo:
    def test_moi_bai_xac_suat_khop_monte_carlo(self, bank: ItemBank) -> None:
        probability_items = [i for i in bank.items.values() if i.meta["task"] in P.MONTE_CARLO_TASKS]
        assert len(probability_items) >= 15
        disagree = [f"{i.item_id}: {P.cross_check(i)}" for i in probability_items if not P.cross_check(i)["agree"]]
        assert disagree == [], "\n".join(disagree)

    @pytest.mark.parametrize("item_id, bug", [
        ("MAS291-HYP-003", lambda true: true / 2),       # quên nhân 2 cho kiểm định hai phía
        ("MAS291-PROB-008", lambda true: 0.95),          # công thức Bayes đảo điều kiện
        ("MAS291-NORM-003", lambda true: 1 - true),      # gọi nhầm cdf thay vì sf
    ])
    def test_monte_carlo_bat_duoc_cong_thuc_sai(self, bank: ItemBank, monkeypatch, item_id, bug) -> None:
        """Điều Monte Carlo thật sự bảo vệ: lỗi trong chính CÔNG THỨC tính đáp án chuẩn.

        Mô phỏng dùng cùng dữ liệu đề với công thức, nên không bắt được đề gõ nhầm
        số liệu — cái đó do test tự verify lo. Nhưng nếu hàm ``analytic`` viết sai
        (gọi nhầm hàm scipy, quên nhân 2...) thì mô phỏng, vốn không dùng công
        thức nào, sẽ lệch hẳn.
        """
        item = bank.get(item_id)
        true_value = P.analytic(item)
        monkeypatch.setattr(P, "analytic", lambda it: bug(true_value))
        assert P.cross_check(item)["agree"] is False

    def test_ket_qua_cham_co_kem_kiem_cheo(self, verifier, bank) -> None:
        result = check(verifier, bank, "MAS291-NORM-002", "0.7745")
        assert result.cross_check is not None and result.cross_check["agree"]

    def test_bai_khong_phai_xac_suat_thi_khong_mo_phong(self, bank: ItemBank) -> None:
        assert P.cross_check(bank.get("MAS291-DESC-002")) is None


class TestTableRounding:
    @pytest.mark.parametrize("item_id, answer", [
        ("MAS291-NORM-002", "0.7745"),
        ("MAS291-NORM-002", "0.775"),         # tra bảng, làm tròn z về 2 chữ số
        ("MAS291-NORM-001", "0.9772"),
        ("MAS291-HYP-003", "0.0456"),
        ("MAS291-PROB-008", "0.161"),
        ("MAS291-CI-002", "[17.869, 22.131]"),
        ("MAS291-CI-002", "(22.13, 17.87)"),  # hai đầu mút đảo thứ tự, làm tròn 2 chữ số
        ("MAS291-REG-003", "0.775"),
    ])
    def test_sai_so_tra_bang_duoc_chap_nhan(self, verifier, bank, item_id: str, answer: str) -> None:
        result = check(verifier, bank, item_id, answer)
        assert result.is_correct, f"{item_id} «{answer}»: {result.notes}"


class TestDiagnosis:
    def test_mot_phia_hai_phia(self, verifier, bank) -> None:
        """p-value một phía (0.0228) cho bài hai phía — lệch đúng hệ số 2."""
        assert P.ERR_HYP_TAIL in check(verifier, bank, "MAS291-HYP-003", "0.0228").candidate_error_codes

    def test_dung_z_khi_phai_dung_t(self, verifier, bank) -> None:
        result = check(verifier, bank, "MAS291-CI-002", "[18.04, 21.96]")
        assert P.ERR_Z_INSTEAD_T in result.candidate_error_codes

    def test_nham_dieu_kien_trong_bayes(self, verifier, bank) -> None:
        """0.95 = P(dương tính | bệnh), đề hỏi P(bệnh | dương tính)."""
        assert P.ERR_COND_REVERSED in check(verifier, bank, "MAS291-PROB-008", "0.95").candidate_error_codes

    def test_quen_he_so_to_hop(self, verifier, bank) -> None:
        assert P.ERR_NOCOMB in check(verifier, bank, "MAS291-BIN-001", "0.00222").candidate_error_codes

    def test_nham_ty_le_va_trung_binh_o_phan_phoi_mu(self, verifier, bank) -> None:
        assert P.ERR_RATE_MEAN in check(verifier, bank, "MAS291-EXP-001", "0.00248").candidate_error_codes

    @pytest.mark.parametrize("item_id, answer", [
        ("MAS291-NORM-001", "0.5"),
        ("MAS291-BIN-003", "0.9"),
        ("MAS291-REG-001", "2"),
    ])
    def test_sai_tuy_y_khong_bia_chan_doan(self, verifier, bank, item_id: str, answer: str) -> None:
        result = check(verifier, bank, item_id, answer)
        assert result.final_answer_correct is False and result.candidate_error_codes == []


class TestDecision:
    @pytest.mark.parametrize("answer, expected", [
        ("bác bỏ H0", True), ("Bác bỏ H₀", True), ("reject H0", True),
        ("không bác bỏ H0", False), ("Chưa đủ cơ sở bác bỏ H0", False), ("fail to reject", False),
    ])
    def test_doc_duoc_nhieu_cach_viet(self, answer: str, expected: bool) -> None:
        assert P.parse_decision(answer) is expected

    def test_ket_luan_dung_va_sai(self, verifier, bank) -> None:
        assert check(verifier, bank, "MAS291-HYP-005", "bác bỏ H0").is_correct
        result = check(verifier, bank, "MAS291-HYP-006", "bác bỏ H0")
        assert result.final_answer_correct is False and P.ERR_DECISION in result.candidate_error_codes

    def test_khong_hieu_thi_hoi_lai(self, verifier, bank) -> None:
        assert check(verifier, bank, "MAS291-HYP-005", "có lẽ vậy").final_answer_correct is None

    def test_guardrail_chan_goi_y_noi_thang_ket_luan(self, bank) -> None:
        assert check_leak("Vậy ta nên bác bỏ H0 nhé", bank.get("MAS291-HYP-005"), HintLevel.PITFALL).leaked
        assert not check_leak("Em so p-value với α xem", bank.get("MAS291-HYP-005"), HintLevel.PITFALL).leaked
