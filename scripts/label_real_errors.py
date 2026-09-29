"""Gán nhãn bài làm sai THẬT của sinh viên — chạy: python scripts/label_real_errors.py

    python scripts/label_real_errors.py                  # gõ tay từng bài
    python scripts/label_real_errors.py --from-db        # lấy bài làm sai đã có trong CSDL
    python scripts/label_real_errors.py --stats          # xem đã gán được bao nhiêu

Đây là công cụ cho NGƯỜI dùng, không phải thí nghiệm tự động. Toàn bộ số liệu về
chẩn đoán lỗi trong báo cáo hiện đo trên lỗi do máy cài vào; muốn có con số đáng
tin thì phải có bài làm sai thật, và việc đó không ai làm thay được.

Cách nó tiết kiệm công: với mỗi bài làm, hệ thống tự chấm và tự đề xuất mã lỗi
sẵn, người gán nhãn chỉ cần **xác nhận hoặc sửa** — nhanh hơn hẳn việc mở bảng 91
mã lỗi ra dò. Nhưng đề xuất của máy được in TÁCH BẠCH và không chọn sẵn, để người
gán nhãn không bị mồi theo: nhãn mà chỉ đi xác nhận máy thì không còn là nhãn độc
lập, và toàn bộ mục đích của tập test thật mất sạch.

Ghi ra ``data/errors/real_labeled.jsonl``, cùng định dạng với tập lỗi tổng hợp nên
mọi script đo đạc dùng lại được ngay.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.itembank import (  # noqa: E402
    ERRORS_DIR,
    ITEMS_DIR,
    ItemBank,
    load_course_error_codes,
    load_items,
)
from src.core.schema import Submission  # noqa: E402
from src.verify.registry import verifier_for  # noqa: E402

OUTPUT = ERRORS_DIR / "real_labeled.jsonl"
SUBJECTS = ("MAE101", "MAI391", "MAS291", "MAD101")


def all_items(subject: str) -> dict:
    items = dict(ItemBank.load(subject).items)
    generated = ITEMS_DIR / f"{subject.lower()}_generated.jsonl"
    if generated.exists():
        items.update({item.item_id: item for item in load_items(generated)})
    return items


def already_labelled() -> set[tuple[str, str]]:
    if not OUTPUT.exists():
        return set()
    return {
        (row["item_id"], row["wrong_final_answer"])
        for row in (json.loads(line) for line in OUTPUT.open(encoding="utf-8"))
    }


def append(row: dict) -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def show_codes(codes: dict, page: int = 0, size: int = 12) -> None:
    entries = sorted(codes.items())
    start = page * size
    for position, (code, entry) in enumerate(entries[start:start + size], start=start + 1):
        print(f"   {position:>3}. {code:<28} {entry.name_vi}")
    if start + size < len(entries):
        print(f"   … còn {len(entries) - start - size} mã, gõ 'more' để xem tiếp")


def label_one(item, answer: str, subject: str, codes: dict) -> dict | None:
    """Hỏi người dùng mã lỗi cho một bài làm. Trả None nếu họ bỏ qua."""
    verifier = verifier_for(subject)
    result = verifier.verify(item, Submission(item_id=item.item_id, final_answer=answer))

    print("\n" + "─" * 78)
    print(f"ĐỀ    : {item.statement_vi}")
    print(f"ĐÚNG  : {item.answer_text}")
    print(f"SV LÀM: {answer}")
    print(f"Bộ chấm: {'ĐÚNG' if result.final_answer_correct else 'SAI'}"
          + (f" | bước sai đầu tiên: {result.first_wrong_step}"
             if result.first_wrong_step is not None else ""))

    if result.final_answer_correct is True:
        print("  (bài này bộ chấm cho là ĐÚNG — nếu thầy cô thấy sai thì đây là ca đáng ghi lại)")

    entries = sorted(codes.items())
    print("\nNhập mã lỗi (gõ số thứ tự hoặc mã đầy đủ), 'list' để xem bảng mã,")
    print("'may' để xem máy đoán gì, 'skip' để bỏ qua, 'quit' để dừng:")

    page = 0
    while True:
        answer_text = input("> ").strip()
        if not answer_text:
            continue
        lowered = answer_text.lower()
        if lowered in ("quit", "q"):
            raise KeyboardInterrupt
        if lowered in ("skip", "s"):
            return None
        if lowered == "list":
            page = 0
            show_codes(codes, page)
            continue
        if lowered == "more":
            page += 1
            show_codes(codes, page)
            continue
        if lowered == "may":
            # Cố ý phải gõ mới hiện: xem trước máy đoán gì thì dễ gật theo.
            print(f"   máy đoán: {', '.join(result.candidate_error_codes) or 'không đoán được'}")
            continue

        if answer_text.isdigit() and 1 <= int(answer_text) <= len(entries):
            code = entries[int(answer_text) - 1][0]
        elif answer_text.upper() in codes:
            code = answer_text.upper()
        else:
            print("   không nhận ra mã đó — gõ 'list' để xem bảng mã")
            continue

        note = input("Ghi chú (bỏ trống nếu không có): ").strip()
        return {
            "item_id": item.item_id,
            "subject": subject,
            "error_code": code,
            "tier": codes[code].tier.value if hasattr(codes[code].tier, "value") else str(codes[code].tier),
            "statement_vi": item.statement_vi,
            "correct_answer": item.answer_text,
            "wrong_final_answer": answer,
            "wrong_steps": [],
            "wrong_step_index": None,
            "source": "real",
            "note": note,
            "machine_guess": list(result.candidate_error_codes),
            "machine_correct": result.final_answer_correct,
        }


def from_database(limit: int) -> list[tuple[str, str, str]]:
    """Bài làm SAI đã có sẵn trong CSDL (do sinh viên dùng web hoặc bot)."""
    from src.api.db import Store
    from src.core.config import load_config

    store = Store(load_config().database_path)
    rows = store._connection.execute(
        "SELECT subject, item_id, raw_input FROM attempts "
        "WHERE is_correct = 0 AND raw_input != '' ORDER BY attempt_id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [(row["subject"] or "MAE101", row["item_id"], row["raw_input"]) for row in rows]


def stats() -> None:
    if not OUTPUT.exists():
        print(f"Chưa có {OUTPUT} — chưa gán nhãn bài nào.")
        return
    rows = [json.loads(line) for line in OUTPUT.open(encoding="utf-8")]
    by_subject: dict[str, int] = {}
    by_code: dict[str, int] = {}
    agree = 0
    for row in rows:
        by_subject[row["subject"]] = by_subject.get(row["subject"], 0) + 1
        by_code[row["error_code"]] = by_code.get(row["error_code"], 0) + 1
        if row["error_code"] in row.get("machine_guess", []):
            agree += 1

    print(f"\nĐã gán nhãn {len(rows)} bài làm sai thật")
    print(f"  theo môn: {by_subject}")
    print(f"  phủ {len(by_code)} mã lỗi")
    print(f"  máy đoán trùng nhãn người: {agree}/{len(rows)} = {agree / len(rows):.1%}")
    print("\n  Con số cuối chính là EXP-2 trên dữ liệu THẬT — thứ mà toàn bộ phần")
    print("  đánh giá chẩn đoán lỗi đang thiếu. Mục tiêu: 200 bài.\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--from-db", action="store_true", help="lấy bài làm sai có sẵn trong CSDL")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--stats", action="store_true")
    args = parser.parse_args()

    if args.stats:
        stats()
        return

    tables = {subject: load_course_error_codes(subject) for subject in SUBJECTS}
    banks = {subject: all_items(subject) for subject in SUBJECTS}
    done = already_labelled()
    saved = 0

    try:
        if args.from_db:
            pending = [(s, i, a) for s, i, a in from_database(args.limit) if (i, a) not in done]
            print(f"Có {len(pending)} bài làm sai chưa gán nhãn trong CSDL.")
            for subject, item_id, answer in pending:
                item = banks.get(subject, {}).get(item_id)
                if item is None:
                    continue
                row = label_one(item, answer, subject, tables[subject])
                if row:
                    append(row)
                    saved += 1
        else:
            print("Gõ tay: nhập mã đề rồi nhập bài làm của sinh viên. Ctrl+C để dừng.\n")
            while True:
                item_id = input("Mã đề (ví dụ MAE101-INT-010): ").strip().upper()
                subject = item_id.split("-", 1)[0]
                item = banks.get(subject, {}).get(item_id)
                if item is None:
                    print("   không có mã đề đó")
                    continue
                answer = input("Bài làm của sinh viên: ").strip()
                if not answer:
                    continue
                row = label_one(item, answer, subject, tables[subject])
                if row:
                    append(row)
                    saved += 1
    except (KeyboardInterrupt, EOFError):
        print()

    print(f"\nĐã lưu {saved} nhãn mới vào {OUTPUT}")
    print("Xem tổng kết: python scripts/label_real_errors.py --stats")


if __name__ == "__main__":
    main()
