"""Nạp giáo trình và dựng kho truy xuất.

    python scripts/build_rag_index.py            # chỉ BM25, chạy ngay, không tải gì
    python scripts/build_rag_index.py --dense    # thêm embedding bge-m3 (qua Ollama nếu có, nhanh ~4 lần)
    python scripts/build_rag_index.py --dense --hf   # ép dùng sentence-transformers
    python scripts/build_rag_index.py --ask "tích phân từng phần là gì"

Thả tài liệu vào ``data/raw/<MÃ MÔN>/`` rồi chạy. Môn học suy ra từ tên thư mục.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.config import ROOT
from src.core.itembank import COURSE_TAXONOMIES, course_taxonomy_paths
from src.rag.chunking import assign_ids
from src.rag.ingest import ingest_all, load_pitfalls
from src.rag.store import EmbeddingCache, Encoder, RagIndex, best_available_encoder

RAW_DIR = ROOT / "data" / "raw"
INDEX_DIR = ROOT / "data" / "rag_index"

SAMPLE_QUERIES = [
    "nguyên hàm là gì",
    "tích phân từng phần",
    "quên hằng số C",
    "đổi biến số",
]


def main() -> None:
    use_dense = "--dense" in sys.argv
    question = None
    if "--ask" in sys.argv:
        index = sys.argv.index("--ask")
        question = sys.argv[index + 1] if index + 1 < len(sys.argv) else None

    if question:
        _answer(question, use_dense)
        return

    if not RAW_DIR.exists() or not any(RAW_DIR.iterdir()):
        print(f"\nChưa có tài liệu nào trong {RAW_DIR}")
        print("Thả giáo trình vào data/raw/MAE101/, data/raw/MAD101/, ... rồi chạy lại.\n")
        print("Vẫn dựng kho từ bảng bẫy viết tay để hệ thống có cái mà dùng...\n")

    print("Đang đọc tài liệu:")
    chunks = ingest_all(RAW_DIR) if RAW_DIR.exists() else []

    # Bảng bẫy viết tay: nguồn chất lượng cao nhất, luôn nạp — theo bảng mã lỗi
    # của TỪNG MÔN, nên bẫy đại số tuyến tính có mặt ở cả MAE101 lẫn MAI391.
    for subject in COURSE_TAXONOMIES:
        pitfalls = [c for path in course_taxonomy_paths(subject) for c in load_pitfalls(path, subject)]
        print(f"  {subject} bẫy thường gặp (viết tay): {len(pitfalls)} chunk")
        chunks.extend(pitfalls)

    if not chunks:
        print("\nKhông có nội dung nào để dựng kho.\n")
        return

    chunks = assign_ids(chunks)

    encoder = None
    if use_dense:
        encoder = Encoder() if "--hf" in sys.argv else best_available_encoder()
        print(f"\nBộ mã hoá: {encoder.model_name}")

    cache = None
    if encoder is not None:
        cache = EmbeddingCache(INDEX_DIR / "embedding_cache" / (encoder.model_name.replace("/", "__") + ".npz"))
    index = RagIndex.build(chunks, encoder, cache=cache)
    if cache is not None:
        cache.save()
    index.save(INDEX_DIR)

    # ------------------------------------------------------------------
    print(f"\nĐã dựng kho: {len(index)} chunk → {INDEX_DIR}")
    print(f"Nhánh embedding: {'BẬT' if index.has_dense else 'TẮT (chỉ BM25)'}")

    by_subject = Counter(c.subject or "(không rõ)" for c in chunks)
    print("\nTheo môn học:")
    for name, number in by_subject.most_common():
        print(f"  {name:<14} {number:>5}")

    by_type = Counter(c.chunk_type.value for c in chunks)
    print("\nTheo loại nội dung:")
    for name, number in by_type.most_common():
        print(f"  {name:<14} {number:>5}")

    print("\nThử vài truy vấn mẫu:")
    for query in SAMPLE_QUERIES:
        hits = index.search(query, top_k=1)
        if hits:
            preview = " ".join(hits[0].chunk.text.split())[:66]
            print(f"  «{query}»")
            print(f"     [{hits[0].chunk.chunk_type.value}] {preview}...")
            print(f"     nguồn: {hits[0].source_label}")
        else:
            print(f"  «{query}» → không tìm thấy")
    print()


def _answer(question: str, use_dense: bool) -> None:
    if not INDEX_DIR.exists():
        print(f"Chưa có kho ở {INDEX_DIR}. Chạy script không kèm --ask trước.")
        return

    index = RagIndex.load(INDEX_DIR)  # bộ mã hoá dựng lại đúng loại đã dùng khi dựng kho
    print(f"\nHỏi: {question}\n")
    for rank, hit in enumerate(index.search(question, top_k=3), start=1):
        print(f"  {rank}. [{hit.chunk.chunk_type.value}] {hit.source_label}")
        print(f"     {' '.join(hit.chunk.text.split())[:200]}")
        print(f"     (điểm RRF {hit.score:.4f} | BM25 hạng {hit.bm25_rank} "
              f"| embedding hạng {hit.dense_rank})\n")


if __name__ == "__main__":
    main()
