"""Test lớp truy xuất giáo trình cho gợi ý.

Kho ở đây dựng tay bằng vài đoạn giả, chỉ nhánh BM25 (không encoder) — test
phải chạy được khi chưa dựng index thật và không cần Ollama.

Hai điều được kiểm chặt nhất đều là chuyện LỘ ĐÁP ÁN: đoạn ``pitfall`` sinh từ
taxonomy lỗi không bao giờ được đưa vào prompt, và đoạn sách nào chứa sẵn đáp án
thì phải bị loại.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.itembank import ItemBank  # noqa: E402
from src.rag.chunking import Chunk, ChunkType  # noqa: E402
from src.rag.hint_retriever import make_hint_retriever  # noqa: E402
from src.rag.store import RagIndex  # noqa: E402
from src.tutor.hint_policy import HintLevel  # noqa: E402


@pytest.fixture(scope="module")
def bank() -> ItemBank:
    return ItemBank.load("MAE101")


@pytest.fixture(scope="module")
def item(bank):
    return bank.get("MAE101-INT-010")  # ∫ x(x²+1)³ dx, đáp án (x**2+1)**4/8 + C


def chunk(text: str, kind: ChunkType, source: str = "sach.pdf") -> Chunk:
    return Chunk(text=text, chunk_type=kind, subject="MAE101", chapter="Integration", source=source)


def index_of(*chunks: Chunk) -> RagIndex:
    return RagIndex(list(chunks))  # chỉ BM25, không embedding


class TestLocDeKhongLoDapAn:
    def test_khong_bao_gio_tra_ve_chunk_pitfall(self, bank, item) -> None:
        """Chunk pitfall sinh từ mô tả mã lỗi, mà mô tả lỗi có thể chứa đáp án."""
        index = index_of(
            chunk("Integration by substitution pitfall: answer is (x**2+1)**4/8 + C", ChunkType.PITFALL,
                  "taxonomy:MAE.INT.SUBST.NODX"),
            chunk("Integration by substitution: if u = g(x) then du = g'(x) dx.", ChunkType.DEFINITION),
        )
        passages = make_hint_retriever(index, bank.skills)(item, HintLevel.CONCEPT)
        assert [source for _, source in passages] == ["sach.pdf — Integration"]

    def test_loai_doan_sach_chua_san_dap_an(self, bank, item) -> None:
        index = index_of(
            chunk("Substitution example: the integral equals (x**2+1)**4/8 + C.", ChunkType.DEFINITION, "lo.pdf"),
            chunk("Substitution replaces the variable and the differential.", ChunkType.DEFINITION, "sach.pdf"),
        )
        passages = make_hint_retriever(index, bank.skills)(item, HintLevel.CONCEPT)
        assert all("lo.pdf" not in source for _, source in passages), passages

    def test_muc_duoc_phep_tiet_lo_thi_khong_loc(self, bank, item) -> None:
        """Từ mức 4 guardrail cho phép nói đáp án — nhưng mức đó không truy xuất nữa."""
        index = index_of(chunk("Substitution rule for integrals.", ChunkType.DEFINITION))
        retrieve = make_hint_retriever(index, bank.skills)
        assert retrieve(item, HintLevel.CORRECT) == []
        assert retrieve(item, HintLevel.PROBE) == []


class TestChonDoan:
    def test_truy_van_bang_ten_tieng_anh_cua_ky_nang(self, bank, item) -> None:
        """Giáo trình là tiếng Anh: hỏi bằng tên tiếng Việt kéo về đoạn lạc đề."""
        index = index_of(
            chunk("Integration by substitution: let u = g(x).", ChunkType.DEFINITION, "dung.pdf"),
            chunk("Một hàm xác định từng phần có nhiều nhánh.", ChunkType.DEFINITION, "lac.pdf"),
        )
        passages = make_hint_retriever(index, bank.skills, top_k=1)(item, HintLevel.CONCEPT)
        assert [source.split(" —")[0] for _, source in passages] == ["dung.pdf"]

    def test_ha_tang_khi_khong_co_dinh_nghia(self, bank, item) -> None:
        """Slide MAS291 gần như không có chữ 'Definition' nào — lọc cứng thì trắng tay."""
        index = index_of(chunk("Substitution changes both the variable and dx.", ChunkType.PROSE))
        assert make_hint_retriever(index, bank.skills)(item, HintLevel.CONCEPT) != []

    def test_khong_co_ky_nang_thi_khong_truy_xuat(self, bank, item) -> None:
        index = index_of(chunk("Substitution rule.", ChunkType.DEFINITION))
        bare = item.model_copy(update={"skills": []})
        assert make_hint_retriever(index, bank.skills)(bare, HintLevel.CONCEPT) == []

    def test_khong_lay_doan_cua_mon_khac(self, bank, item) -> None:
        other = Chunk(text="Integration by substitution in statistics.", chunk_type=ChunkType.DEFINITION,
                      subject="MAS291", source="khac.pdf")
        assert make_hint_retriever(index_of(other), bank.skills)(item, HintLevel.CONCEPT) == []
