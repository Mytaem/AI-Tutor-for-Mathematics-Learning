"""Test bộ chấm Mathematics for Machine Learning (MAI391).

Bộ test sinh lỗi đã kiểm từng mã lỗi; ở đây kiểm chiều NGƯỢC LẠI: mọi dạng viết
ĐÚNG phải được nhận — thứ tự khác, bội vô hướng khác, dạng số khác — và chẩn
đoán không được bịa ra khi đáp án sai tuỳ ý.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.itembank import ItemBank  # noqa: E402
from src.core.schema import Submission  # noqa: E402
from src.verify import mml as M  # noqa: E402
from src.verify.registry import verifier_for  # noqa: E402


@pytest.fixture(scope="module")
def bank() -> ItemBank:
    return ItemBank.load("MAI391")


@pytest.fixture(scope="module")
def verifier():
    return verifier_for("MAI391")


def check(verifier, bank, item_id: str, answer: str):
    return verifier.verify(bank.get(item_id), Submission(item_id=item_id, final_answer=answer))


class TestAcceptsEveryCorrectForm:
    @pytest.mark.parametrize("item_id, answer", [
        ("MAI391-NORM-001", "5.0"),
        ("MAI391-ANGLE-001", "1/sqrt(2)"),                  # cùng giá trị với sqrt(2)/2
        ("MAI391-ANGLE-001", "0.70710678"),
        ("MAI391-PROJ-002", "[2.5, 2.5, 0]"),
        ("MAI391-DIAG-001", "[[6, 0], [0, 1]]"),            # thứ tự trị riêng tuỳ ý
        ("MAI391-SVD-002", "0, sqrt(2)"),
        ("MAI391-GRAD-001", "[2*y*x, 3 + x^2]"),
        ("MAI391-PART-001", "3x^2 y^2"),
        ("MAI391-CHAIN-001", "2*t*(1 + 2*t**2)"),           # dạng nhân tử
        ("MAI391-GD-001", "(0.8, 0.6)"),
        ("MAI391-PROB-002", "0.49"),
        ("MAI391-LS-001", "[0.8333333, 1.5]"),
        ("MAI391-PCA-001", "[-2, -2]"),                     # bội âm vẫn là cùng hướng
        ("MAI391-SVM-002", "2/sqrt(2)"),
    ])
    def test_dang_viet_khac_van_dung(self, verifier, bank, item_id: str, answer: str) -> None:
        result = check(verifier, bank, item_id, answer)
        assert result.is_correct, f"{item_id} «{answer}»: {result.notes}"


class TestPropertyBased:
    def test_binh_phuong_toi_thieu_kiem_bang_phuong_trinh_chuan(self, verifier, bank) -> None:
        """Không so với θ chuẩn mà kiểm Xᵀ(Xθ − y) = 0."""
        assert "phương trình chuẩn" in check(verifier, bank, "MAI391-LS-002", "[2/3, 1/2]").notes[0]

    def test_diem_dung_kiem_bang_gradient(self, verifier, bank) -> None:
        assert "∇f" in check(verifier, bank, "MAI391-CRIT-002", "[10/7, -5/7]").notes[0]

    def test_vector_0_khong_phai_thanh_phan_chinh(self, verifier, bank) -> None:
        result = check(verifier, bank, "MAI391-PCA-001", "[0, 0]")
        assert result.final_answer_correct is False
        assert "LA.EIG.ZEROVEC" in result.candidate_error_codes


class TestNoFabricatedDiagnosis:
    """Sai tuỳ ý thì chấm sai nhưng KHÔNG gán mã lỗi — không bịa chẩn đoán."""

    @pytest.mark.parametrize("item_id, answer", [
        ("MAI391-NORM-001", "6"),   # (7 thì KHÔNG tuỳ ý: đó đúng là chuẩn L1 của (3, 4))
        ("MAI391-TRACE-002", "11"),
        ("MAI391-SVM-001", "3"),
        ("MAI391-PROB-002", "0.2"),
        ("MAI391-GD-001", "[0.5, 0.5]"),
    ])
    def test_sai_tuy_y(self, verifier, bank, item_id: str, answer: str) -> None:
        result = check(verifier, bank, item_id, answer)
        assert result.final_answer_correct is False
        assert result.candidate_error_codes == [], result.candidate_error_codes


class TestRouting:
    def test_bai_math_for_ml_do_bo_cham_mml_cham(self, verifier, bank) -> None:
        assert verifier.part_for(bank.get("MAI391-GRAD-001")).name == "mml"

    def test_dinh_thuc_va_vector_rieng_dung_bo_cham_dai_so_tuyen_tinh(self, verifier, bank) -> None:
        """Chương 4 của MAI391 dùng lại bộ chấm đại số tuyến tính của MAE101."""
        assert verifier.part_for(bank.get("MAI391-DET-001")).name == "linear_algebra"
        assert verifier.part_for(bank.get("MAI391-VEC-001")).name == "linear_algebra"

    def test_bai_pca_la_vector_rieng_nhung_do_mml_cham(self, verifier, bank) -> None:
        """PCA có đáp án dạng vector riêng nhưng mã lỗi riêng — phải đi qua bộ chấm MML."""
        assert verifier.part_for(bank.get("MAI391-PCA-001")).name == "mml"

    def test_moi_task_deu_co_bo_cham(self, bank) -> None:
        tasks = {item.meta.get("task") for item in bank.items.values()} - {None}
        from src.verify.linalg import LA_TASKS

        assert tasks <= M.MML_TASKS | LA_TASKS, tasks - (M.MML_TASKS | LA_TASKS)
