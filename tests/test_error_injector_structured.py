"""Test bộ sinh lỗi cho đáp án có cấu trúc: đại số tuyến tính (MAE101) và Math for ML (MAI391).

Nhắc lại cảnh báo trong ``linear_algebra_errors`` và ``mml_errors``: tỉ lệ gán
đúng mã trên dữ liệu tổng hợp mang tính vòng quanh (bộ sinh và bộ chẩn đoán viết
từ cùng một bảng mã lỗi). Test ở đây kiểm tra tính NHẤT QUÁN, không phải năng lực thật.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.itembank import ItemBank, load_course_error_codes  # noqa: E402
from src.core.schema import Submission  # noqa: E402
from src.data_gen.error_injector import InjectedError, build_dataset  # noqa: E402
from src.verify.calculus import ERR_ALG_STEP, ERR_DEF_SWAPBOUNDS  # noqa: E402
from src.verify.registry import verifier_for  # noqa: E402

SUBJECTS = ["MAE101", "MAI391", "MAS291", "MAD101"]
#: Mảng kiến thức có đáp án cấu trúc mà file này kiểm tra, theo tiền tố mã lỗi.
STRUCTURED = ("LA.", "MAI.", "MAS.", "MAD.")


@pytest.fixture(scope="module", params=SUBJECTS)
def subject(request) -> str:
    return request.param


@pytest.fixture(scope="module")
def bank(subject: str) -> ItemBank:
    return ItemBank.load(subject)


@pytest.fixture(scope="module")
def dataset(bank: ItemBank, subject: str) -> list[InjectedError]:
    records = build_dataset(bank, load_course_error_codes(subject))
    return [r for r in records if r.error_code.startswith(STRUCTURED)]


def verify(subject: str, bank: ItemBank, record: InjectedError):
    item = bank.get(record.item_id)
    return verifier_for(subject).verify(item, Submission(
        item_id=item.item_id, final_answer=record.wrong_final_answer, steps=record.wrong_steps,
    ))


class TestShape:
    def test_chi_dung_ma_loi_cua_mon(self, dataset: list[InjectedError], subject: str) -> None:
        """Mã lỗi phải nằm trong bảng mã lỗi của môn — MAE101 không được có mã MAI.*."""
        allowed = set(load_course_error_codes(subject))
        assert dataset and {r.error_code for r in dataset} <= allowed

    def test_ma_dai_so_tuyen_tinh_dung_chung(self) -> None:
        """LA.* phải xuất hiện ở CẢ HAI môn — đó là lý do đặt mã lỗi theo kiểu sai, không theo môn."""
        for subject in ("MAE101", "MAI391"):
            records = build_dataset(ItemBank.load(subject), load_course_error_codes(subject))
            assert any(r.error_code.startswith("LA.") for r in records), subject

    def test_phu_gan_het_ma_math_for_ml(self) -> None:
        records = build_dataset(ItemBank.load("MAI391"), load_course_error_codes("MAI391"))
        produced = {r.error_code for r in records if r.error_code.startswith("MAI.")}
        expected = {c for c in load_course_error_codes("MAI391") if c.startswith("MAI.")}
        assert produced == expected, f"thiếu {sorted(expected - produced)}"

    def test_dap_an_dung_hien_thi_duoc(self, dataset: list[InjectedError]) -> None:
        """correct_answer là chuỗi nộp được, không phải repr của list Python."""
        assert all("'" not in r.correct_answer for r in dataset)

    def test_khong_co_mau_mang_hai_nhan(self, dataset: list[InjectedError]) -> None:
        """Cùng một bài, cùng một đáp án sai mà hai mã lỗi khác nhau là dữ liệu huấn luyện mâu thuẫn."""
        seen: dict[tuple, str] = {}
        for record in dataset:
            key = (record.item_id, record.wrong_final_answer, tuple(record.wrong_steps))
            assert seen.setdefault(key, record.error_code) == record.error_code, key


class TestLabels:
    def test_moi_mau_deu_thuc_su_sai(self, bank: ItemBank, dataset, subject: str) -> None:
        for record in dataset:
            if record.wrong_step_index is None:
                assert verify(subject, bank, record).final_answer_correct is False, record.error_code

    def test_bat_dung_buoc_sai(self, bank: ItemBank, dataset, subject: str) -> None:
        for record in (r for r in dataset if r.wrong_step_index is not None):
            result = verify(subject, bank, record)
            assert result.first_wrong_step == record.wrong_step_index
            assert result.final_answer_correct is True, "Lỗi nằm ở bước, đáp án cuối vẫn đúng"

    def test_gan_dung_ma_da_cai(self, bank: ItemBank, dataset, subject: str) -> None:
        wrong = []
        for record in dataset:
            codes = verify(subject, bank, record).candidate_error_codes
            if record.error_code not in codes:
                wrong.append(f"{record.item_id}/{record.error_code}: nhận {codes}")
        assert wrong == [], "\n".join(wrong)


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
