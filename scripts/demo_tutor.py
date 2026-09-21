"""Demo phiên gia sư đầy đủ — chạy: python scripts/demo_tutor.py

Mô phỏng một sinh viên làm bài sai, xin gợi ý dần, rồi sửa được. Không dùng LLM:
toàn bộ gợi ý sinh từ template + taxonomy lỗi, nên chạy được mọi lúc, kể cả khi
mất mạng hoặc model chết — đây cũng là đường lui cho buổi bảo vệ.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.itembank import ERRORS_DIR, ItemBank, load_error_codes
from src.core.schema import Submission
from src.tutor.hints import HintGenerator, TutorEngine
from src.verify.calculus import CalculusVerifier

WIDTH = 78


def rule(title: str = "") -> None:
    if title:
        print(f"\n{'=' * WIDTH}\n{title}\n{'=' * WIDTH}")
    else:
        print("-" * WIDTH)


def student(text: str) -> None:
    print(f"\n  SINH VIÊN │ {text}")


def tutor(response) -> None:
    if response.is_correct:
        print(f"  GIA SƯ    │ ✓ {response.congratulation}")
        if response.verification.candidate_error_codes:
            print(f"            │   (ghi nhận: {', '.join(response.verification.candidate_error_codes)})")
        return

    hint = response.hint
    print(f"  GIA SƯ    │ [mức {int(hint.level)} — {hint.level.label_vi}]")
    for line in hint.text.split("\n"):
        print(f"            │ {line}")

    tags = []
    if hint.error_code:
        tags.append(f"lỗi={hint.error_code}")
    if hint.source:
        tags.append(f"nguồn={hint.source}")
    if hint.was_blocked:
        tags.append("BỊ GUARDRAIL CHẶN")
    if tags:
        print(f"            │   ({' | '.join(tags)})")


def main() -> None:
    bank = ItemBank.load("MAE101")
    engine = TutorEngine(
        CalculusVerifier(),
        HintGenerator(
            error_codes=load_error_codes(ERRORS_DIR / "mae101.json"),
            skills=bank.skills,
            seed=7,
        ),
    )

    item = bank.get("MAE101-INT-010")

    rule("PHIÊN GIA SƯ")
    print(f"\n  ĐỀ BÀI    │ {item.statement_vi}")
    print(f"            │ kỹ năng: {', '.join(item.skills)} | độ khó: {item.difficulty}")

    # Lượt 1 — sai vì quên hệ số 1/2 từ du.
    wrong = "(x**2+1)**4 + C"
    student(f"Em làm ra {wrong}")
    response = engine.submit(item, Submission(item_id=item.item_id, final_answer=wrong))
    tutor(response)

    # Xin gợi ý thêm ba lần.
    for _ in range(3):
        student("Em chưa hiểu, thầy/cô gợi ý thêm ạ")
        response = engine.request_hint(item, response.verification)
        tutor(response)

    # Sửa được.
    correct = "(x**2+1)**4/8 + C"
    student(f"À em hiểu rồi, đáp án là {correct}")
    response = engine.submit(item, Submission(item_id=item.item_id, final_answer=correct))
    tutor(response)

    # ------------------------------------------------------------------
    rule("KHI SINH VIÊN ĐÒI XEM LỜI GIẢI NGAY")

    engine.reset(item.item_id)
    student(f"Em làm ra {wrong}")
    response = engine.submit(item, Submission(item_id=item.item_id, final_answer=wrong))
    tutor(response)

    for attempt in (1, 2):
        student("Cho em xem lời giải luôn đi ạ")
        response = engine.request_hint(item, response.verification, asked_for_solution=True)
        tutor(response)
        if attempt == 1:
            print("            │   → lần đòi đầu tiên chưa được cấp, đẩy lên một mức")

    # ------------------------------------------------------------------
    rule("CÁ NHÂN HOÁ THEO MỨC THÀNH THẠO")

    cases = [
        (0.9, "nắm vững — nhiều khả năng chỉ bất cẩn, hích nhẹ là đủ"),
        (0.5, "trung bình — nhắc lại khái niệm"),
        (0.2, "còn yếu — cảnh báo bẫy luôn"),
        (None, "chưa biết năng lực — dùng mặc định"),
    ]
    for mastery, note in cases:
        engine.reset(item.item_id)
        # want_hint=False: ghi nhận lần làm sai nhưng CHƯA phát gợi ý nào, để
        # lượt xin gợi ý sau đó dùng mức khởi đầu theo năng lực thay vì leo thang.
        first = engine.submit(
            item, Submission(item_id=item.item_id, final_answer=wrong), want_hint=False
        )
        response = engine.request_hint(item, first.verification, mastery=mastery)
        label = "None" if mastery is None else f"{mastery}"
        print(f"\n  mastery = {label:<5} ({note})")
        print(f"    → vào mức {int(response.hint.level)} — {response.hint.level.label_vi}")

    # ------------------------------------------------------------------
    rule("GUARDRAIL CHẶN LỘ ĐÁP ÁN")

    from src.tutor.guardrail import check_leak
    from src.tutor.hint_policy import HintLevel

    samples = [
        ("Em thử đặt u = x**2 + 1 xem sao?", "gợi ý hợp lệ"),
        ("Ta cần tính nguyên hàm của x*(x**2+1)**3", "nhắc lại đề bài"),
        ("Đáp án là (x**2+1)**4/8 + C", "lộ thẳng đáp án"),
        ("Kết quả bằng (x**2+1)**4 / 8", "lộ dưới dạng viết khác"),
    ]
    print()
    for text, label in samples:
        report = check_leak(text, item, HintLevel.PITFALL)
        mark = "CHẶN " if report.leaked else "cho qua"
        print(f"  [{mark}] {label:<26} {text[:44]}")
    print()


if __name__ == "__main__":
    main()
