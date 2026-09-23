"""EXP-4 — so ba cấu hình truy xuất: BM25, dense (bge-m3), và hybrid.

    python scripts/exp4_retrieval.py                 # cả ba cấu hình, mọi môn
    python scripts/exp4_retrieval.py --subject MAS291 --k 10

Bộ câu hỏi được sinh từ **taxonomy kỹ năng**: mỗi kỹ năng cho một câu hỏi tiếng
Việt (``name_vi``), và một đoạn được tính là ĐÚNG nếu nó chứa thuật ngữ tiếng Anh
của kỹ năng đó (``name_en``). Ví dụ: hỏi "Tích phân bằng phương pháp đổi biến",
đoạn đúng là đoạn có cụm "integration by substitution".

Vì sao đo như vậy, và yếu ở chỗ nào — phải ghi rõ trong báo cáo:

- **Được**: không cần gán nhãn tay, tái lập được, và đo đúng thứ đang cần biết —
  câu hỏi tiếng Việt có tìm được tài liệu tiếng Anh không.
- **Yếu**: nhãn dựa trên khớp thuật ngữ, nên một đoạn giải thích đúng khái niệm
  mà dùng từ khác (ví dụ "u-substitution" thay vì "integration by substitution")
  bị tính là sai. Con số ở đây vì thế là chặn DƯỚI, và không thay được bộ 100 cặp
  gán nhãn tay mà kế hoạch đặt ra.

Cũng chính vì nhãn dựa trên từ khoá tiếng Anh, BM25 với truy vấn TIẾNG VIỆT không
hề được ưu ái: từ khoá tiếng Anh không có trong câu hỏi.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.config import ROOT  # noqa: E402
from src.core.itembank import ItemBank  # noqa: E402
from src.rag.chunking import ChunkType  # noqa: E402
from src.rag.hint_retriever import load_index  # noqa: E402

SUBJECTS = ("MAE101", "MAI391", "MAS291", "MAD101")
#: Chunk pitfall do chính dự án viết bằng tiếng Việt — để lại thì BM25 tiếng Việt
#: thắng dễ dàng mà không nói lên điều gì về việc tra giáo trình.
EXCLUDED = {ChunkType.PITFALL}


def gold_chunks(index, subject: str, term: str) -> set[int]:
    """Các đoạn được coi là đúng: có chứa thuật ngữ tiếng Anh của kỹ năng."""
    needle = term.lower()
    return {
        position
        for position, chunk in enumerate(index.chunks)
        if chunk.subject == subject and chunk.chunk_type not in EXCLUDED
        and needle in chunk.text.lower()
    }


def ranked(index, query: str, subject: str, mode: str, k: int) -> list[int]:
    allowed = index.candidates(subject, None, None)
    allowed = {i for i in allowed if index.chunks[i].chunk_type not in EXCLUDED}
    if mode == "bm25":
        return [i for i, _ in index.bm25.search(query, top_k=k, candidates=allowed)]
    if mode == "dense":
        return [i for i, _ in index._dense_search(query, k, allowed)]
    return [hit_index(index, hit) for hit in index.search(query, top_k=k, subject=subject)]


def hit_index(index, hit) -> int:
    """Vị trí của một kết quả trong danh sách chunk (SearchHit chỉ giữ chunk)."""
    return index.chunks.index(hit.chunk)


def evaluate(index, queries: list[tuple[str, str, str]], mode: str, k: int) -> dict:
    """Recall@k, MRR và tỉ lệ câu hỏi không có kết quả đúng nào."""
    recalls: list[float] = []
    reciprocal: list[float] = []
    misses: list[str] = []

    for subject, query, term in queries:
        gold = gold_chunks(index, subject, term)
        if not gold:
            continue                       # thuật ngữ không xuất hiện trong kho: bỏ câu hỏi này
        results = ranked(index, query, subject, mode, k)
        hits = [position for position, chunk in enumerate(results, start=1) if chunk in gold]
        recalls.append(1.0 if hits else 0.0)
        reciprocal.append(1 / hits[0] if hits else 0.0)
        if not hits:
            misses.append(f"{subject}: «{query}» (cần «{term}»)")

    return {
        "n": len(recalls),
        "recall_at_k": statistics.mean(recalls) if recalls else 0.0,
        "mrr": statistics.mean(reciprocal) if reciprocal else 0.0,
        "misses": misses,
    }


def build_queries(subjects=SUBJECTS) -> list[tuple[str, str, str]]:
    """(môn, câu hỏi tiếng Việt, thuật ngữ tiếng Anh) cho từng kỹ năng."""
    queries = []
    for subject in subjects:
        for skill in ItemBank.load(subject).skills.values():
            if skill.name_en:
                queries.append((subject, skill.name_vi, skill.name_en))
    return queries


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--subject", default=None)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--english", action="store_true",
                        help="hỏi bằng chính thuật ngữ tiếng Anh — mốc trần của phép đo")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    index = load_index()
    if index is None:
        print("Chưa dựng kho RAG. Chạy: python scripts/build_rag_index.py --dense")
        raise SystemExit(1)

    subjects = (args.subject,) if args.subject else SUBJECTS
    queries = build_queries(subjects)
    if args.english:
        queries = [(subject, term, term) for subject, _, term in queries]

    print(f"\nEXP-4 — {len(queries)} câu hỏi ({'tiếng Anh' if args.english else 'tiếng Việt'}), "
          f"kho {len(index.chunks)} đoạn, k = {args.k}\n")

    summary = {}
    for mode in ("bm25", "dense", "hybrid"):
        result = evaluate(index, queries, mode, args.k)
        summary[mode] = result
        print(f"{mode:<8} n={result['n']:<4} Recall@{args.k} {result['recall_at_k']:.3f}   "
              f"MRR {result['mrr']:.3f}")

    worst = summary["hybrid"]["misses"][:5]
    if worst:
        print("\nHybrid vẫn trượt ở:")
        for line in worst:
            print(f"  - {line}")

    out = args.out or ROOT / "experiments" / "exp4" / (
        f"{'en' if args.english else 'vi'}_k{args.k}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"k": args.k, "english": args.english,
                               "queries": len(queries), "summary": summary},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nĐã ghi {out}\n")


if __name__ == "__main__":
    main()
