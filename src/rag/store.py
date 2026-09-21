"""Kho truy xuất hybrid: BM25 + embedding, hợp nhất bằng RRF.

Thiết kế để **không bao giờ bị chặn**: nhánh BM25 chạy ngay, không cần tải model
nào. Nhánh embedding là phần nâng cấp, bật lên khi đã tải xong bge-m3 (~2GB).
Nhờ vậy có thể nạp giáo trình và thấy kết quả tìm kiếm ngay trong đêm đầu tiên,
không phải ngồi đợi tải model.

Không dùng FAISS: với kho vài nghìn chunk, nhân ma trận bằng numpy còn nhanh hơn
chi phí dựng index, và bớt được một dependency nặng. Khi nào kho vượt ~10⁵ chunk
thì hãy tính lại — đồ án này không tới mức đó.

Hợp nhất bằng **Reciprocal Rank Fusion** chứ không cộng điểm thô: điểm BM25 và
điểm cosine nằm trên hai thang hoàn toàn khác nhau, cộng thẳng là vô nghĩa. RRF
chỉ dùng THỨ HẠNG nên miễn nhiễm với chuyện đó.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from src.rag.bm25 import BM25
from src.rag.chunking import Chunk, ChunkType

#: Hằng số làm mượt của RRF. 60 là giá trị chuẩn trong bài báo gốc.
RRF_K = 60


@dataclass
class SearchHit:
    chunk: Chunk
    score: float
    bm25_rank: int | None = None
    dense_rank: int | None = None

    @property
    def source_label(self) -> str:
        """Nhãn trích dẫn hiển thị cho sinh viên."""
        parts = [p for p in (self.chunk.source, self.chunk.chapter) if p]
        if self.chunk.page is not None:
            parts.append(f"tr.{self.chunk.page}")
        return " — ".join(parts) if parts else "nguồn không rõ"


class Encoder:
    """Bọc sentence-transformers, nạp model theo kiểu lười."""

    def __init__(self, model_name: str = "BAAI/bge-m3") -> None:
        self.model_name = model_name
        self._model = None

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
        return self._model

    def encode(self, texts: list[str]) -> np.ndarray:
        vectors = self.model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return np.asarray(vectors, dtype=np.float32)


class RagIndex:
    """Kho chunk có thể tìm kiếm."""

    def __init__(
        self,
        chunks: list[Chunk],
        embeddings: np.ndarray | None = None,
        encoder: Encoder | None = None,
    ) -> None:
        self.chunks = chunks
        self.embeddings = embeddings
        self.encoder = encoder
        self.bm25 = BM25().fit([chunk.text for chunk in chunks])

    def __len__(self) -> int:
        return len(self.chunks)

    @property
    def has_dense(self) -> bool:
        return self.embeddings is not None and self.encoder is not None

    # ------------------------------------------------------------------

    @classmethod
    def build(
        cls,
        chunks: list[Chunk],
        encoder: Encoder | None = None,
    ) -> RagIndex:
        """Dựng kho. Không truyền ``encoder`` thì chỉ có nhánh BM25."""
        embeddings = None
        if encoder is not None and chunks:
            embeddings = encoder.encode([chunk.text for chunk in chunks])
        return cls(chunks, embeddings, encoder)

    # ------------------------------------------------------------------

    def candidates(
        self,
        subject: str | None = None,
        types: list[ChunkType] | None = None,
        skill_ids: list[str] | None = None,
    ) -> set[int]:
        """Lọc theo metadata TRƯỚC khi xếp hạng.

        Đây là chỗ giảm nhiễu hiệu quả nhất: khi sinh viên đang làm bài tích
        phân MAE101, không có lý do gì để trả về một định lý đồ thị của MAD101.
        """
        wanted_types = {t.value for t in types} if types else None
        wanted_skills = set(skill_ids) if skill_ids else None

        selected: set[int] = set()
        for index, chunk in enumerate(self.chunks):
            if subject and chunk.subject and chunk.subject != subject:
                continue
            if wanted_types and chunk.chunk_type.value not in wanted_types:
                continue
            if wanted_skills and not (wanted_skills & set(chunk.skill_ids)):
                continue
            selected.add(index)
        return selected

    # ------------------------------------------------------------------

    def _dense_search(
        self, query: str, top_k: int, candidates: set[int] | None
    ) -> list[tuple[int, float]]:
        if not self.has_dense:
            return []

        query_vector = self.encoder.encode([query])[0]
        similarities = self.embeddings @ query_vector  # đã chuẩn hoá -> chính là cosine

        indices = np.arange(len(self.chunks))
        if candidates is not None:
            mask = np.zeros(len(self.chunks), dtype=bool)
            mask[sorted(candidates)] = True
            indices = indices[mask]
            similarities = similarities[mask]

        order = np.argsort(-similarities)[:top_k]
        return [(int(indices[i]), float(similarities[i])) for i in order]

    @staticmethod
    def _fuse(ranked_lists: list[list[tuple[int, float]]]) -> dict[int, float]:
        """Reciprocal Rank Fusion trên nhiều danh sách xếp hạng."""
        fused: dict[int, float] = {}
        for ranked in ranked_lists:
            for rank, (index, _score) in enumerate(ranked, start=1):
                fused[index] = fused.get(index, 0.0) + 1.0 / (RRF_K + rank)
        return fused

    def search(
        self,
        query: str,
        top_k: int = 5,
        *,
        subject: str | None = None,
        types: list[ChunkType] | None = None,
        skill_ids: list[str] | None = None,
        pool: int = 20,
    ) -> list[SearchHit]:
        """Tìm kiếm hybrid, đã lọc theo metadata."""
        if not self.chunks:
            return []

        allowed = self.candidates(subject, types, skill_ids)
        if not allowed:
            return []

        lexical = self.bm25.search(query, top_k=pool, candidates=allowed)
        dense = self._dense_search(query, pool, allowed)

        fused = self._fuse([lexical, dense] if dense else [lexical])
        bm25_ranks = {index: rank for rank, (index, _) in enumerate(lexical, start=1)}
        dense_ranks = {index: rank for rank, (index, _) in enumerate(dense, start=1)}

        ordered = sorted(fused.items(), key=lambda pair: pair[1], reverse=True)[:top_k]
        return [
            SearchHit(
                chunk=self.chunks[index],
                score=score,
                bm25_rank=bm25_ranks.get(index),
                dense_rank=dense_ranks.get(index),
            )
            for index, score in ordered
        ]

    # ------------------------------------------------------------------

    def save(self, directory: str | Path) -> None:
        """Ghi kho ra đĩa. BM25 dựng lại khi nạp nên không cần lưu."""
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)

        payload = [
            {
                "text": chunk.text,
                "type": chunk.chunk_type.value,
                "subject": chunk.subject,
                "chapter": chunk.chapter,
                "skill_ids": chunk.skill_ids,
                "source": chunk.source,
                "page": chunk.page,
                "chunk_id": chunk.chunk_id,
            }
            for chunk in self.chunks
        ]
        (directory / "chunks.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8"
        )

        if self.embeddings is not None:
            np.save(directory / "embeddings.npy", self.embeddings)
            (directory / "encoder.txt").write_text(self.encoder.model_name, encoding="utf-8")

    @classmethod
    def load(cls, directory: str | Path, encoder: Encoder | None = None) -> RagIndex:
        directory = Path(directory)
        payload = json.loads((directory / "chunks.json").read_text(encoding="utf-8"))

        chunks = [
            Chunk(
                text=entry["text"],
                chunk_type=ChunkType(entry["type"]),
                subject=entry.get("subject", ""),
                chapter=entry.get("chapter", ""),
                skill_ids=entry.get("skill_ids", []),
                source=entry.get("source", ""),
                page=entry.get("page"),
                chunk_id=entry.get("chunk_id", ""),
            )
            for entry in payload
        ]

        embeddings_path = directory / "embeddings.npy"
        embeddings = np.load(embeddings_path) if embeddings_path.exists() else None

        if embeddings is not None and encoder is None:
            name_path = directory / "encoder.txt"
            if name_path.exists():
                encoder = Encoder(name_path.read_text(encoding="utf-8").strip())

        return cls(chunks, embeddings, encoder)
