"""Sinh tập dữ liệu lỗi có nhãn — chạy: python scripts/build_error_dataset.py

Xuất ra data/errors/<môn>_injected.jsonl, dùng cho hai việc:
- huấn luyện bộ phân loại lỗi (LoRA)
- làm bộ test hồi quy cho verifier
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.itembank import ERRORS_DIR, ITEMS_DIR, SKILLS_DIR, ItemBank, load_items, load_skills
from src.core.schema import Submission
from src.data_gen.error_injector import build_dataset, write_dataset
from src.verify.calculus import CalculusVerifier

SUBJECT = "MAE101"


def load_full_bank() -> ItemBank:
    """Gộp đề chép tay và đề sinh tự động thành một ngân hàng."""
    items = load_items(ITEMS_DIR / "mae101.jsonl")

    generated = ITEMS_DIR / "mae101_generated.jsonl"
    if generated.exists():
        items += load_items(generated)
    else:
        print("  (chưa có đề sinh tự động — chạy scripts/build_bank.py trước để có nhiều dữ liệu hơn)")

    return ItemBank(items=items, skills=load_skills(SKILLS_DIR / "mae101.json"))


def main() -> None:
    bank = load_full_bank()
    dataset = build_dataset(bank, ERRORS_DIR / f"{SUBJECT.lower()}.json")

    output = ERRORS_DIR / f"{SUBJECT.lower()}_injected.jsonl"
    write_dataset(dataset, output)

    print(f"\nĐã sinh {len(dataset)} mẫu lỗi từ {len(bank.items)} bài tập")
    print(f"Ghi ra: {output}\n")

    # Đo tỉ lệ verifier phát hiện được — chính là số liệu cho EXP-2.
    verifier = CalculusVerifier()
    detected = 0
    labeled = 0

    for record in dataset:
        item = bank.get(record.item_id)
        result = verifier.verify(item, Submission(
            item_id=item.item_id,
            final_answer=record.wrong_final_answer,
            steps=record.wrong_steps,
        ))
        if record.error_code == "MAE.INT.NOCONST":
            hit = "MAE.INT.NOCONST" in result.candidate_error_codes
        elif record.error_code == "MAE.ALG.STEP":
            hit = result.first_wrong_step == record.wrong_step_index
        else:
            hit = result.final_answer_correct is False
        detected += hit
        labeled += bool(result.candidate_error_codes)

    total = len(dataset)
    print("Phân bố theo mã lỗi:")
    for code, count in Counter(r.error_code for r in dataset).most_common():
        print(f"  {code:<30} {count:>3}")

    print(f"\n  Tỉ lệ phát hiện (tầng ký hiệu) : {detected}/{total} = {detected / total:.1%}")
    print(f"  Tỉ lệ gán được nhãn            : {labeled}/{total} = {labeled / total:.1%}")
    print("\n  Khoảng cách giữa hai con số trên chính là phần việc của bộ phân loại neural.\n")


if __name__ == "__main__":
    main()
