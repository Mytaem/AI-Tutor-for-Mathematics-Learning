"""Test phần logic thuần của các script thí nghiệm.

Script thí nghiệm hay bị coi là "code dùng một lần" rồi không ai test — nhưng số
liệu trong báo cáo lại sinh ra từ chính chúng. Một hàm bóc đáp án viết cẩu thả có
thể hạ accuracy của baseline xuống vài chục phần trăm, và không ai biết là do
model dở hay do code bóc sai.

Chỉ test các hàm KHÔNG gọi model: bóc đáp án, tính macro-F1, tính tỉ lệ sai.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def load_script(name: str):
    """Nạp một script trong scripts/ như module (chúng không nằm trong package)."""
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def exp3():
    return load_script("exp3_error_classification")


@pytest.fixture(scope="module")
def exp1():
    return load_script("exp1_solving")


@pytest.fixture(scope="module")
def exp7():
    return load_script("exp7_llm_judge")


class TestExtractCode:
    def test_lay_duoc_ma_trong_cau_tra_loi_dai_dong(self, exp3) -> None:
        """Model nhỏ hay trả lời thừa dù prompt cấm."""
        valid = {"MAE.INT.NOCONST"}
        assert exp3.extract_code("Mã lỗi là MAE.INT.NOCONST vì thiếu hằng số", valid) == "MAE.INT.NOCONST"

    def test_ma_bia_khong_duoc_tinh(self, exp3) -> None:
        assert exp3.extract_code("MAE.INT.KHONGCOTHAT", {"MAE.INT.NOCONST"}) is None

    def test_khong_co_ma_nao_thi_tra_none(self, exp3) -> None:
        assert exp3.extract_code("Em làm sai rồi", {"MAE.INT.NOCONST"}) is None

    def test_khong_phan_biet_hoa_thuong(self, exp3) -> None:
        assert exp3.extract_code("mae.int.noconst", {"MAE.INT.NOCONST"}) == "MAE.INT.NOCONST"


class TestMacroF1:
    def test_doan_dung_het_thi_bang_mot(self, exp3) -> None:
        score, _ = exp3.macro_f1([("A", "A"), ("B", "B")])
        assert score == 1.0

    def test_doan_sai_het_thi_bang_khong(self, exp3) -> None:
        score, _ = exp3.macro_f1([("A", "B"), ("B", "A")])
        assert score == 0.0

    def test_chi_doan_lop_pho_bien_thi_macro_f1_thap(self, exp3) -> None:
        """Điểm mấu chốt: accuracy cao mà macro-F1 vẫn tệ khi dữ liệu lệch."""
        pairs = [("A", "A")] * 9 + [("B", "A")]
        score, _ = exp3.macro_f1(pairs)
        accuracy = sum(1 for t, g in pairs if t == g) / len(pairs)
        assert accuracy == 0.9
        assert score < 0.55

    def test_khong_tra_loi_duoc_tinh_la_sai(self, exp3) -> None:
        score, _ = exp3.macro_f1([("A", None), ("A", "A")])
        assert 0.0 < score < 1.0


class TestExtractAnswer:
    def test_uu_tien_dong_dap_an(self, exp1) -> None:
        assert exp1.extract_answer("Ta có x = 2.\nĐÁP ÁN: 42") == "42"

    def test_khong_co_dong_dap_an_thi_lay_dong_cuoi(self, exp1) -> None:
        assert exp1.extract_answer("bước 1\nbước 2\nx**3/3 + C") == "x**3/3 + C"

    def test_bo_dau_nhay_va_ky_hieu_latex(self, exp1) -> None:
        assert exp1.extract_answer("ĐÁP ÁN: `x**2`") == "x**2"

    def test_chuoi_rong_khong_lam_vo(self, exp1) -> None:
        assert exp1.extract_answer("   ") == ""

    def test_chon_da_so_bo_qua_cau_rong(self, exp1) -> None:
        assert exp1.majority(["5", "", "5", "6"]) == "5"


class TestJudgeRates:
    def test_tach_rieng_hai_loai_sai(self, exp7) -> None:
        """Báo đúng cho bài SAI nguy hiểm hơn hẳn báo sai cho bài ĐÚNG."""
        results = [(False, True), (False, False), (True, True), (True, False)]
        rates = exp7.rates(results)
        assert rates["accuracy"] == 0.5
        assert rates["false_accept"] == 0.5
        assert rates["false_reject"] == 0.5

    def test_bo_cham_hoan_hao(self, exp7) -> None:
        rates = exp7.rates([(True, True), (False, False)])
        assert rates["accuracy"] == 1.0 and rates["false_accept"] == 0.0

    def test_khong_tra_loi_duoc_van_tinh_la_sai(self, exp7) -> None:
        rates = exp7.rates([(True, None), (False, None)])
        assert rates["accuracy"] == 0.0 and rates["no_answer"] == 1.0


@pytest.fixture(scope="module")
def rating():
    return load_script("build_hint_rating_sheet")


class TestCohenKappa:
    def test_dong_thuan_hoan_toan(self, rating) -> None:
        assert rating.cohen_kappa([5, 4, 3, 2], [5, 4, 3, 2]) == 1.0

    def test_lech_hoan_toan_thi_am(self, rating) -> None:
        assert rating.cohen_kappa([5, 5, 5, 1], [1, 1, 1, 5]) < 0

    def test_ai_cung_cho_mot_muc_diem_thi_khong_xac_dinh(self, rating) -> None:
        """Trùng nhau 100% nhưng kappa không xác định — trả 1.0 ở đây là tự khen."""
        value = rating.cohen_kappa([4, 4, 4, 4], [4, 4, 4, 4])
        assert value != value, "phải là NaN"

    def test_bo_qua_o_chua_cham(self, rating) -> None:
        """Ô trống (giá trị 0) không được tính là một mức điểm."""
        assert rating.cohen_kappa([5, 0, 3], [5, 0, 3]) == 1.0
