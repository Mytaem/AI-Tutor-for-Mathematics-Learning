"""Phân tích lỗi của chính hệ thống (mục L4) — chạy: python scripts/exp_error_analysis.py

    python scripts/exp_error_analysis.py                # cả 4 môn
    python scripts/exp_error_analysis.py --subject MAE101 --show 15

Lấy mọi ca mà bộ chấm KHÔNG gán đúng mã lỗi đã cài vào, rồi phân loại NGUYÊN NHÂN
để biết nên sửa chỗ nào trước. Không có bảng này thì "gán đúng mã 72,3%" chỉ là
một con số, không nói được phần 27,7% còn lại hỏng vì cái gì.

Năm nguyên nhân, phân biệt được bằng máy:

    khong_gan_nhan     bắt được là sai nhưng không gán nổi mã nào
    gan_nham_ma        gán mã khác — hai kiểu sai cho cùng một đáp án
    bat_duoc_nhieu_ma  có gán đúng nhưng kèm mã thừa (gợi ý có thể nhắm sai bẫy)
    khong_bat_duoc_sai chấm bài sai thành ĐÚNG — nguy hiểm nhất
    loi_ky_thuat       verifier ném lỗi khi chấm

Riêng ``khong_bat_duoc_sai`` phải soi từng ca: phần lớn là lỗi CỐ Ý giữ nguyên giá
trị (quên + C, sai ở bước mà đáp án cuối vẫn đúng), nhưng nếu có ca nào khác thì
đó là lỗ hổng thật của bộ chấm.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.config import ROOT  # noqa: E402
from src.core.itembank import ERRORS_DIR, ITEMS_DIR, ItemBank, load_items  # noqa: E402
from src.core.schema import Submission  # noqa: E402
from src.data_gen.error_injector import VALUE_PRESERVING  # noqa: E402
from src.verify.registry import verifier_for  # noqa: E402

SUBJECTS = ("MAE101", "MAI391", "MAS291", "MAD101")

CAUSES = {
    "khong_gan_nhan": "bắt được là sai nhưng không gán nổi mã nào",
    "gan_nham_ma": "gán sang mã khác",
    "bat_duoc_nhieu_ma": "có mã đúng nhưng kèm mã thừa",
    "khong_bat_duoc_sai": "chấm bài SAI thành đúng",
    "loi_ky_thuat": "verifier ném lỗi",
}


def all_items(subject: str) -> dict:
    items = dict(ItemBank.load(subject).items)
    generated = ITEMS_DIR / f"{subject.lower()}_generated.jsonl"
    if generated.exists():
        items.update({item.item_id: item for item in load_items(generated)})
    return items


def classify(row: dict, items: dict, verifier) -> tuple[str, dict]:
    """Chấm lại một mẫu lỗi và nói xem hệ thống hỏng ở đâu (nếu có)."""
    item = items[row["item_id"]]
    detail = {"item_id": row["item_id"], "error_code": row["error_code"],
              "statement": item.statement_vi[:90], "answer": row["wrong_final_answer"][:60]}
    try:
        result = verifier.verify(item, Submission(
            item_id=item.item_id, final_answer=row["wrong_final_answer"],
            steps=[str(step) for step in row.get("wrong_steps") or []]))
    except Exception as exc:
        return "loi_ky_thuat", {**detail, "note": f"{type(exc).__name__}: {exc}"[:90]}

    codes = list(result.candidate_error_codes)
    detail["got"] = ", ".join(codes) or "—"

    value_preserving = (row["error_code"] in VALUE_PRESERVING
                        or row["wrong_final_answer"].strip() == row["correct_answer"].strip())
    if result.final_answer_correct is True and not value_preserving:
        return "khong_bat_duoc_sai", detail
    if row["error_code"] in codes:
        return ("bat_duoc_nhieu_ma", detail) if len(codes) > 1 else ("dung", detail)
    if not codes:
        return "khong_gan_nhan", detail
    return "gan_nham_ma", detail


def confusion(pairs: list[tuple[str, str]], limit: int = 8) -> list[str]:
    """Cặp mã hay bị nhầm lẫn nhất — chính là chỗ taxonomy chưa tách bạch."""
    counter = Counter(pairs)
    return [f"{expected} → {got} ({count} ca)" for (expected, got), count in counter.most_common(limit)]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--subject", default=None)
    parser.add_argument("--show", type=int, default=6, help="số ca in ra làm ví dụ")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    subjects = [args.subject.upper()] if args.subject else list(SUBJECTS)
    totals: Counter[str] = Counter()
    per_subject: dict[str, Counter] = {}
    by_code: dict[str, Counter] = defaultdict(Counter)
    confusions: list[tuple[str, str]] = []
    examples: dict[str, list[dict]] = defaultdict(list)

    for subject in subjects:
        path = ERRORS_DIR / f"{subject.lower()}_injected.jsonl"
        if not path.exists():
            continue
        rows = [json.loads(line) for line in path.open(encoding="utf-8")]
        items = all_items(subject)
        verifier = verifier_for(subject)
        counter: Counter[str] = Counter()

        for row in rows:
            if row["item_id"] not in items:
                continue
            cause, detail = classify(row, items, verifier)
            counter[cause] += 1
            totals[cause] += 1
            if cause == "dung":
                continue
            by_code[row["error_code"]][cause] += 1
            if cause == "gan_nham_ma":
                confusions.append((row["error_code"], detail["got"].split(", ")[0]))
            if len(examples[cause]) < args.show:
                examples[cause].append({**detail, "subject": subject})

        per_subject[subject] = counter
        total = sum(counter.values())
        print(f"{subject}: {counter['dung'] / total:.1%} gán đúng mã "
              f"({counter['dung']}/{total})")

    total = sum(totals.values())
    print(f"\n{'nguyên nhân':<20}{'số ca':>8}{'tỉ lệ':>9}")
    print(f"{'gán đúng mã':<20}{totals['dung']:>8}{totals['dung'] / total:>9.1%}")
    for cause, description in CAUSES.items():
        if totals[cause]:
            print(f"{cause:<20}{totals[cause]:>8}{totals[cause] / total:>9.1%}   {description}")

    if confusions:
        print("\nCặp mã hay nhầm nhất (đây là chỗ taxonomy chưa tách bạch):")
        for line in confusion(confusions):
            print(f"  {line}")

    worst = sorted(by_code.items(), key=lambda kv: -sum(kv[1].values()))[:6]
    print("\nMã lỗi hệ thống hay chẩn đoán hỏng nhất:")
    for code, counter in worst:
        breakdown = ", ".join(f"{cause} {count}" for cause, count in counter.most_common())
        print(f"  {code:<28} {breakdown}")

    for cause in ("khong_bat_duoc_sai", "khong_gan_nhan", "loi_ky_thuat"):
        if not examples[cause]:
            continue
        print(f"\nVí dụ — {CAUSES[cause]}:")
        for sample in examples[cause][:args.show]:
            print(f"  [{sample['subject']}] {sample['item_id']} ({sample['error_code']})")
            print(f"     đề: {sample['statement']}")
            print(f"     bài làm: {sample['answer']} | hệ thống gán: {sample.get('got', '—')}"
                  f"{' | ' + sample['note'] if sample.get('note') else ''}")

    out = args.out or ROOT / "experiments" / "error_analysis" / "summary.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "total": total,
        "causes": dict(totals),
        "per_subject": {s: dict(c) for s, c in per_subject.items()},
        "confusions": confusion(confusions, limit=20),
        "worst_codes": {code: dict(counter) for code, counter in worst},
        "examples": {cause: rows for cause, rows in examples.items()},
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nĐã ghi {out}\n")


if __name__ == "__main__":
    main()
