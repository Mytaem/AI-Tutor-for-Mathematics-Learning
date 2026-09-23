"""EXP-2b — bộ chấm có chỉ đúng BƯỚC SAI ĐẦU TIÊN không?

    python scripts/exp2_step_detection.py

Phần EXP-2 ở ``build_error_dataset.py`` chỉ đo chuyện nhận ra bài làm sai và gán
đúng mã lỗi — tức là đo ở mức ĐÁP ÁN CUỐI. Nhưng cái làm nên giá trị sư phạm của
hệ thống lại là chỉ đúng chỗ sai trong lời giải: gợi ý mức 3 nói "bước 2 của em
chưa đúng", nói sai bước thì gợi ý thành vô nghĩa.

Đo ba thứ, và thứ ba quan trọng không kém hai thứ đầu:

    phát hiện     có nhận ra trong chuỗi bước có chỗ sai không
    đúng bước     chỗ nó chỉ có đúng là bước đã bị cài lỗi không
    báo oan       chạy trên LỜI GIẢI ĐÚNG: có bước nào bị kết tội oan không

Báo oan là lỗi tệ nhất trong ba: sinh viên làm đúng mà bị bảo sai thì mất lòng
tin ngay, và không có cách nào để họ "sửa" cho đúng.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.config import ROOT  # noqa: E402
from src.core.itembank import ERRORS_DIR, ITEMS_DIR, ItemBank, load_items  # noqa: E402
from src.core.schema import Submission  # noqa: E402
from src.verify.registry import verifier_for  # noqa: E402

SUBJECTS = ("MAE101", "MAI391", "MAS291", "MAD101")


def all_items(subject: str) -> dict:
    items = dict(ItemBank.load(subject).items)
    generated = ITEMS_DIR / f"{subject.lower()}_generated.jsonl"
    if generated.exists():
        items.update({item.item_id: item for item in load_items(generated)})
    return items


def step_errors(subject: str) -> list[dict]:
    path = ERRORS_DIR / f"{subject.lower()}_injected.jsonl"
    if not path.exists():
        return []
    return [row for row in (json.loads(line) for line in path.open(encoding="utf-8"))
            if row.get("wrong_step_index") is not None and row.get("wrong_steps")]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    found = exact = total = 0
    by_code: Counter[str] = Counter()
    correct_by_code: Counter[str] = Counter()
    misses: list[str] = []

    print("\nEXP-2b — chỉ đúng bước sai đầu tiên\n")
    for subject in SUBJECTS:
        rows = step_errors(subject)
        if not rows:
            continue
        items = all_items(subject)
        verifier = verifier_for(subject)
        subject_found = subject_exact = 0

        for row in rows:
            item = items.get(row["item_id"])
            if item is None:
                continue
            total += 1
            by_code[row["error_code"]] += 1
            result = verifier.verify(item, Submission(
                item_id=item.item_id,
                final_answer=row["wrong_final_answer"],
                steps=[str(step) for step in row["wrong_steps"]],
            ))
            if result.first_wrong_step is not None:
                found += 1
                subject_found += 1
                if result.first_wrong_step == row["wrong_step_index"]:
                    exact += 1
                    subject_exact += 1
                    correct_by_code[row["error_code"]] += 1
                elif len(misses) < 10:
                    misses.append(f"{item.item_id} ({row['error_code']}): "
                                  f"chỉ bước {result.first_wrong_step}, thật ra bước "
                                  f"{row['wrong_step_index']}")
            elif len(misses) < 10:
                misses.append(f"{item.item_id} ({row['error_code']}): không chỉ ra bước nào")

        print(f"  {subject}: {len(rows)} bài làm sai ở bước — phát hiện {subject_found}, "
              f"đúng bước {subject_exact}")

    # Báo oan: chạy trên chính lời giải mẫu (đúng), không được kết tội bước nào.
    false_alarms = checked = 0
    for subject in SUBJECTS:
        verifier = verifier_for(subject)
        for item in list(all_items(subject).values()):
            if len(item.reference_solution_steps) < 2:
                continue
            checked += 1
            result = verifier.verify(item, Submission(
                item_id=item.item_id, final_answer=item.answer_text,
                steps=[step.expr for step in item.reference_solution_steps],
            ))
            if result.first_wrong_step is not None:
                false_alarms += 1

    print(f"\n{'chỉ số':<34}{'giá trị':>12}")
    print(f"{'phát hiện có chỗ sai':<34}{found}/{total} = {found / max(1, total):.1%}")
    print(f"{'chỉ ĐÚNG bước đã cài lỗi':<34}{exact}/{total} = {exact / max(1, total):.1%}")
    print(f"{'báo oan trên lời giải đúng':<34}{false_alarms}/{checked} = "
          f"{false_alarms / max(1, checked):.1%}")

    if misses:
        print("\nVài ca chỉ sai bước:")
        for line in misses[:5]:
            print(f"  - {line}")

    out = args.out or ROOT / "experiments" / "exp2" / "step_detection.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "total": total, "found": found, "exact": exact,
        "detection_rate": found / max(1, total), "exact_rate": exact / max(1, total),
        "false_alarm_rate": false_alarms / max(1, checked), "checked_correct": checked,
        "by_code": {code: {"n": count, "exact": correct_by_code[code]}
                    for code, count in by_code.items()},
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nĐã ghi {out}\n")


if __name__ == "__main__":
    main()
