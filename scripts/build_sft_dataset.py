"""Dựng tập dữ liệu phân loại mã lỗi — chạy: python scripts/build_sft_dataset.py [trần mỗi mã]

Ghi ra data/sft/{train,validation,test}.jsonl. Dùng cho hai việc:

- fine-tune LoRA (Phần H, chạy trên Colab/Kaggle);
- đo baseline prompting ngay tại máy (``scripts/exp3_error_classification.py``).

Ba con số in ra cuối cùng đáng nhìn kỹ: số mã lỗi có mặt ở TEST (thiếu mã nào là
macro-F1 không so sánh được giữa các lần chạy), số đề trùng giữa train và test
(phải bằng 0), và mã lỗi hiếm nhất còn bao nhiêu mẫu.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.config import ROOT  # noqa: E402
from src.data_gen.sft_dataset import (  # noqa: E402
    build_examples,
    cap_per_code,
    label_distribution,
    split_by_item,
    write_jsonl,
)

DEFAULT_CAP = 120
OUTPUT_DIR = ROOT / "data" / "sft"


def main() -> None:
    cap = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CAP

    examples = build_examples()
    print(f"\nTổng mẫu lỗi có nhãn: {len(examples)}")

    capped = cap_per_code(examples, cap)
    print(f"Sau khi chặn trần {cap} mẫu/mã: {len(capped)}")

    train, validation, test = split_by_item(capped)
    for name, part in (("train", train), ("validation", validation), ("test", test)):
        write_jsonl(part, OUTPUT_DIR / f"{name}.jsonl")

    codes_train = {e.error_code for e in train}
    codes_test = {e.error_code for e in test}
    items_train = {e.item_id for e in train}
    items_test = {e.item_id for e in test}
    distribution = label_distribution(train)

    print(f"\n{'tập':<12}{'mẫu':>8}{'mã lỗi':>9}{'đề':>8}")
    for name, part in (("train", train), ("validation", validation), ("test", test)):
        print(f"{name:<12}{len(part):>8}{len({e.error_code for e in part}):>9}"
              f"{len({e.item_id for e in part}):>8}")

    print(f"\nMã lỗi chỉ có ở train, không có ở test: {sorted(codes_train - codes_test)}")
    print(f"Đề trùng giữa train và test: {len(items_train & items_test)} (phải bằng 0)")
    thin = [f"{code} ({count})" for code, count in list(distribution.items())[-5:]]
    print(f"Mã hiếm nhất trong train: {', '.join(thin)}")
    print(f"\nĐã ghi vào {OUTPUT_DIR}\n")


if __name__ == "__main__":
    main()
