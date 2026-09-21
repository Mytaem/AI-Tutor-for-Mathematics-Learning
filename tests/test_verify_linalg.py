"""Test verifier MAI391 — đại số tuyến tính và phương trình vi phân.

Hai nhóm test quyết định:
- Mọi DẠNG đúng phải được chấp nhận (tham số hoá khác, bội vô hướng khác, tên
  hằng số khác) — vì verifier kiểm tính chất, không so khớp dạng chuẩn.
- Mọi lỗi kinh điển phải được gọi đúng tên.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.itembank import ItemBank  # noqa: E402
from src.core.schema import Submission  # noqa: E402
from src.verify import linalg_ode as L  # noqa: E402
from src.verify.registry import verifier_for  # noqa: E402


@pytest.fixture(scope="module")
def bank() -> ItemBank:
    return ItemBank.load("MAI391")


@pytest.fixture(scope="module")
def verifier() -> L.LinalgODEVerifier:
    return verifier_for("MAI391")


def check(verifier, bank, item_id: str, answer: str, steps: list[str] | None = None):
    item = bank.get(item_id)
    return verifier.verify(item, Submission(item_id=item_id, final_answer=answer, steps=steps or []))


# ==========================================================================
# Hệ phương trình
# ==========================================================================

class TestLinearSystem:
    def test_nghiem_duy_nhat(self, verifier, bank) -> None:
        assert check(verifier, bank, "MAI391-SYS-002", "[5, 3, -2]").is_correct

    def test_chap_nhan_dang_bo_so_trong_ngoac_tron(self, verifier, bank) -> None:
        assert check(verifier, bank, "MAI391-SYS-001", "(2, 1)").is_correct

    def test_chap_nhan_moi_cach_tham_so_hoa(self, verifier, bank) -> None:
        """[1-s-t, s, t] và [u, v, 1-u-v] là CÙNG một họ nghiệm — phải chấm đúng cả hai."""
        for answer in ["[1 - s - t, s, t]", "[u, v, 1 - u - v]", "[a, 1 - a - b, b]"]:
            result = check(verifier, bank, "MAI391-SYS-003", answer)
            assert result.is_correct, f"{answer}: {result.notes}"

    def test_dem_bac_tu_do_that_khong_dem_ky_hieu(self, verifier, bank) -> None:
        """[2-2(s+t), s+t, 1] có hai ký hiệu nhưng chỉ một bậc tự do — vẫn là đủ họ nghiệm."""
        assert check(verifier, bank, "MAI391-SYS-004", "[2 - 2*(s + t), s + t, 1]").is_correct

    def test_mot_nghiem_rieng_cua_he_vo_so_nghiem(self, verifier, bank) -> None:
        result = check(verifier, bank, "MAI391-SYS-004", "[2, 0, 1]")
        assert result.final_answer_correct is False
        assert L.ERR_SYS_PARTIAL in result.candidate_error_codes

    def test_thieu_bac_tu_do(self, verifier, bank) -> None:
        """Hệ cần 2 tham số, bài làm chỉ có 1 — vẫn là một phần họ nghiệm."""
        result = check(verifier, bank, "MAI391-SYS-003", "[1 - t, t, 0]")
        assert L.ERR_SYS_PARTIAL in result.candidate_error_codes

    def test_nghiem_khong_thoa_he(self, verifier, bank) -> None:
        result = check(verifier, bank, "MAI391-SYS-002", "[5, 3, 2]")
        assert result.final_answer_correct is False
        assert L.ERR_SYS_NOTSOLUTION in result.candidate_error_codes

    def test_he_vo_nghiem(self, verifier, bank) -> None:
        assert check(verifier, bank, "MAI391-SYS-005", "vô nghiệm").is_correct
        assert check(verifier, bank, "MAI391-SYS-005", "Hệ vô nghiệm.").is_correct

    def test_dua_nghiem_cho_he_vo_nghiem(self, verifier, bank) -> None:
        result = check(verifier, bank, "MAI391-SYS-005", "[1, 0]")
        assert L.ERR_SYS_INCONSISTENT in result.candidate_error_codes

    def test_ket_luan_vo_nghiem_sai(self, verifier, bank) -> None:
        result = check(verifier, bank, "MAI391-SYS-001", "vô nghiệm")
        assert L.ERR_SYS_FALSE_NOSOL in result.candidate_error_codes

    def test_sai_so_an(self, verifier, bank) -> None:
        result = check(verifier, bank, "MAI391-SYS-001", "[2, 1, 0]")
        assert L.ERR_SHAPE in result.candidate_error_codes


# ==========================================================================
# Khử Gauss — kiểm tra từng bước bằng tương đương hàng
# ==========================================================================

class TestRowOperations:
    GOOD = [
        "[[1, 1, 1, 6], [0, 2, 5, -4], [2, 5, -1, 27]]",
        "[[1, 1, 1, 6], [0, 2, 5, -4], [0, 3, -3, 15]]",
        "[[1, 1, 1, 6], [0, 2, 5, -4], [0, 0, -21/2, 21]]",
    ]

    def test_chuoi_bien_doi_dung(self, verifier, bank) -> None:
        result = check(verifier, bank, "MAI391-SYS-002", "[5, 3, -2]", self.GOOD)
        assert result.first_wrong_step is None
        assert result.is_correct

    def test_bat_dung_buoc_tinh_sai(self, verifier, bank) -> None:
        """R3 − 2·R1 mà tính nhầm một phần tử: 15 thành 17."""
        steps = [self.GOOD[0], "[[1, 1, 1, 6], [0, 2, 5, -4], [0, 3, -3, 17]]", self.GOOD[2]]
        result = check(verifier, bank, "MAI391-SYS-002", "[5, 3, -2]", steps)
        assert result.first_wrong_step == 2
        assert L.ERR_ROWOP in result.candidate_error_codes

    def test_gop_nhieu_phep_bien_doi_vao_mot_buoc(self, verifier, bank) -> None:
        """Tương đương hàng không quan tâm thứ tự hay số phép biến đổi."""
        steps = [self.GOOD[0], "[[1, 0, 0, 5], [0, 1, 0, 3], [0, 0, 1, -2]]"]
        assert check(verifier, bank, "MAI391-SYS-002", "[5, 3, -2]", steps).first_wrong_step is None

    def test_bo_dong_toan_so_0_van_hop_le(self, verifier, bank) -> None:
        steps = ["[[1, 1, 1, 1], [2, 2, 2, 2]]", "[[1, 1, 1, 1]]"]
        result = check(verifier, bank, "MAI391-SYS-003", "[1 - s - t, s, t]", steps)
        assert result.first_wrong_step is None

    def test_dap_an_dung_nhung_buoc_sai_thi_chua_dat(self, verifier, bank) -> None:
        steps = [self.GOOD[0], "[[1, 1, 1, 6], [0, 2, 5, -4], [0, 3, -3, 17]]"]
        result = check(verifier, bank, "MAI391-SYS-002", "[5, 3, -2]", steps)
        assert result.final_answer_correct is True
        assert result.is_correct is False


# ==========================================================================
# Định thức, nghịch đảo
# ==========================================================================

class TestDeterminant:
    def test_dung(self, verifier, bank) -> None:
        assert check(verifier, bank, "MAI391-DET-003", "10").is_correct

    def test_quen_doi_dau_khi_doi_hang(self, verifier, bank) -> None:
        assert L.ERR_DET_SIGN in check(verifier, bank, "MAI391-DET-003", "-10").candidate_error_codes

    def test_nhan_hang_voi_k_ma_khong_bu(self, verifier, bank) -> None:
        assert L.ERR_DET_SCALE in check(verifier, bank, "MAI391-DET-003", "20").candidate_error_codes

    def test_sai_tuy_y_thi_khong_bia_chan_doan(self, verifier, bank) -> None:
        """7 so với 10 là tỉ số 7/10 — không có ý nghĩa gì, không được gán mã lỗi."""
        result = check(verifier, bank, "MAI391-DET-003", "7")
        assert result.final_answer_correct is False
        assert result.candidate_error_codes == []


class TestInverse:
    def test_dung_dang_phan_so(self, verifier, bank) -> None:
        assert check(verifier, bank, "MAI391-INV-001", "[[3/5, -7/10], [-1/5, 2/5]]").is_correct

    def test_dung_dang_thap_phan(self, verifier, bank) -> None:
        assert check(verifier, bank, "MAI391-INV-001", "[[0.6, -0.7], [-0.2, 0.4]]").is_correct

    def test_quen_chia_dinh_thuc(self, verifier, bank) -> None:
        result = check(verifier, bank, "MAI391-INV-001", "[[6, -7], [-2, 4]]")
        assert L.ERR_INV_NODET in result.candidate_error_codes

    def test_quen_chuyen_vi(self, verifier, bank) -> None:
        result = check(verifier, bank, "MAI391-INV-001", "[[3/5, -1/5], [-7/10, 2/5]]")
        assert L.ERR_INV_TRANSPOSE in result.candidate_error_codes

    def test_quen_doi_dau_voi_ma_tran_2x2(self, verifier, bank) -> None:
        result = check(verifier, bank, "MAI391-INV-001", "[[6/10, 7/10], [2/10, 4/10]]")
        assert L.ERR_INV_NOSIGN in result.candidate_error_codes

    def test_ma_tran_suy_bien(self, verifier, bank) -> None:
        assert check(verifier, bank, "MAI391-INV-003", "không khả nghịch").is_correct
        result = check(verifier, bank, "MAI391-INV-003", "[[1, 0], [0, 1]]")
        assert L.ERR_INV_SINGULAR in result.candidate_error_codes

    def test_ket_luan_suy_bien_sai(self, verifier, bank) -> None:
        result = check(verifier, bank, "MAI391-INV-001", "không khả nghịch")
        assert L.ERR_INV_FALSE_SINGULAR in result.candidate_error_codes


# ==========================================================================
# Trị riêng, vector riêng
# ==========================================================================

class TestEigen:
    def test_tri_rieng_khong_quan_tam_thu_tu(self, verifier, bank) -> None:
        assert check(verifier, bank, "MAI391-EIG-001", "{3, 1}").is_correct
        assert check(verifier, bank, "MAI391-EIG-001", "λ = 1; λ = 3").is_correct

    def test_thieu_tri_rieng(self, verifier, bank) -> None:
        assert L.ERR_EIG_MISSING in check(verifier, bank, "MAI391-EIG-001", "3").candidate_error_codes

    def test_gia_tri_khong_phai_tri_rieng(self, verifier, bank) -> None:
        assert L.ERR_EIG_NOTVALUE in check(verifier, bank, "MAI391-EIG-001", "3, 4").candidate_error_codes

    @pytest.mark.parametrize("answer", ["[1, 1]", "[3, 3]", "[-2, -2]", "[t, t]"])
    def test_vector_rieng_moi_boi_vo_huong(self, verifier, bank, answer: str) -> None:
        """Vector riêng xác định sai khác một bội — kể cả bội dạng tham số."""
        assert check(verifier, bank, "MAI391-VEC-001", answer).is_correct

    def test_vector_0(self, verifier, bank) -> None:
        assert L.ERR_EIG_ZEROVEC in check(verifier, bank, "MAI391-VEC-001", "[0, 0]").candidate_error_codes

    def test_vector_rieng_cua_tri_rieng_khac(self, verifier, bank) -> None:
        """[1, -1] đúng là vector riêng — nhưng của λ = 1, đề hỏi λ = 3."""
        result = check(verifier, bank, "MAI391-VEC-001", "[1, -1]")
        assert result.final_answer_correct is False
        assert L.ERR_EIG_WRONGVALUE in result.candidate_error_codes
        assert "λ = 1" in result.notes[0]

    def test_khong_phai_vector_rieng(self, verifier, bank) -> None:
        assert L.ERR_EIG_NOTEIGEN in check(verifier, bank, "MAI391-VEC-001", "[1, 2]").candidate_error_codes


# ==========================================================================
# Phương trình vi phân
# ==========================================================================

class TestODE:
    @pytest.mark.parametrize("answer", [
        "C1*exp(x) + C2*exp(2*x)",
        "y = C1 e^x + C2 e^(2x)",          # cách viết tự nhiên của sinh viên
        "y(x) = A*exp(2*x) + B*exp(x)",    # tên hằng số khác, thứ tự khác
    ])
    def test_nghiem_tong_quat_moi_cach_viet(self, verifier, bank, answer: str) -> None:
        result = check(verifier, bank, "MAI391-ODE-002", answer)
        assert result.is_correct, f"{answer}: {result.notes}"

    def test_thieu_hang_so(self, verifier, bank) -> None:
        result = check(verifier, bank, "MAI391-ODE-002", "C1*exp(x)")
        assert L.ERR_ODE_INCOMPLETE in result.candidate_error_codes

    def test_nghiem_kep_hai_hang_so_phu_thuoc(self, verifier, bank) -> None:
        """Lỗi kinh điển nhất: nghiệm kép r = 1 mà viết C1·eˣ + C2·eˣ.

        Có hai ký hiệu hằng số nhưng chúng gộp lại được thành một — đếm ký hiệu
        sẽ chấm bài này là đúng. Phải đếm số hằng số ĐỘC LẬP.
        """
        result = check(verifier, bank, "MAI391-ODE-004", "C1*exp(x) + C2*exp(x)")
        assert result.final_answer_correct is False
        assert L.ERR_ODE_INCOMPLETE in result.candidate_error_codes

    def test_nghiem_kep_dung(self, verifier, bank) -> None:
        assert check(verifier, bank, "MAI391-ODE-004", "(C1 + C2*x)*exp(x)").is_correct
        assert check(verifier, bank, "MAI391-ODE-004", "C1*exp(x) + C2*x*exp(x)").is_correct

    def test_nghiem_luong_giac(self, verifier, bank) -> None:
        assert check(verifier, bank, "MAI391-ODE-003", "C1*cos(2x) + C2*sin(2x)").is_correct

    def test_khong_phai_nghiem(self, verifier, bank) -> None:
        result = check(verifier, bank, "MAI391-ODE-002", "C1*exp(-x) + C2*exp(2*x)")
        assert L.ERR_ODE_NOTSOLUTION in result.candidate_error_codes

    def test_chi_co_nghiem_rieng(self, verifier, bank) -> None:
        """y' − y = x: −x − 1 thoả phương trình nhưng thiếu phần C·eˣ."""
        result = check(verifier, bank, "MAI391-ODE-005", "-x - 1")
        assert L.ERR_ODE_NOHOMO in result.candidate_error_codes

    def test_khong_thuan_nhat_dung(self, verifier, bank) -> None:
        assert check(verifier, bank, "MAI391-ODE-005", "C*exp(x) - x - 1").is_correct

    def test_bai_toan_gia_tri_dau(self, verifier, bank) -> None:
        assert check(verifier, bank, "MAI391-ODE-006", "3*exp(-x)").is_correct
        assert check(verifier, bank, "MAI391-ODE-007", "2*sin(x)").is_correct

    def test_chua_dung_dieu_kien_dau(self, verifier, bank) -> None:
        result = check(verifier, bank, "MAI391-ODE-006", "C1*exp(-x)")
        assert L.ERR_ODE_IC_UNSOLVED in result.candidate_error_codes

    def test_sai_dieu_kien_dau(self, verifier, bank) -> None:
        assert L.ERR_ODE_IC in check(verifier, bank, "MAI391-ODE-006", "2*exp(-x)").candidate_error_codes

    def test_sai_dieu_kien_dau_cua_dao_ham(self, verifier, bank) -> None:
        """sin(x) thoả y(0) = 0 nhưng y'(0) = 1 chứ không phải 2."""
        result = check(verifier, bank, "MAI391-ODE-007", "sin(x)")
        assert L.ERR_ODE_IC in result.candidate_error_codes
        assert "y'(0)" in result.notes[0]


class TestRobustness:
    def test_khong_doc_duoc_thi_hoi_lai(self, verifier, bank) -> None:
        result = check(verifier, bank, "MAI391-INV-001", "[[1, 2], [3")
        assert result.final_answer_correct is None

    def test_hang_lech_do_dai_thi_hoi_lai(self, verifier, bank) -> None:
        assert check(verifier, bank, "MAI391-INV-001", "[[1, 2], [3]]").final_answer_correct is None

    def test_dap_an_rong(self, verifier, bank) -> None:
        assert check(verifier, bank, "MAI391-DET-001", "  ").final_answer_correct is False
