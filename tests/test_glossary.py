"""Test từ điển thuật ngữ Việt–Anh và phép đo độ phủ kho giáo trình.

Hai module này sinh ra từ một buổi demo thất bại: sinh viên hỏi tiếng Việt,
giáo trình tiếng Anh, và hệ thống trả lời trôi chảy nhưng sai chủ đề. Nên thứ
đáng canh nhất ở đây là **đừng để nó trôi chảy mà sai** lần nữa.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.rag.coverage import _words, chapter_for_terms, normalise  # noqa: E402
from src.rag.glossary import TERMS, english_terms, expand  # noqa: E402
from src.rag.store import looks_like_boilerplate  # noqa: E402


class TestTuDien:
    @pytest.mark.parametrize("question, expected", [
        ("Chu trình Euler là gì?", "euler circuit"),
        ("Tích phân từng phần là gì?", "integration by parts"),
        ("Quy tắc hàm hợp là gì?", "chain rule"),
        ("Định lý giới hạn trung tâm nói gì?", "central limit theorem"),
        ("Khoảng tin cậy là gì?", "confidence interval"),
        ("Cây khung nhỏ nhất là gì?", "minimum spanning tree"),
    ])
    def test_nhan_ra_thuat_ngu(self, question: str, expected: str) -> None:
        assert expected in english_terms(question)

    def test_cum_dai_thang_cum_ngan(self) -> None:
        """«tích phân từng phần» phải thắng «tích phân».

        Không sắp theo độ dài giảm dần thì câu hỏi về integration by parts chỉ
        được mở rộng thành "integral", và lại trả về đúng cái đoạn sai như cũ.
        """
        terms = english_terms("Tích phân từng phần là gì?")
        assert terms == ["integration by parts"]

        terms = english_terms("Cây khung nhỏ nhất là gì?")
        assert "minimum spanning tree" in terms
        assert "tree" not in terms

    def test_khong_dau_van_nhan_ra(self) -> None:
        """Sinh viên gõ nhanh hay thiếu dấu, và bàn phím điện thoại tự sửa lung tung."""
        assert english_terms("chu trinh euler") == english_terms("chu trình Euler")

    def test_cau_ngoai_pham_vi_khong_khop_gi(self) -> None:
        """Khớp bừa thì câu ngoài phạm vi được mở rộng rồi lọt qua ngưỡng chặn."""
        assert english_terms("Cách nấu phở bò ngon") == []
        assert english_terms("Messi ghi được bao nhiêu bàn") == []

    def test_mo_rong_giu_nguyen_cau_goc(self) -> None:
        """Câu gốc vẫn cần cho vector dày; phần tiếng Anh chỉ nối thêm."""
        question = "Chu trình Euler là gì?"
        assert expand(question).startswith(question)
        assert "euler circuit" in expand(question)

    def test_khong_nhan_ra_thi_tra_nguyen(self) -> None:
        assert expand("Cách nấu phở bò ngon") == "Cách nấu phở bò ngon"

    def test_khoa_trong_bang_khong_trung_lap(self) -> None:
        keys = list(TERMS)
        assert len(keys) == len(set(keys))


class TestChuanHoaTenChuong:
    def test_bo_tien_to_so_chuong(self) -> None:
        """Nhãn trong kho là "Chapter 6: Graph Theory", khoá là "Ch6 Graph Theory".

        So chuỗi thẳng thì ba trong bốn môn báo "thiếu toàn bộ" trong khi tài
        liệu nằm ngay đó — đúng lỗi tôi đã mắc ở bản đầu.
        """
        assert normalise("Ch6 Graph Theory") == normalise("Chapter 6: Graph Theory")

    def test_mo_viet_tat(self) -> None:
        """"Ch4 Continuous RVs" phải khớp "Chapter 4: Continuous Random Variables"."""
        assert normalise("Ch4 Continuous RVs") <= normalise("Chapter 4: Continuous Random Variables")

    def test_bo_so_nhieu(self) -> None:
        """"p-value" và tên kỹ năng "P-values" phải rút về cùng một tập từ."""
        assert _words("p-value") == _words("P-values")


class TestDoanChuongChoCauHoi:
    @pytest.mark.parametrize("subject, question, chapter", [
        ("MAS291", "Khoảng tin cậy là gì?", "Ch8 Statistical Intervals"),
        ("MAS291", "p-value nghĩa là gì?", "Ch9 Hypothesis Tests"),
        ("MAS291", "Hồi quy tuyến tính là gì?", "Ch11 Regression"),
        ("MAD101", "Chu trình Euler là gì?", "Ch6 Graph Theory"),
    ])
    def test_doan_dung_chuong(self, subject: str, question: str, chapter: str) -> None:
        assert chapter_for_terms(subject, english_terms(question)) == chapter

    def test_trung_mot_tu_chung_thi_khong_doan(self) -> None:
        """«t distribution» trùng «Binomial distribution» đúng một chữ "distribution".

        Tin vào kiểu khớp đó thì có ngày từ chối oan một câu hỏi mà giáo trình
        có đủ tài liệu. Thà bỏ sót một lần từ chối đúng.
        """
        assert chapter_for_terms("MAS291", ["t distribution"]) is None

    def test_khong_co_thuat_ngu_thi_khong_doan(self) -> None:
        assert chapter_for_terms("MAS291", []) is None


class TestKhongBietThiKhongTuChoi:
    """Kho không mang nhãn chương thì KHÔNG được kết luận chương nào thiếu.

    Thiếu quy tắc này thì một kho nạp mà quên gắn nhãn chương sẽ làm MỌI câu
    hỏi bị trả "chưa có tài liệu" — hỏng toàn bộ, và hỏng theo cách im lặng.
    Chính test này đã bắt được nó.
    """

    def test_kho_khong_co_nhan_chuong_thi_cu_tra_loi(self) -> None:
        from src.rag.chunking import Chunk, ChunkType
        from src.rag.coverage import has_material_for
        from src.rag.store import RagIndex

        plain = RagIndex([
            Chunk(text="An Euler circuit uses every edge exactly once.",
                  chunk_type=ChunkType.DEFINITION, subject="MAD101", source="rosen.pdf"),
        ])
        assert has_material_for(plain, "MAD101", "Ch6 Graph Theory") is True

    def test_co_nhan_chuong_khac_thi_moi_dam_ket_luan(self) -> None:
        """Chương khác có nhãn hẳn hoi mới chứng tỏ sự vắng mặt là thật."""
        from src.rag.chunking import Chunk, ChunkType
        from src.rag.coverage import has_material_for
        from src.rag.store import RagIndex

        labelled = RagIndex([
            Chunk(text="Probability of an event is defined as the ratio of outcomes.",
                  chunk_type=ChunkType.DEFINITION, subject="MAS291",
                  chapter="Chapter 2: Probability", source="02_probability.pdf"),
        ])
        assert has_material_for(labelled, "MAS291", "Ch2 Probability") is True
        assert has_material_for(labelled, "MAS291", "Ch9 Hypothesis Tests") is False


class TestLocDoanRac:
    def test_bat_trang_chi_muc(self) -> None:
        """Đoạn từng được trả về hạng nhất cho câu hỏi «Chu trình Euler là gì?»."""
        assert looks_like_boilerplate(
            "Euler circuit of, 694 Euler path of, 698 orientation of, 740 "
            "paths in, 679, 736 underlying, 654, 736 Unicasting, litmus, 655"
        )

    def test_bat_trang_muc_luc(self) -> None:
        assert looks_like_boilerplate(
            "Chapter 1 Introduction ........ 1\n"
            "Chapter 2 Probability ......... 23\n"
            "Chapter 3 Random Variables .... 55\n"
        )

    def test_khong_cat_oan_noi_dung_that(self) -> None:
        """Định lý có trích dẫn trang vẫn phải được giữ."""
        assert not looks_like_boilerplate(
            "Definition. An Euler circuit in a graph G is a simple circuit "
            "containing every edge of G. See Theorem 1 on page 694 for the "
            "necessary and sufficient condition."
        )

    def test_khong_cat_oan_cong_thuc_nhieu_so(self) -> None:
        assert not looks_like_boilerplate(
            "Theorem. For a normal distribution with mean 0 and variance 1, "
            "we have P(-1.96 < Z < 1.96) = 0.95, which is the basis of the "
            "95% confidence interval used throughout this chapter."
        )

    def test_doan_ngan_khong_bi_cat(self) -> None:
        assert not looks_like_boilerplate("Euler circuit, 694")
