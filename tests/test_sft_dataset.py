"""Test tập dữ liệu phân loại mã lỗi.

Hai lỗi âm thầm mà test này canh:

1. **Rò rỉ giữa train và test** — một đề đẻ ra nhiều mẫu lỗi; chia theo mẫu thì
   cùng một đề nằm cả hai bên, mô hình học thuộc đề và macro-F1 đẹp giả.
2. **Mất lớp ở tập test** — macro-F1 lấy trung bình trên các lớp có mặt, nên nếu
   mỗi lần chạy tập test lại thiếu những mã khác nhau thì hai con số không so
   được với nhau.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data_gen.sft_dataset import (  # noqa: E402
    build_examples,
    cap_per_code,
    label_distribution,
    split_by_item,
)


@pytest.fixture(scope="module")
def examples():
    return build_examples()


@pytest.fixture(scope="module")
def split(examples):
    return split_by_item(cap_per_code(examples, 120))


class TestPrompt:
    def test_prompt_co_du_de_dap_an_va_bai_lam(self, examples) -> None:
        prompt = examples[0].prompt
        for field in ("ĐỀ BÀI:", "ĐÁP ÁN ĐÚNG:", "BÀI LÀM CỦA SINH VIÊN:", "DANH SÁCH MÃ LỖI:"):
            assert field in prompt

    def test_dap_an_dung_duoc_phep_co_trong_prompt(self, examples) -> None:
        """Khác prompt sinh gợi ý: ở đây hệ thống ĐÃ biết đáp án, giấu đi là tự trói tay."""
        assert "ĐÁP ÁN ĐÚNG:" in examples[0].prompt

    def test_nhan_nam_trong_danh_sach_ma_cua_mon(self, examples) -> None:
        from src.core.itembank import load_course_error_codes

        tables = {s: load_course_error_codes(s) for s in ("MAE101", "MAI391", "MAS291", "MAD101")}
        bad = [e.item_id for e in examples[::50] if e.error_code not in tables[e.subject]]
        assert bad == [], f"mã lỗi không thuộc bảng của môn: {bad[:5]}"

    def test_menu_ma_loi_dung_mon(self, examples) -> None:
        mad = next(e for e in examples if e.subject == "MAD101")
        assert "MAD." in mad.prompt
        assert "MAS." not in mad.prompt.split("DANH SÁCH MÃ LỖI:")[1]


class TestSplit:
    def test_khong_de_nao_nam_o_hai_tap(self, split) -> None:
        train, validation, test = split
        items = [{e.item_id for e in part} for part in (train, validation, test)]
        assert not (items[0] & items[1])
        assert not (items[0] & items[2])
        assert not (items[1] & items[2])

    def test_hau_het_ma_loi_deu_co_mat_o_test(self, split) -> None:
        train, _, test = split
        missing = {e.error_code for e in train} - {e.error_code for e in test}
        # Mã duy nhất được phép vắng là mã chỉ có đúng một đề trong cả ngân hàng.
        assert len(missing) <= 1, f"quá nhiều mã vắng mặt ở test: {sorted(missing)}"

    def test_ti_le_chia_xap_xi_dung(self, split) -> None:
        train, validation, test = split
        total = len(train) + len(validation) + len(test)
        assert 0.6 <= len(train) / total <= 0.8

    def test_cung_seed_chia_giong_nhau(self, examples) -> None:
        capped = cap_per_code(examples, 50)
        first = split_by_item(capped, seed=7)[2]
        second = split_by_item(capped, seed=7)[2]
        assert [e.item_id for e in first] == [e.item_id for e in second]


class TestBalance:
    def test_chan_tran_lam_giam_do_lech(self, examples) -> None:
        before = label_distribution(examples)
        after = label_distribution(cap_per_code(examples, 100))
        assert max(before.values()) > max(after.values())
        assert max(after.values()) <= 100

    def test_chan_tran_khong_lam_mat_ma_nao(self, examples) -> None:
        assert set(label_distribution(cap_per_code(examples, 30))) == set(label_distribution(examples))
