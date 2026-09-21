"""Demo verifier MAI391 — chạy: python scripts/demo_mai391.py

Cho thấy verifier kiểm TÍNH CHẤT toán học chứ không so khớp một đáp án chuẩn:
mọi dạng đúng đều được nhận, và mỗi kiểu sai kinh điển được gọi đúng tên.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.itembank import ItemBank
from src.core.schema import Submission
from src.verify.registry import verifier_for

CASES = [
    ("MAI391-SYS-003", [
        ("[1 - s - t, s, t]", "tham số hoá kiểu giáo trình"),
        ("[u, v, 1 - u - v]", "tham số hoá khác hẳn — vẫn đúng"),
        ("[1, 0, 0]", "chỉ một nghiệm riêng"),
    ]),
    ("MAI391-VEC-001", [
        ("[1, 1]", "vector riêng"),
        ("[-3, -3]", "bội vô hướng khác — vẫn đúng"),
        ("[1, -1]", "vector riêng của trị riêng KHÁC"),
        ("[0, 0]", "vector 0"),
    ]),
    ("MAI391-INV-001", [
        ("[[0.6, -0.7], [-0.2, 0.4]]", "dạng thập phân"),
        ("[[6, -7], [-2, 4]]", "ma trận phụ hợp, quên chia det"),
        ("[[6/10, 7/10], [2/10, 4/10]]", "quên đổi dấu (2×2)"),
    ]),
    ("MAI391-ODE-004", [
        ("(C1 + C2*x)*exp(x)", "nghiệm kép, dạng đúng"),
        ("C1*exp(x) + C2*exp(x)", "nghiệm kép, dạng SAI kinh điển"),
    ]),
    ("MAI391-ODE-007", [
        ("2*sin(x)", "thoả phương trình và điều kiện đầu"),
        ("sin(x)", "thoả phương trình, sai y'(0)"),
        ("C1*cos(x) + C2*sin(x)", "chưa dùng điều kiện đầu"),
    ]),
]


def main() -> None:
    bank = ItemBank.load("MAI391")
    verifier = verifier_for("MAI391")

    for item_id, answers in CASES:
        item = bank.get(item_id)
        print(f"\n{'=' * 78}\n{item.statement_vi}\n{'=' * 78}")
        for answer, label in answers:
            result = verifier.verify(item, Submission(item_id=item_id, final_answer=answer))
            verdict = {True: "ĐÚNG", False: "SAI ", None: " ?  "}[result.final_answer_correct]
            codes = ", ".join(result.candidate_error_codes) or "—"
            print(f"  [{verdict}] {answer:<28} ({label})")
            print(f"           mã lỗi: {codes}")
            print(f"           lý do : {result.notes[0][:70]}")

    print(f"\n{'=' * 78}\nKHỬ GAUSS — kiểm tra từng bước bằng tương đương hàng\n{'=' * 78}")
    item = bank.get("MAI391-SYS-002")
    steps = [
        "[[1, 1, 1, 6], [0, 2, 5, -4], [2, 5, -1, 27]]",
        "[[1, 1, 1, 6], [0, 2, 5, -4], [0, 3, -3, 17]]",   # R3 − 2·R1 tính sai: 15 thành 17
        "[[1, 1, 1, 6], [0, 2, 5, -4], [0, 0, -21/2, 23]]",
    ]
    result = verifier.verify(item, Submission(item_id=item.item_id, steps=steps, final_answer="[5, 3, -2]"))
    for check in result.step_results:
        mark = {True: "OK ", False: "SAI", None: " ? "}[check.ok]
        print(f"  bước {check.step}: {mark}  {check.reason[:62]}")
    print(f"\n  → bước sai đầu tiên: {result.first_wrong_step} | mã lỗi: {', '.join(result.candidate_error_codes)}")
    print(f"  → đáp án cuối đúng nhưng bài chưa đạt: {result.final_answer_correct and not result.is_correct}\n")


if __name__ == "__main__":
    main()
