"""Chương nào trong kho giáo trình chưa có tài liệu — chạy trước khi demo.

    python scripts/rag_coverage.py

Có script này vì một buổi demo thất bại: sinh viên hỏi "khoảng tin cậy là gì?",
kho MAS291 không có chương Khoảng tin cậy, và hệ thống trả về một đoạn của
chương Xác suất — trôi chảy, đúng môn, sai chủ đề. Thiếu dữ liệu thì phải biết
TRƯỚC khi đứng trước hội đồng, chứ không phải lúc đang demo.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.rag.coverage import (  # noqa: E402
    TEXTBOOK_MIN_CHUNKS,
    chapter_coverage,
    general_material,
)
from src.rag.hint_retriever import load_index  # noqa: E402

SUBJECTS = ("MAE101", "MAD101", "MAI391", "MAS291")


def main() -> None:
    index = load_index()
    if index is None:
        print("Chưa dựng kho — chạy scripts/build_rag_index.py trước.")
        raise SystemExit(1)

    print(f"Kho: {len(index.chunks)} đoạn "
          f"({len(index.boilerplate)} đoạn bị loại vì là mục lục/chỉ mục)\n")

    gaps: list[str] = []
    for subject in SUBJECTS:
        rows = chapter_coverage(index, subject)
        book = general_material(index, subject)
        covered = [row for row in rows if row.covered]
        missing = [row for row in rows if not row.covered]

        print(f"=== {subject} — {len(covered)}/{len(rows)} chương có slide riêng ===")
        for row in rows:
            print(f"  {'  ok ' if row.covered else 'THIẾU'}  {row.name_vi:40} {row.chunks:>5} đoạn")

        if book >= TEXTBOOK_MIN_CHUNKS:
            print(f"  + sách giáo trình chung: {book} đoạn — đủ bù cho các chương thiếu slide")
        else:
            print(f"  ! KHÔNG có sách giáo trình chung ({book} đoạn lẻ)")
            for row in missing:
                gaps.append(f"{subject} — {row.name_vi}")
        print()

    if not gaps:
        print("Mọi chương đều có tài liệu để trả lời. Demo được.")
        return

    print("=" * 70)
    print("CHƯƠNG KHÔNG CÓ TÀI LIỆU NÀO — hệ thống sẽ nói thẳng là chưa có,")
    print("và đó là hành vi đúng, nhưng demo sẽ trống đúng những chương này:\n")
    for gap in gaps:
        print(f"  • {gap}")
    print(f"\nCách bịt: thả slide của các chương trên vào data/raw/<MÔN>/slides/")
    print("rồi chạy:  python scripts/build_rag_index.py --dense")


if __name__ == "__main__":
    main()
