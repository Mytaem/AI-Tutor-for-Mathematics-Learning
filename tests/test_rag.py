"""Test pipeline RAG trên corpus giả.

Chạy không cần giáo trình thật và không cần tải model embedding — nhánh BM25 đủ
để kiểm tra toàn bộ luồng: chia chunk, lọc metadata, xếp hạng, hợp nhất, lưu/nạp.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.itembank import ERRORS_DIR  # noqa: E402
from src.rag.bm25 import BM25, tokenize  # noqa: E402
from src.rag.chunking import Chunk, ChunkType, assign_ids, chunk_text  # noqa: E402
from src.rag.ingest import clean_text, ingest_all, load_pitfalls  # noqa: E402
from src.rag.store import RagIndex  # noqa: E402

GIAO_TRINH = """
Chương 3. Nguyên hàm và tích phân

Định nghĩa 3.1. Hàm số F(x) được gọi là nguyên hàm của hàm số f(x) trên khoảng K
nếu F'(x) = f(x) với mọi x thuộc K. Mọi nguyên hàm của f đều có dạng F(x) + C.

Định lý 3.2. Nếu F là một nguyên hàm của f trên K thì với mỗi hằng số C, hàm số
G(x) = F(x) + C cũng là một nguyên hàm của f trên K.

Công thức 3.3. Bảng nguyên hàm cơ bản: nguyên hàm của x mũ n bằng x mũ n cộng 1
chia cho n cộng 1, với n khác âm một.

Ví dụ 3.4. Tính nguyên hàm của x bình phương. Áp dụng quy tắc luỹ thừa ta được
x mũ ba chia ba cộng C.

Chú ý 3.5. Sinh viên thường quên cộng hằng số C vào kết quả. Nguyên hàm là một
họ hàm số chứ không phải một hàm duy nhất.

Bài tập 3.6. Tính các nguyên hàm sau đây và kiểm tra lại bằng phép đạo hàm.
"""


@pytest.fixture(scope="module")
def chunks() -> list[Chunk]:
    return assign_ids(chunk_text(
        GIAO_TRINH, subject="MAE101", chapter="Nguyên hàm", source="giaotrinh.pdf", page=42
    ))


@pytest.fixture(scope="module")
def index(chunks: list[Chunk]) -> RagIndex:
    return RagIndex.build(chunks)


# ==========================================================================
# Chia chunk theo cấu trúc
# ==========================================================================

class TestChunking:
    def test_nhan_dien_dung_cac_moc(self, chunks: list[Chunk]) -> None:
        found = {chunk.chunk_type for chunk in chunks}
        assert ChunkType.DEFINITION in found
        assert ChunkType.THEOREM in found
        assert ChunkType.FORMULA in found
        assert ChunkType.EXAMPLE in found
        assert ChunkType.PITFALL in found, "'Chú ý' phải được nhận là bẫy thường gặp"
        assert ChunkType.EXERCISE in found

    def test_khong_cat_dinh_nghia_lam_doi(self, chunks: list[Chunk]) -> None:
        """Định nghĩa bị cắt đôi thì cả hai nửa đều vô dụng."""
        definitions = [c for c in chunks if c.chunk_type is ChunkType.DEFINITION]
        assert len(definitions) == 1
        assert "F'(x) = f(x)" in definitions[0].text
        assert "F(x) + C" in definitions[0].text, "Phần cuối của định nghĩa bị mất"

    def test_moi_chunk_giu_metadata(self, chunks: list[Chunk]) -> None:
        for chunk in chunks:
            assert chunk.subject == "MAE101"
            assert chunk.chapter == "Nguyên hàm"
            assert chunk.source == "giaotrinh.pdf"
            assert chunk.page == 42
            assert chunk.chunk_id

    def test_van_ban_khong_co_moc_thi_cat_theo_doan(self) -> None:
        text = "Đoạn thứ nhất nói về một nội dung nào đó khá dài dòng.\n\n" * 3
        result = chunk_text(text)
        assert result
        assert all(c.chunk_type is ChunkType.PROSE for c in result)

    def test_van_ban_rong_khong_sinh_chunk(self) -> None:
        assert chunk_text("") == []
        assert chunk_text("   \n\n  ") == []

    def test_lam_sach_van_ban_trich_tu_pdf(self) -> None:
        """Từ bị gạch nối xuống dòng phải được nối lại, nếu không token sẽ vỡ."""
        assert "nguyên" in clean_text("nguy-\nên hàm")
        assert clean_text("a\n\n\n\n\nb") == "a\n\nb"


# ==========================================================================
# BM25
# ==========================================================================

class TestTokenize:
    def test_giu_ky_hieu_toan_lam_token(self) -> None:
        tokens = tokenize("Tính ∫ x dx")
        assert "∫" in tokens, "Ký hiệu toán là tín hiệu truy xuất rất mạnh, không được vứt"
        assert "dx" in tokens

    def test_bo_tu_dung(self) -> None:
        assert "của" not in tokenize("nguyên hàm của hàm số")
        assert "nguyên" in tokenize("nguyên hàm của hàm số")

    def test_giu_bien_mot_ky_tu(self) -> None:
        assert "x" in tokenize("đạo hàm theo x")


class TestBM25:
    def test_tra_ve_tai_lieu_khop_nhat(self) -> None:
        engine = BM25().fit([
            "nguyên hàm của hàm số luỹ thừa",
            "đồ thị Euler và chu trình Hamilton",
            "kiểm định giả thuyết thống kê",
        ])
        hits = engine.search("nguyên hàm luỹ thừa")
        assert hits and hits[0][0] == 0

    def test_khong_khop_thi_tra_rong(self) -> None:
        engine = BM25().fit(["nguyên hàm", "đạo hàm"])
        assert engine.search("zzzz không có từ này") == []

    def test_gioi_han_pham_vi_xep_hang(self) -> None:
        engine = BM25().fit(["nguyên hàm luỹ thừa", "nguyên hàm lượng giác"])
        hits = engine.search("nguyên hàm", candidates={1})
        assert [index for index, _ in hits] == [1]


# ==========================================================================
# Kho truy xuất
# ==========================================================================

class TestRagIndex:
    def test_tim_duoc_dinh_nghia(self, index: RagIndex) -> None:
        hits = index.search("nguyên hàm là gì", top_k=3)
        assert hits
        assert any("Định nghĩa" in hit.chunk.text for hit in hits)

    def test_loc_theo_loai_noi_dung(self, index: RagIndex) -> None:
        """Hint mức 1 chỉ được lấy định nghĩa và công thức, không lấy bài tập."""
        hits = index.search("nguyên hàm", types=[ChunkType.DEFINITION, ChunkType.FORMULA])
        assert hits
        assert all(
            hit.chunk.chunk_type in {ChunkType.DEFINITION, ChunkType.FORMULA} for hit in hits
        )

    def test_loc_theo_mon_hoc(self, chunks: list[Chunk]) -> None:
        """Đang làm MAE101 thì không được trả về nội dung MAD101."""
        other = Chunk("Đồ thị Euler có chu trình đi qua mọi cạnh đúng một lần",
                      ChunkType.THEOREM, subject="MAD101")
        index = RagIndex.build(chunks + [other])

        hits = index.search("đồ thị Euler chu trình", subject="MAE101")
        assert all(hit.chunk.subject == "MAE101" for hit in hits)

    def test_loc_theo_ky_nang(self) -> None:
        index = RagIndex.build([
            Chunk("Đổi biến số trong tích phân", ChunkType.FORMULA,
                  subject="MAE101", skill_ids=["MAE.INT.SUBST"]),
            Chunk("Tích phân từng phần", ChunkType.FORMULA,
                  subject="MAE101", skill_ids=["MAE.INT.PARTS"]),
        ])
        hits = index.search("tích phân", skill_ids=["MAE.INT.PARTS"])
        assert len(hits) == 1
        assert "từng phần" in hits[0].chunk.text

    def test_loc_het_thi_tra_rong_chu_khong_loi(self, index: RagIndex) -> None:
        assert index.search("nguyên hàm", subject="MAS291") == []

    def test_kho_rong_khong_loi(self) -> None:
        assert RagIndex.build([]).search("bất kỳ") == []

    def test_chi_co_bm25_van_chay_duoc(self, index: RagIndex) -> None:
        """Không có model embedding thì vẫn phải tìm kiếm được."""
        assert not index.has_dense
        assert index.search("nguyên hàm")

    def test_hit_co_nhan_trich_dan(self, index: RagIndex) -> None:
        hit = index.search("nguyên hàm")[0]
        assert "giaotrinh.pdf" in hit.source_label
        assert "tr.42" in hit.source_label, "Thiếu số trang thì sinh viên không tra lại được"


class TestPersistence:
    def test_luu_roi_nap_lai_giu_nguyen_ket_qua(
        self, index: RagIndex, tmp_path: Path
    ) -> None:
        index.save(tmp_path / "idx")
        reloaded = RagIndex.load(tmp_path / "idx")

        assert len(reloaded) == len(index)
        before = [h.chunk.chunk_id for h in index.search("nguyên hàm", top_k=3)]
        after = [h.chunk.chunk_id for h in reloaded.search("nguyên hàm", top_k=3)]
        assert before == after

    def test_giu_nguyen_metadata_sau_khi_nap(self, index: RagIndex, tmp_path: Path) -> None:
        index.save(tmp_path / "idx")
        reloaded = RagIndex.load(tmp_path / "idx")
        assert reloaded.chunks[0].subject == "MAE101"
        assert reloaded.chunks[0].page == 42


# ==========================================================================
# Nạp tài liệu
# ==========================================================================

class TestIngest:
    def test_nap_duoc_thu_muc_theo_mon(self, tmp_path: Path) -> None:
        (tmp_path / "MAE101").mkdir()
        (tmp_path / "MAE101" / "chuong3.md").write_text(GIAO_TRINH, encoding="utf-8")
        (tmp_path / "MAD101").mkdir()
        (tmp_path / "MAD101" / "logic.md").write_text(
            "Định nghĩa. Mệnh đề là câu khẳng định có giá trị chân lý xác định.",
            encoding="utf-8",
        )

        chunks = ingest_all(tmp_path)
        subjects = {chunk.subject for chunk in chunks}
        assert subjects == {"MAE101", "MAD101"}, "Môn học phải suy ra từ tên thư mục"
        assert all(chunk.chunk_id for chunk in chunks)

    def test_bo_qua_dinh_dang_khong_ho_tro(self, tmp_path: Path) -> None:
        (tmp_path / "MAE101").mkdir()
        (tmp_path / "MAE101" / "anh.png").write_bytes(b"khong phai tai lieu")
        (tmp_path / "MAE101" / "ok.md").write_text(GIAO_TRINH, encoding="utf-8")
        assert ingest_all(tmp_path)

    def test_nap_bay_tu_taxonomy_loi(self) -> None:
        """Bảng bẫy viết tay là nguồn chất lượng cao nhất, phải nạp được."""
        pitfalls = load_pitfalls(ERRORS_DIR / "mae101.json", "MAE101")
        assert len(pitfalls) >= 10
        assert all(c.chunk_type is ChunkType.PITFALL for c in pitfalls)
        assert all(c.source.startswith("taxonomy:") for c in pitfalls)
        assert any("hằng số" in c.text for c in pitfalls)


class TestEmbeddingCache:
    """Vector đệm theo nội dung: dựng lại kho không phải mã hoá lại, và không bao giờ lệch thứ tự."""

    class FakeEncoder:
        model_name = "fake"

        def __init__(self) -> None:
            self.encoded: list[str] = []

        def encode(self, texts):
            import numpy as np

            self.encoded.extend(texts)
            return np.array([[len(t), 1.0] for t in texts], dtype=np.float32)

    def test_chi_ma_hoa_doan_moi(self, chunks, tmp_path: Path) -> None:
        from src.rag.store import EmbeddingCache

        path = tmp_path / "cache.npz"
        first = self.FakeEncoder()
        RagIndex.build(chunks, first, cache=(cache := EmbeddingCache(path)))
        cache.save()
        assert len(first.encoded) == len({c.text for c in chunks})

        extra = Chunk("Định nghĩa mới hoàn toàn về chuỗi số hội tụ tuyệt đối", ChunkType.DEFINITION, "MAE101")
        second = self.FakeEncoder()
        index = RagIndex.build(chunks + [extra], second, cache=EmbeddingCache(path))
        assert second.encoded == [extra.text], "Chỉ đoạn mới được mã hoá lại"
        assert len(index.embeddings) == len(chunks) + 1

    def test_dung_kho_bm25_xoa_vector_cu_khong_de_lech(self, chunks, tmp_path: Path) -> None:
        """Vector cũ nằm lại cạnh danh sách đoạn mới sẽ cho kết quả sai mà không báo lỗi."""
        RagIndex.build(chunks, self.FakeEncoder()).save(tmp_path / "idx")
        assert (tmp_path / "idx" / "embeddings.npy").exists()

        RagIndex.build(chunks[:2]).save(tmp_path / "idx")
        assert not (tmp_path / "idx" / "embeddings.npy").exists()
        assert len(RagIndex.load(tmp_path / "idx")) == 2

    def test_nap_kho_lech_so_vector_thi_bao_loi(self, chunks, tmp_path: Path) -> None:
        import numpy as np

        RagIndex.build(chunks, self.FakeEncoder()).save(tmp_path / "idx")
        np.save(tmp_path / "idx" / "embeddings.npy", np.zeros((1, 2), dtype=np.float32))
        with pytest.raises(ValueError, match="Kho hỏng"):
            RagIndex.load(tmp_path / "idx")
