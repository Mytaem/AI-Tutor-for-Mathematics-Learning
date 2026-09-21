"""Sinh tập dữ liệu lỗi có nhãn — chạy: python scripts/build_error_dataset.py [MÃ MÔN]

    python scripts/build_error_dataset.py            # MAE101
    python scripts/build_error_dataset.py MAI391

Xuất ra data/errors/<môn>_injected.jsonl, dùng cho hai việc:
- huấn luyện bộ phân loại lỗi (LoRA)
- làm bộ test hồi quy cho verifier

In ra ba con số cho EXP-2/EXP-3:
- phát hiện    : verifier nhận ra bài làm là sai
- gán nhãn     : verifier gán được ÍT NHẤT một mã lỗi
- đúng mã      : trong các mã gán ra có đúng mã đã cài vào
"""

from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.itembank import ERRORS_DIR, ITEMS_DIR, SKILLS_DIR, ItemBank, load_items, load_skills
from src.core.schema import Submission
from src.data_gen.error_injector import VALUE_PRESERVING, build_dataset, write_dataset
from src.verify.registry import verifier_for


def load_full_bank(subject: str) -> ItemBank:
    """Gộp đề chép tay và đề sinh tự động (nếu có) thành một ngân hàng."""
    stem = subject.lower()
    items = load_items(ITEMS_DIR / f"{stem}.jsonl")
    generated = ITEMS_DIR / f"{stem}_generated.jsonl"
    if generated.exists():
        items += load_items(generated)
    else:
        print(f"  (chưa có đề sinh tự động cho {subject} — chỉ dùng đề chép tay)")
    return ItemBank(items=items, skills=load_skills(SKILLS_DIR / f"{stem}.json"))


def main() -> None:
    subject = sys.argv[1] if len(sys.argv) > 1 else "MAE101"
    bank = load_full_bank(subject)
    dataset = build_dataset(bank, ERRORS_DIR / f"{subject.lower()}.json")

    output = ERRORS_DIR / f"{subject.lower()}_injected.jsonl"
    write_dataset(dataset, output)

    print(f"\n{subject}: sinh {len(dataset)} mẫu lỗi từ {len(bank.items)} bài tập")
    print(f"Ghi ra: {output}\n")

    verifier = verifier_for(subject)
    detected = labeled = exact = 0
    per_code: dict[str, list[int]] = defaultdict(lambda: [0, 0])

    for record in dataset:
        item = bank.get(record.item_id)
        result = verifier.verify(item, Submission(
            item_id=item.item_id,
            final_answer=record.wrong_final_answer,
            steps=record.wrong_steps,
        ))
        if record.error_code in VALUE_PRESERVING:
            hit = record.error_code in result.candidate_error_codes
        elif record.wrong_step_index is not None:
            hit = result.first_wrong_step == record.wrong_step_index
        else:
            hit = result.final_answer_correct is False
        correct_label = record.error_code in result.candidate_error_codes

        detected += hit
        labeled += bool(result.candidate_error_codes)
        exact += correct_label
        per_code[record.error_code][0] += 1
        per_code[record.error_code][1] += correct_label

    total = len(dataset) or 1
    print(f"  {'mã lỗi':<26} {'số mẫu':>6} {'đúng mã':>8}")
    for code, (count, right) in sorted(per_code.items(), key=lambda kv: -kv[1][0]):
        print(f"  {code:<26} {count:>6} {right / count:>8.0%}")

    print(f"\n  Phát hiện (tầng ký hiệu) : {detected}/{total} = {detected / total:.1%}")
    print(f"  Gán được nhãn            : {labeled}/{total} = {labeled / total:.1%}")
    print(f"  Gán ĐÚNG mã đã cài       : {exact}/{total} = {exact / total:.1%}\n")


if __name__ == "__main__":
    main()
