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

import hashlib
import json
import re
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
            # Chunk dài tối đa 1200 ký tự ≈ 300–400 token, nên 512 là đủ. Mặc định
            # của bge-m3 là 8192: một chunk hỏng dài bất thường sẽ ngốn cả giờ CPU.
            self._model.max_seq_length = min(self._model.max_seq_length, 512)
        return self._model

    def encode(self, texts: list[str], batch_size: int = 16) -> np.ndarray:
        # Hiện tiến độ khi mã hoá cả kho: trên CPU, vài nghìn đoạn mất hàng chục
        # phút, không có tiến độ thì không biết nó đang chạy hay đã treo.
        vectors = self.model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=len(texts) > 100,
        )
        return np.asarray(vectors, dtype=np.float32)


class OllamaEncoder:
    """bge-m3 chạy qua Ollama (llama.cpp, trọng số lượng tử hoá).

    Lý do có lớp này, đo trên máy phát triển với 64 chunk thật:

    - Tốc độ: 4.8 chunk/giây so với 1.2 của sentence-transformers (PyTorch fp32)
      — mã hoá cả kho 10 nghìn chunk mất ~37 phút thay vì ~2.5 giờ.
    - Chất lượng: cosine giữa vector hai bên thấp nhất 0.9981, trung bình 0.9999;
      truy vấn tiếng Việt cho cùng kết quả top-1. Lượng tử hoá không làm đổi thứ
      hạng tìm kiếm.

    Vector hai bên KHÔNG trộn vào cùng một kho: ``model_name`` khác nhau nên bộ
    đệm và file vector của kho luôn tách riêng theo từng backend.
    """

    def __init__(self, model: str = "bge-m3", url: str = "http://localhost:11434", timeout: float = 600.0) -> None:
        self.model = model
        self.url = url.rstrip("/")
        self.timeout = timeout
        self.model_name = f"ollama:{model}"

    def available(self) -> bool:
        try:
            import httpx

            tags = httpx.get(f"{self.url}/api/tags", timeout=5.0).json().get("models", [])
        except Exception:
            return False
        return any(t.get("name", "").split(":")[0] == self.model.split(":")[0] for t in tags)

    def encode(self, texts: list[str], batch_size: int = 16) -> np.ndarray:
        import httpx

        vectors: list[list[float]] = []
        total = len(texts)
        for start in range(0, total, batch_size):
            response = httpx.post(
                f"{self.url}/api/embed",
                json={"model": self.model, "input": texts[start:start + batch_size]},
                timeout=self.timeout,
            )
            response.raise_for_status()
            vectors.extend(response.json()["embeddings"])
            done = min(start + batch_size, total)
            if total > 100 and (done // batch_size) % 25 == 0 or done == total and total > 100:
                print(f"  đã mã hoá {done}/{total} đoạn", flush=True)

        matrix = np.asarray(vectors, dtype=np.float32)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        return matrix / np.where(norms == 0, 1.0, norms)


def encoder_from_name(name: str):
    """Dựng lại bộ mã hoá từ tên lưu trong kho (``encoder.txt``)."""
    if name.startswith("ollama:"):
        return OllamaEncoder(name.split(":", 1)[1])
    return Encoder(name)


def best_available_encoder():
    """Ollama nếu đang chạy và có sẵn bge-m3 (nhanh gấp ~4 lần), không thì sentence-transformers."""
    ollama = OllamaEncoder()
    return ollama if ollama.available() else Encoder()


class EmbeddingCache:
    """Vector đã mã hoá, tra theo hash của NỘI DUNG đoạn, lưu riêng cho từng model.

    Tách khỏi file vector của kho vì hai lý do:
    - Dựng lại kho chỉ-BM25 không được làm mất cả giờ mã hoá.
    - File vector của kho phải LUÔN khớp đúng thứ tự danh sách đoạn hiện tại —
      một file vector cũ nằm lại cạnh danh sách đoạn mới sẽ cho kết quả tìm kiếm
      sai mà không báo lỗi gì.
    """

    def __init__(self, path: str | Path | None) -> None:
        self.path = Path(path) if path else None
        self._vectors: dict[str, np.ndarray] = {}
        if self.path is not None and self.path.exists():
            data = np.load(self.path)
            self._vectors = dict(zip(data["keys"].tolist(), data["vectors"]))

    @staticmethod
    def key(text: str) -> str:
        return hashlib.sha1(text.encode("utf-8")).hexdigest()

    def __len__(self) -> int:
        return len(self._vectors)

    def missing(self, texts: list[str]) -> list[str]:
        return list(dict.fromkeys(t for t in texts if self.key(t) not in self._vectors))

    def add(self, texts: list[str], vectors: np.ndarray) -> None:
        for text, vector in zip(texts, vectors):
            self._vectors[self.key(text)] = np.asarray(vector, dtype=np.float32)

    def lookup(self, texts: list[str]) -> np.ndarray:
        return np.stack([self._vectors[self.key(t)] for t in texts]).astype(np.float32)

    def save(self) -> None:
        if self.path is None or not self._vectors:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        keys = np.array(list(self._vectors))
        np.savez(self.path, keys=keys, vectors=np.stack([self._vectors[k] for k in keys]))


#: Chữ cái chỉ có trong tiếng Việt — đủ để nhận ra câu hỏi tiếng Việt mà không
#: cần thư viện nhận dạng ngôn ngữ nào.
_VIETNAMESE_LETTERS = set("ăâđêôơưàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵ")

#: Câu hỏi tiếng Việt viết KHÔNG DẤU thì không có chữ nào ở trên; bắt qua từ chức năng.
_VIETNAMESE_WORDS = {"la", "gi", "cua", "cach", "the", "nao", "tinh", "tim", "khi", "cho"}


def looks_vietnamese(text: str) -> bool:
    lowered = text.lower()
    if any(character in _VIETNAMESE_LETTERS for character in lowered):
        return True
    words = set(re.findall(r"[a-z]+", lowered))
    return len(words & _VIETNAMESE_WORDS) >= 2


#: Dấu chấm dẫn của mục lục: «Chương 3 ........ 45».
_LEADER_DOTS = re.compile(r"\.{3,}\s*\d+")
#: Một dòng chỉ mục: «thuật ngữ, 694» — tên rồi số trang.
_INDEX_ENTRY = re.compile(r"[A-Za-zÀ-ỹ][^,\n]{2,40},\s*\d{1,4}")


def looks_like_boilerplate(text: str) -> bool:
    """Đoạn này là mục lục / chỉ mục chứ không phải nội dung?

    Ba dấu hiệu, cố ý đặt ngưỡng cao để không cắt oan nội dung thật:

    * nhiều dấu chấm dẫn  → mục lục
    * nhiều dòng "tên, số trang" → trang chỉ mục cuối sách
    * dày đặc chữ số mà thưa dấu câu → bảng tra, danh sách trang

    Một định lý có trích dẫn trang ("xem tr. 45") chỉ khớp một lần nên không bị
    cắt; phải từ bốn dòng kiểu chỉ mục trở lên mới tính.
    """
    stripped = text.strip()
    if len(stripped) < 60:
        return False
    if len(_LEADER_DOTS.findall(stripped)) >= 2:
        return True
    if len(_INDEX_ENTRY.findall(stripped)) >= 4:
        return True
    digits = sum(character.isdigit() for character in stripped)
    sentences = stripped.count(".") + stripped.count("!") + stripped.count("?")
    return digits / len(stripped) > 0.22 and sentences < len(stripped) / 220


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
        self._boilerplate: set[int] | None = None

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
        cache: EmbeddingCache | None = None,
    ) -> RagIndex:
        """Dựng kho. Không truyền ``encoder`` thì chỉ có nhánh BM25.

        ``cache``: vector đã mã hoá từ trước, tra theo NỘI DUNG đoạn. Chỉ đoạn
        mới mới phải mã hoá — bge-m3 trên CPU mất cỡ một giờ cho cả bộ giáo
        trình, không thể trả giá đó mỗi lần thêm một cuốn sách.
        """
        embeddings = None
        if encoder is not None and chunks:
            # KHÔNG viết `cache or ...`: EmbeddingCache có __len__, nên một bộ đệm
            # RỖNG bị coi là False và bị thay bằng bộ đệm không có đường dẫn lưu —
            # lần mã hoá đầu tiên (đắt nhất) sẽ không bao giờ được ghi xuống đĩa.
            if cache is None:
                cache = EmbeddingCache(None)
            texts = [chunk.text for chunk in chunks]
            missing = cache.missing(texts)
            print(f"  embedding: dùng lại {len(texts) - len(missing)} vector, mã hoá mới {len(missing)} đoạn")
            if missing:
                cache.add(missing, encoder.encode(missing))
            embeddings = cache.lookup(texts)
        return cls(chunks, embeddings, encoder)

    # ------------------------------------------------------------------

    @property
    def boilerplate(self) -> set[int]:
        """Các đoạn là TRANG MỤC LỤC hoặc TRANG CHỈ MỤC, tính một lần rồi giữ.

        Đây là loại rác nguy hiểm nhất cho BM25: trang chỉ mục đặc kín thuật
        ngữ nên khớp rất cao với mọi truy vấn, mà không chứa một câu giải thích
        nào. Hỏi "Chu trình Euler là gì?" thì đoạn hạng nhất từng là dòng
        «Euler circuit of, 694 Euler path of, 698 orientation of, 740» — tệ hơn
        là không trả lời, vì nó trông như một câu trả lời.

        Lọc ở đây chứ không lọc lúc dựng kho: không cần dựng lại 10.566 đoạn và
        43 MB embedding, mà vẫn chặn được ở mọi đường truy xuất.
        """
        if self._boilerplate is None:
            self._boilerplate = {
                index for index, chunk in enumerate(self.chunks)
                if looks_like_boilerplate(chunk.text)
            }
        return self._boilerplate

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
        junk = self.boilerplate

        selected: set[int] = set()
        for index, chunk in enumerate(self.chunks):
            if index in junk:
                continue
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

    def best_similarity(self, query: str, subject: str | None = None) -> float | None:
        """Độ tương đồng cosine cao nhất giữa câu hỏi và kho.

        Dùng để nhận ra câu hỏi NGOÀI PHẠM VI. Không dùng điểm RRF của
        ``search`` được: RRF chỉ là hàm của THỨ HẠNG nên câu hỏi nào cũng cho
        điểm gần như nhau, kể cả "cách nấu phở".

        Trả None khi kho chưa có embedding — khi đó không có cách nào phân biệt,
        và bên gọi phải tự quyết.
        """
        if not self.has_dense:
            return None
        allowed = self.candidates(subject, None, None)
        hits = self._dense_search(query, 1, allowed)
        return hits[0][1] if hits else None

    def _fusion_mode(self, fusion: str, query: str) -> str:
        """Chọn nhánh tìm kiếm. ``auto`` = theo ngôn ngữ câu hỏi.

        Đo được ở EXP-4 (70 câu hỏi, k = 5): câu hỏi TIẾNG VIỆT trên kho giáo
        trình tiếng Anh cho Recall@5 là BM25 0.167, dense 0.595, hybrid 0.310 —
        hybrid TỆ HƠN dense vì RRF trộn kết quả rác của BM25 vào làm loãng. Câu
        hỏi tiếng Anh thì ngược lại: BM25 0.929, dense 0.833, hybrid 0.976.

        Nên: hỏi cùng ngôn ngữ với kho thì hợp nhất hai nhánh, hỏi khác ngôn ngữ
        thì chỉ dùng nhánh dense (bge-m3 vốn đa ngữ).
        """
        if fusion != "auto":
            return fusion
        if self.has_dense and looks_vietnamese(query):
            return "dense"
        return "hybrid"

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
        fusion: str = "auto",
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

        mode = self._fusion_mode(fusion, query)
        lexical = self.bm25.search(query, top_k=pool, candidates=allowed) if mode != "dense" else []
        dense = self._dense_search(query, pool, allowed) if mode != "bm25" else []

        lists = [ranking for ranking in (lexical, dense) if ranking]
        fused = self._fuse(lists) if lists else {}
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
        else:
            # Kho chỉ-BM25: xoá file vector của lần dựng TRƯỚC, nếu không lần nạp
            # sau sẽ ghép vector cũ với danh sách đoạn mới. Vector không mất —
            # chúng vẫn nằm trong EmbeddingCache.
            for stale in ("embeddings.npy", "encoder.txt"):
                (directory / stale).unlink(missing_ok=True)

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
                encoder = encoder_from_name(name_path.read_text(encoding="utf-8").strip())

        if embeddings is not None and len(embeddings) != len(chunks):
            raise ValueError(
                f"Kho hỏng: {len(embeddings)} vector nhưng {len(chunks)} đoạn — dựng lại bằng build_rag_index.py"
            )
        return cls(chunks, embeddings, encoder)
