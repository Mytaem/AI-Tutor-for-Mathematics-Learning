"""Test bộ nạp ASSISTments.

File thật 82 MB không nằm trong git (``data/kt/*.csv`` bị .gitignore), nên test
dựng một file CSV tí hon đúng định dạng gốc. Thứ cần canh là **các bước làm sạch
theo quy ước của literature** — làm khác đi thì AUC báo cáo không so được với bài
báo nào, mà cũng chẳng có gì báo động.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.kt.assistments import describe, load_sequences  # noqa: E402

#: File gốc là UTF-8 có BOM nhưng phải đọc bằng latin-1 (có ký tự không hợp lệ ở
#: cột tên kỹ năng), nên BOM hiện ra thành ba ký tự "ï»¿" dính vào tên cột đầu.
HEADER = "ï»¿order_id,user_id,correct,original,skill_id,skill_name"
#: Tên kỹ năng để tiếng Anh như file gốc — file đọc bằng latin-1 nên không chứa
#: được chữ tiếng Việt có dấu.
ROWS = [
    # người 1: đủ dài, có một lượt scaffolding (original=0) phải bị loại
    *[f"{i},1,{i % 2},1,10,Addition" for i in range(1, 11)],
    "11,1,0,0,10,Addition",
    # người 2: chỉ 3 lượt — quá ngắn, bị loại cả người
    *[f"{i},2,1,1,20,Fractions" for i in range(12, 15)],
    # người 3: đủ dài nhưng có lượt thiếu skill_id
    *[f"{i},3,1,1,30,Graphs" for i in range(15, 26)],
    "26,3,1,1,,Unknown",
]


@pytest.fixture
def csv_path(tmp_path: Path) -> Path:
    path = tmp_path / "assistments.csv"
    path.write_text("\n".join([HEADER, *ROWS]) + "\n", encoding="latin-1")
    return path


class TestLoading:
    def test_bo_nguoi_qua_it_luot(self, csv_path: Path) -> None:
        sequences = load_sequences(csv_path, min_interactions=10)
        assert len(sequences) == 2, "người chỉ có 3 lượt phải bị loại"

    def test_bo_luot_scaffolding(self, csv_path: Path) -> None:
        """original=0 là bài phụ sinh ra KHI HỌC SINH LÀM SAI.

        Giữ lại là rò rỉ: chính sự tồn tại của lượt đó đã tiết lộ kết quả cần đoán.
        """
        sequences = load_sequences(csv_path, min_interactions=10)
        assert len(sequences[0]) == 10

    def test_bo_luot_khong_co_ky_nang(self, csv_path: Path) -> None:
        sequences = load_sequences(csv_path, min_interactions=10)
        assert all(skill for sequence in sequences for skill, _ in sequence)
        assert len(sequences[1]) == 11

    def test_dung_dinh_dang_chuoi(self, csv_path: Path) -> None:
        for sequence in load_sequences(csv_path, min_interactions=10):
            assert all(isinstance(skill, str) and answer in (0, 1) for skill, answer in sequence)

    def test_gioi_han_do_dai_va_so_nguoi(self, csv_path: Path) -> None:
        assert len(load_sequences(csv_path, min_interactions=10, max_students=1)) == 1
        assert all(len(s) <= 5 for s in load_sequences(csv_path, min_interactions=3, max_length=5))

    def test_thieu_file_thi_bao_ro_cach_tai(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="kaggle datasets download"):
            load_sequences(tmp_path / "khong-co.csv")


class TestDescribe:
    def test_thong_ke_khop_voi_du_lieu(self, csv_path: Path) -> None:
        stats = describe(load_sequences(csv_path, min_interactions=10))
        assert stats["students"] == 2
        assert stats["interactions"] == 21
        assert stats["skills"] == 2
        assert 0.0 <= stats["accuracy"] <= 1.0
