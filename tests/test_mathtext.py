"""Test dọn công thức và ngôn ngữ trong câu trả lời của model.

Mọi ca ở đây lấy từ **đầu ra thật** của qwen2.5:7b-instruct, không phải ca tưởng
tượng. Trước khi có module này, trang hỏi lý thuyết in nguyên văn
``\\( \\frac{\\sigma}{\\sqrt{n}} \\)`` cho người học đọc.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.rag.mathtext import (  # noqa: E402
    cjk_ratio,
    clean_answer,
    has_cjk,
    normalise_math,
    strip_prompt_numbering,
)


class TestChuanHoaKyHieu:
    def test_cong_thuc_trong_cau(self) -> None:
        got = normalise_math(r"khi \( n \) đủ lớn")
        assert got == "khi $n$ đủ lớn"

    def test_cong_thuc_dung_rieng(self) -> None:
        got = normalise_math(r"Công thức: \[ \int u \, dv = uv - \int v \, du \]")
        assert "$$\\int u \\, dv = uv - \\int v \\, du$$" in got

    def test_khong_an_khoang_trang_quanh_dau(self) -> None:
        """Bản đầu biến "khi \\( n \\) đủ lớn" thành "khi$n$đủ lớn" — chữ dính liền.

        Lỗi này còn kéo theo lỗi thứ hai: số thứ tự sau công thức không còn đứng
        đầu câu nên không bóc ra được nữa.
        """
        got = clean_answer(r"khi \( n \) đủ lớn, \( \bar{X} \) có độ lệch chuẩn")
        assert "khi $n$ đủ lớn" in got
        assert "$n$đủ" not in got
        assert "khi$n$" not in got

    def test_da_dung_kieu_thi_khong_doi(self) -> None:
        text = r"Công thức $\sigma_{\bar{X}} = \frac{\sigma}{\sqrt{n}}$ đã đúng."
        assert normalise_math(text) == text

    def test_giu_nguyen_noi_dung_cong_thuc(self) -> None:
        """Chỉ đổi DẤU bọc ngoài, không được sửa gì bên trong công thức."""
        got = normalise_math(r"\(\sum_{v \in V} \deg(v) = 2m\)")
        assert got == r"$\sum_{v \in V} \deg(v) = 2m$"

    def test_ky_hieu_unicode_de_nguyen(self) -> None:
        """Model đôi khi viết thẳng "λ ∈ R", "∑" — đọc được ngay, đừng đụng tới."""
        text = "Trị riêng là số λ ∈ R sao cho ∑ các bậc bằng 2m."
        assert normalise_math(text) == text


class TestBoSoThuTuCuaPrompt:
    def test_bo_so_dau_cau(self) -> None:
        got = strip_prompt_numbering("(1) Định nghĩa.\n\n(2) Công thức.\n\n(3) Điều kiện.")
        assert got.startswith("Định nghĩa")
        assert "(1)" not in got and "(2)" not in got and "(3)" not in got

    def test_giu_so_giua_cau(self) -> None:
        """"nghiệm (2) của phương trình" là nội dung thật, xoá là làm hỏng nghĩa."""
        text = "nghiệm (2) của phương trình vẫn phải giữ"
        assert strip_prompt_numbering(text) == text

    def test_bo_so_ca_khi_co_cong_thuc_dung_rieng_o_giua(self) -> None:
        raw = "(1) Định nghĩa.\n\n(2) Công thức: \\[ x^2 \\]\n\n(3) Điều kiện áp dụng."
        got = clean_answer(raw)
        assert "(1)" not in got and "(2)" not in got and "(3)" not in got
        assert "$$x^2$$" in got


class TestPhatHienTiengTrung:
    def test_bat_duoc_chu_han(self) -> None:
        """Ca thật: model trả lời câu hỏi về quy tắc hàm hợp bằng tiếng Trung."""
        text = "Quy tắc hàm hợp là một quy tắc trong微分学，用于计算复合函数的导数。"
        assert has_cjk(text)
        assert cjk_ratio(text) > 0.1

    def test_tieng_viet_thuan_khong_bi_bao_sai(self) -> None:
        text = "Định lý giới hạn trung tâm nói rằng khi cỡ mẫu đủ lớn thì trung bình mẫu..."
        assert not has_cjk(text)
        assert cjk_ratio(text) == 0.0

    @pytest.mark.parametrize("text", [
        "Công thức $\\frac{\\sigma}{\\sqrt{n}}$ với λ ∈ ℝ và ∑ bậc đỉnh",
        "Dùng ký hiệu ≈, ≤, ∞, ∫, √ bình thường",
    ])
    def test_ky_hieu_toan_khong_bi_coi_la_tieng_trung(self, text: str) -> None:
        """Ký hiệu toán Unicode không nằm trong dải CJK — đừng bắt oan."""
        assert not has_cjk(text)

    def test_chuoi_rong(self) -> None:
        assert cjk_ratio("") == 0.0
