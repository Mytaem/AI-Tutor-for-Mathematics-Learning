"""Test bộ sinh lỗi MAI391, và hồi quy cho hai mã lỗi MAE101 trước đây bị bỏ sót.

Nhắc lại cảnh báo trong ``mai391_errors``: tỉ lệ gán đúng mã trên dữ liệu tổng
hợp của MAI391 mang tính vòng quanh (bộ sinh và bộ chẩn đoán viết từ cùng một
taxonomy). Test ở đây kiểm tra tính NHẤT QUÁN, không phải năng lực thật.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.itembank import ERRORS_DIR, ItemBank, load_error_codes  # noqa: E402
from src.core.schema import Submission  # noqa: E402
from src.data_gen.error_injector import InjectedError, build_dataset  # noqa: E402
from src.verify.calculus import ERR_ALG_STEP, ERR_DEF_SWAPBOUNDS  # noqa: E402
from src.verify.registry import verifier_for  # noqa: E402


@pytest.fixture(scope="module")
def bank() -> ItemBank:
    return ItemBank.load("MAI391")


@pytest.fixture(scope="module")
def dataset(bank: ItemBank) -> list[InjectedError]:
    return build_dataset(bank, ERRORS_DIR / "mai391.json")


def verify(bank: ItemBank, record: InjectedError):
    item = bank.get(record.item_id)
    return verifier_for("MAI391").verify(item, Submission(
        item_id=item.item_id, final_answer=record.wrong_final_answer, steps=record.wrong_steps,
    ))


class TestShape:
    def test_chi_sinh_ma_loi_cua_mai391(self, dataset: list[InjectedError]) -> None:
        """Mã lỗi MAE không được áp nhầm vào bài MAI391."""
        assert dataset and all(r.error_code.startswith("MAI.") for r in dataset)

    def test_phu_gan_het_taxonomy(self, dataset: list[InjectedError]) -> None:
        taxonomy = set(load_error_codes(ERRORS_DIR / "mai391.json"))
        produced = {r.error_code for r in dataset}
        assert produced <= taxonomy
        assert len(produced) >= 20, f"Mới phủ {len(produced)}/{len(taxonomy)}: thiếu {sorted(taxonomy - produced)}"

    def test_dap_an_dung_hien_thi_duoc(self, dataset: list[InjectedError]) -> None:
        """correct_answer là chuỗi nộp được, không phải repr của list Python."""
        assert all("'" not in r.correct_answer for r in dataset)


class TestLabels:
    def test_moi_mau_deu_thuc_su_sai(self, bank: ItemBank, dataset: list[InjectedError]) -> None:
        for record in dataset:
            result = verify(bank, record)
            if record.wrong_step_index is None:
                assert result.final_answer_correct is False, f"{record.item_id}/{record.error_code}"

    def test_bat_dung_buoc_sai(self, bank: ItemBank, dataset: list[InjectedError]) -> None:
        steps = [r for r in dataset if r.wrong_step_index is not None]
        assert steps
        for record in steps:
            result = verify(bank, record)
            assert result.first_wrong_step == record.wrong_step_index
            assert result.final_answer_correct is True, "Lỗi nằm ở bước, đáp án cuối vẫn đúng"

    def test_gan_dung_ma_da_cai(self, bank: ItemBank, dataset: list[InjectedError]) -> None:
        wrong = [
            f"{r.item_id}/{r.error_code}: nhận {verify(bank, r).candidate_error_codes}"
            for r in dataset if r.error_code not in verify(bank, r).candidate_error_codes
        ]
        assert wrong == [], "\n".join(wrong)

    def test_nghiem_kep_tai_hien_dung_loi_kinh_dien(self, dataset: list[InjectedError]) -> None:
        """Bộ sinh phải tái hiện C1·eˣ + C2·eˣ cho bài nghiệm kép, không chỉ xoá một hằng số."""
        record = next(r for r in dataset if r.item_id == "MAI391-ODE-004" and r.error_code == "MAI.ODE.INCOMPLETE")
        assert "C2" in record.wrong_final_answer and "x*" not in record.wrong_final_answer.replace("exp(x)", "")


class TestMAE101CodesNoLongerSilent:
    """Hồi quy: verifier MAE101 từng phát hiện được hai loại lỗi này nhưng không gắn mã."""

    def test_buoc_sai_duoc_gan_ma(self) -> None:
        bank = ItemBank.load("MAE101")
        item = bank.get("MAE101-INT-001")
        result = verifier_for("MAE101").verify(item, Submission(
            item_id=item.item_id, steps=["Integral(x**2, x)", "2*x**3/3"], final_answer="x**3/3 + C",
        ))
        assert ERR_ALG_STEP in result.candidate_error_codes

    def test_the_can_nguoc_duoc_gan_ma(self) -> None:
        bank = ItemBank.load("MAE101")
        item = bank.get("MAE101-DEF-002")  # ∫_0^π sin x dx = 2
        result = verifier_for("MAE101").verify(item, Submission(item_id=item.item_id, final_answer="-2"))
        assert result.final_answer_correct is False
        assert ERR_DEF_SWAPBOUNDS in result.candidate_error_codes

    def test_sai_tuy_y_khong_bi_gan_the_can_nguoc(self) -> None:
        bank = ItemBank.load("MAE101")
        item = bank.get("MAE101-DEF-002")
        result = verifier_for("MAE101").verify(item, Submission(item_id=item.item_id, final_answer="3"))
        assert ERR_DEF_SWAPBOUNDS not in result.candidate_error_codes
