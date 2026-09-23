"""Kiểm tra tính toàn vẹn của ngân hàng đề.

Test ``test_moi_dap_an_chuan_deu_tu_verify_duoc`` là test quan trọng nhất của cả
dự án. Nó bắt hai loại lỗi mà không cách nào khác phát hiện được:

- Đáp án trong ngân hàng đề bị gõ sai (sai một dấu, thiếu một hệ số).
- Verifier có lỗ hổng khiến nó từ chối cả lời giải đúng.

Nếu test này đỏ, mọi số liệu thực nghiệm sinh ra sau đó đều vô nghĩa.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.itembank import ItemBank  # noqa: E402
from src.core.schema import Submission  # noqa: E402
from src.verify.registry import verifier_for  # noqa: E402


@pytest.fixture(scope="module")
def bank() -> ItemBank:
    return ItemBank.load("MAE101")


class TestIntegrity:
    def test_nap_duoc_ngan_hang_de(self, bank: ItemBank) -> None:
        assert len(bank.items) >= 20, "Gate 0 cần tối thiểu 20 bài"
        assert len(bank.skills) >= 10

    def test_khong_tham_chieu_ky_nang_khong_ton_tai(self, bank: ItemBank) -> None:
        assert bank.unknown_skill_references() == []

    def test_cay_tien_quyet_khong_co_chu_trinh(self, bank: ItemBank) -> None:
        assert bank.prerequisite_cycles() == []

    def test_tien_quyet_khong_tro_vao_khoang_khong(self, bank: ItemBank) -> None:
        assert bank.orphan_prerequisites() == []

    def test_ma_bai_tap_khong_trung(self, bank: ItemBank) -> None:
        ids = [item.item_id for item in bank.items.values()]
        assert len(ids) == len(set(ids))

    def test_moi_bai_deu_gan_it_nhat_mot_ky_nang(self, bank: ItemBank) -> None:
        """Bài không gắn kỹ năng thì mô hình năng lực không học được gì từ nó."""
        missing = [item.item_id for item in bank.items.values() if not item.skills]
        assert missing == [], f"Các bài chưa gắn kỹ năng: {missing}"


class TestReferenceAnswersSelfVerify:
    def test_moi_dap_an_chuan_deu_tu_verify_duoc(self, bank: ItemBank) -> None:
        """Nộp chính đáp án chuẩn vào verifier thì phải được chấm là ĐÚNG."""
        verifier = verifier_for("MAE101")
        failures: list[str] = []

        for item in bank.items.values():
            if item.answer is None:
                failures.append(f"{item.item_id}: thiếu đáp án chuẩn")
                continue

            result = verifier.verify(
                item, Submission(item_id=item.item_id, final_answer=item.answer_text)
            )
            if result.final_answer_correct is not True:
                failures.append(f"{item.item_id}: {result.notes}")

        assert failures == [], "Đáp án chuẩn bị verifier từ chối:\n" + "\n".join(failures)

    def test_loi_giai_mau_khong_co_buoc_nao_bi_bao_sai(self, bank: ItemBank) -> None:
        """Các bước trong lời giải mẫu không được bị đánh dấu là sai."""
        verifier = verifier_for("MAE101")
        failures: list[str] = []

        for item in bank.items.values():
            if not item.reference_solution_steps:
                continue
            steps = [step.expr for step in item.reference_solution_steps]
            checks = verifier.check_steps(item, steps)
            for check in checks:
                if check.ok is False:
                    failures.append(f"{item.item_id} bước {check.step}: {check.reason}")

        assert failures == [], "Lời giải mẫu bị chấm sai:\n" + "\n".join(failures)


class TestLookup:
    def test_tra_cuu_theo_ky_nang(self, bank: ItemBank) -> None:
        items = bank.by_skill("MAE.INT.SUBST")
        assert items, "Phải có bài tập cho kỹ năng đổi biến"
        assert all("MAE.INT.SUBST" in item.skills for item in items)

    def test_loc_theo_do_kho(self, bank: ItemBank) -> None:
        easy = bank.by_difficulty(0.0, 0.3)
        hard = bank.by_difficulty(0.6, 1.0)
        assert easy and hard
        assert set(i.item_id for i in easy).isdisjoint(i.item_id for i in hard)

    def test_bao_loi_ro_rang_khi_tra_ma_khong_ton_tai(self, bank: ItemBank) -> None:
        with pytest.raises(KeyError):
            bank.get("KHONG-TON-TAI")
