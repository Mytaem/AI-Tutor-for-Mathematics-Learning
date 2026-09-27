"""Sinh ngân hàng đề bằng template — chạy: python scripts/build_bank.py [MÃ MÔN] [số lượng]

    python scripts/build_bank.py                 # MAE101, 300 bài
    python scripts/build_bank.py MAD101 300
    python scripts/build_bank.py all 300         # cả 4 môn

Ghi ra data/items/<môn>_generated.jsonl. File này CÓ commit lên git (khác với
data/raw/) vì nó sinh lại được y hệt từ seed, và là một phần kết quả của đồ án.

Mọi bài sinh ra đều phải tự chấm được mới được nhận, nên số bài thực tế có thể
ít hơn số yêu cầu; script in ra cả hai để không ai tưởng nhầm là đã đủ.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.itembank import ITEMS_DIR, write_items

DEFAULT_COUNT = 300
SEED = 20260923

#: Mỗi môn một module sinh đề riêng; tất cả cùng giao diện generate/template_ids.
#: Mỗi môn một hay nhiều module sinh đề, tất cả cùng giao diện generate/template_ids.
#: MAE101 có hai mảng kiến thức tách biệt (giải tích và đại số tuyến tính) nên dùng
#: hai bộ sinh, chia đôi số lượng — chỉ dùng bộ giải tích thì cả chương ma trận
#: không có đề sinh tự động nào để bộ chọn bài chọn.
GENERATORS = {
    "MAE101": ["src.data_gen.item_generator", "src.data_gen.linalg_items"],
    "MAD101": ["src.data_gen.discrete_items"],
    "MAS291": ["src.data_gen.probstat_items"],
    "MAI391": ["src.data_gen.mml_items"],
}


def build(subject: str, count: int) -> None:
    from importlib import import_module

    modules = [import_module(name) for name in GENERATORS[subject]]
    templates = [name for module in modules for name in module.template_ids()]
    share = count // len(modules)
    print(f"\n=== {subject}: sinh {count} bài từ {len(templates)} template "
          f"({len(modules)} bộ sinh, seed={SEED})")

    seed = SEED if subject != "MAE101" else 20260921  # giữ nguyên seed cũ của MAE101
    items = []
    for position, module in enumerate(modules):
        # Bộ cuối nhận phần dư để tổng đúng bằng count.
        wanted = share if position < len(modules) - 1 else count - share * (len(modules) - 1)
        items += module.generate(wanted, seed=seed + 7 * position, validate=True)

    output = ITEMS_DIR / f"{subject.lower()}_generated.jsonl"
    write_items(items, output)
    print(f"Nhận {len(items)}/{count} bài (bài nào verifier không xác nhận thì loại), ghi ra {output}")

    by_template = Counter(item.meta.get("template", "?") for item in items)
    empty = [name for name in templates if name not in by_template]
    if empty:
        print(f"  ⚠ template không sinh được bài nào: {', '.join(empty)}")

    by_skill: Counter[str] = Counter()
    for item in items:
        by_skill.update(item.skills)
    print(f"  phủ {len(by_skill)} kỹ năng, template nhiều nhất {by_template.most_common(1)[0]}")

    buckets = Counter(
        "dễ" if i.difficulty < 0.4 else "trung bình" if i.difficulty < 0.65 else "khó"
        for i in items
    )
    print("  độ khó: " + ", ".join(f"{name} {buckets[name]}" for name in ("dễ", "trung bình", "khó")))


def main() -> None:
    subject = sys.argv[1].upper() if len(sys.argv) > 1 else "MAE101"
    count = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_COUNT

    if subject == "ALL":
        for code in GENERATORS:
            build(code, count)
    elif subject in GENERATORS:
        build(subject, count)
    else:
        print(f"Chưa có bộ sinh đề cho {subject}. Có: {', '.join(GENERATORS)}")
        raise SystemExit(1)
    print()


if __name__ == "__main__":
    main()
