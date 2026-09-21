"""Demo bộ chấm MAI391 — Mathematics for Machine Learning. Chạy: python scripts/demo_mai391.py

Cho thấy bộ chấm kiểm TÍNH CHẤT toán học chứ không so khớp một đáp án chuẩn:
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
    ("MAI391-SVD-001", [
        ("3, 2", "giá trị kỳ dị"),
        ("2, 3", "thứ tự khác — vẫn đúng"),
        ("3, -2", "nhầm với trị riêng của A"),
        ("9, 4", "quên lấy căn trị riêng của AᵀA"),
    ]),
    ("MAI391-GRAD-002", [
        ("[y*exp(x*y), x*exp(x*y)]", "gradient"),
        ("[exp(x*y), exp(x*y)]", "quên nhân đạo hàm hàm trong"),
        ("[x*exp(x*y), y*exp(x*y)]", "đảo thứ tự biến"),
    ]),
    ("MAI391-GD-001", [
        ("[0.8, 0.6]", "một bước gradient descent"),
        ("[1.2, 1.4]", "đi XUÔI chiều gradient"),
        ("[-1, -3]", "quên nhân tốc độ học η"),
    ]),
    ("MAI391-LS-001", [
        ("[5/6, 3/2]", "nghiệm bình phương tối thiểu"),
        ("[0.8333333, 1.5]", "làm tròn thập phân — vẫn đúng"),
        ("[1, 1]", "đường thẳng qua đúng 2 điểm đầu"),
    ]),
    ("MAI391-PCA-001", [
        ("[1, 1]", "thành phần chính thứ nhất"),
        ("[-3, -3]", "bội âm — vẫn cùng hướng"),
        ("[1, -1]", "hướng có phương sai NHỎ nhất"),
    ]),
    ("MAI391-SVM-001", [
        ("0.4", "độ rộng lề 2/‖w‖"),
        ("0.2", "chỉ tính nửa lề"),
        ("0.08", "dùng ‖w‖² thay vì ‖w‖"),
    ]),
]


def main() -> None:
    bank = ItemBank.load("MAI391")
    verifier = verifier_for("MAI391")

    for item_id, answers in CASES:
        item = bank.get(item_id)
        part = verifier.part_for(item).name
        print(f"\n{'=' * 78}\n{item.statement_vi}\n(bộ chấm: {part})\n{'=' * 78}")
        for answer, label in answers:
            result = verifier.verify(item, Submission(item_id=item_id, final_answer=answer))
            verdict = {True: "ĐÚNG", False: "SAI ", None: " ?  "}[result.final_answer_correct]
            codes = ", ".join(result.candidate_error_codes) or "—"
            print(f"  [{verdict}] {answer:<30} ({label})")
            print(f"           mã lỗi: {codes}")
    print()


if __name__ == "__main__":
    main()
