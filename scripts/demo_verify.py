"""Demo tầng kiểm chứng MAE101 — chạy: python scripts/demo_verify.py

Cho thấy verifier phân biệt được bốn tình huống khác nhau trên cùng một bài:
đúng hoàn chỉnh, đúng nhưng thiếu hằng số, sai đúng một hệ số, và sai hẳn bản chất.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.itembank import ItemBank
from src.core.schema import Submission
from src.verify.calculus import CalculusVerifier

CASES = [
    ("(x**2+1)**4/8 + C", "lời giải đúng hoàn chỉnh"),
    ("(x**2+1)**4/8", "đúng nhưng quên + C"),
    ("(x**2+1)**4 + C", "quên hệ số 1/8 khi đổi biến"),
    ("-((x**2+1)**4)/8 + C", "sai dấu"),
    ("x^2(x^2+1)^3 + C", "sai hẳn bản chất"),
    ("(x**2+1)**4/8 +++", "nhập liệu hỏng"),
]


def main() -> None:
    bank = ItemBank.load("MAE101")
    verifier = CalculusVerifier()
    item = bank.get("MAE101-INT-010")

    print(f"\nĐỀ BÀI : {item.statement_vi}")
    print(f"Kỹ năng : {', '.join(item.skills)}")
    print(f"Độ khó  : {item.difficulty}\n")
    print("-" * 78)

    for answer, label in CASES:
        result = verifier.verify(item, Submission(item_id=item.item_id, final_answer=answer))
        verdict = {True: "ĐÚNG", False: "SAI", None: "KHÔNG KẾT LUẬN"}[result.final_answer_correct]

        print(f"\n[{label}]")
        print(f"  Bài làm : {answer}")
        print(f"  Kết quả : {verdict}")
        print(f"  Mã lỗi  : {', '.join(result.candidate_error_codes) or '—'}")
        print(f"  Lý do   : {result.notes[0][:90]}")

    print("\n" + "=" * 78)
    print("\nKIỂM TRA CHUỖI BƯỚC CÓ ĐỔI BIẾN\n")

    chains = [
        ("lời giải đúng", [
            "Integral(x*(x**2+1)**3, x)",
            "u = x**2 + 1",
            "Integral(u**3/2, u)",
            "u**4/8",
            "(x**2+1)**4/8",
        ]),
        ("quên du = 2x dx", [
            "Integral(x*(x**2+1)**3, x)",
            "u = x**2 + 1",
            "Integral(u**3, u)",
        ]),
        ("không khai báo phép thế", [
            "Integral(x*(x**2+1)**3, x)",
            "Integral(u**3/2, u)",
        ]),
    ]

    for label, steps in chains:
        result = verifier.verify(item, Submission(item_id=item.item_id, steps=steps))
        print(f"[{label}]")
        for check in result.step_results:
            mark = {True: "OK ", False: "SAI", None: " ? "}[check.ok]
            print(f"   {check.step}. {mark}  {steps[check.step - 1]:<32} {check.reason[:60]}")
        print(f"   -> bước sai đầu tiên: {result.first_wrong_step or 'không có'}"
              f" | có bước chưa kiểm chứng được: {result.has_unverifiable_steps}\n")


if __name__ == "__main__":
    main()
