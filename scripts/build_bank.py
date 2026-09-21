"""Sinh ngân hàng đề bằng template — chạy: python scripts/build_bank.py [số lượng]

Ghi ra data/items/mae101_generated.jsonl. File này CÓ commit lên git (khác với
data/raw/) vì nó sinh lại được y hệt từ seed, và là một phần kết quả của đồ án.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.itembank import ITEMS_DIR, write_items
from src.data_gen.item_generator import generate, template_ids

DEFAULT_COUNT = 300
SEED = 20260921


def main() -> None:
    count = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_COUNT

    print(f"\nĐang sinh {count} bài từ {len(template_ids())} template (seed={SEED})...")
    items = generate(count, seed=SEED, validate=True)

    output = ITEMS_DIR / "mae101_generated.jsonl"
    write_items(items, output)

    print(f"Sinh được {len(items)} bài, ghi ra {output}\n")

    by_template = Counter(item.meta["template"] for item in items)
    print("Phân bố theo template:")
    for name, number in sorted(by_template.items()):
        print(f"  {name:<22} {number:>4}")

    by_skill: Counter[str] = Counter()
    for item in items:
        by_skill.update(item.skills)
    print("\nPhân bố theo kỹ năng:")
    for name, number in by_skill.most_common():
        print(f"  {name:<24} {number:>4}")

    buckets = Counter(
        "dễ" if i.difficulty < 0.4 else "trung bình" if i.difficulty < 0.65 else "khó"
        for i in items
    )
    print("\nPhân bố độ khó:")
    for name in ("dễ", "trung bình", "khó"):
        print(f"  {name:<12} {buckets[name]:>4}")
    print()


if __name__ == "__main__":
    main()
