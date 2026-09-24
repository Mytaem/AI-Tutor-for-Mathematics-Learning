"""Demo toàn hệ thống cho buổi bảo vệ — chạy: python scripts/demo_full.py

    python scripts/demo_full.py              # không cần model, không cần mạng
    python scripts/demo_full.py --llm        # gợi ý do Qwen diễn đạt (cần Ollama)

Sáu cảnh, mỗi cảnh chứng minh đúng một điều mà hội đồng sẽ hỏi:

    1. Chấm đúng mọi cách viết tương đương — không so chuỗi
    2. Kiểm chéo độc lập: Monte Carlo (MAS291), liệt kê vét cạn (MAD101)
    3. Chỉ đúng BƯỚC sai đầu tiên, không chỉ báo "sai"
    4. Thang gợi ý cho dần, guardrail chặn câu làm lộ đáp án
    5. Chọn bài thích ứng theo mức thành thạo
    6. Hỏi lý thuyết có trích nguồn, hỏi ngoài phạm vi thì từ chối

Chạy được cả khi mất mạng và không có model: mặc định dùng gợi ý template. Đây là
đường lui đã chuẩn bị sẵn cho buổi bảo vệ, không phải phương án chữa cháy.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.itembank import ItemBank, load_course_error_codes  # noqa: E402
from src.core.schema import Submission  # noqa: E402
from src.kt.bkt import BKTTracker  # noqa: E402
from src.kt.coldstart import make_tracker  # noqa: E402
from src.kt.selector import select_next  # noqa: E402
from src.tutor.guardrail import check_leak  # noqa: E402
from src.tutor.hint_policy import HintLevel  # noqa: E402
from src.tutor.hints import HintGenerator  # noqa: E402
from src.verify import discrete as D  # noqa: E402
from src.verify import probstat as P  # noqa: E402
from src.verify.registry import verifier_for  # noqa: E402

WIDTH = 78


def scene(number: int, title: str) -> None:
    print(f"\n{'═' * WIDTH}\n CẢNH {number}. {title}\n{'═' * WIDTH}")


def check(subject: str, item_id: str, answer: str, bank: ItemBank | None = None):
    bank = bank or ItemBank.load(subject)
    item = bank.get(item_id)
    return item, verifier_for(subject).verify(
        item, Submission(item_id=item_id, final_answer=answer))


# --------------------------------------------------------------------------

def scene_equivalence() -> None:
    scene(1, "Cùng một đáp án, viết cách nào cũng được")
    bank = ItemBank.load("MAE101")
    item = bank.get("MAE101-INT-010")
    print(f"Đề: {item.statement_vi}\n")
    for answer in ["(x**2+1)**4/8 + C", "(1/8)*(x^2+1)^4 + C", "x**8/8 + x**6/2 + 3*x**4/4 + x**2/2 + C"]:
        _, result = check("MAE101", item.item_id, answer, bank)
        print(f"  {'✔' if result.is_correct else '✘'} {answer}")
    print("\n  Dạng thứ ba là khai triển hết ra — khác hẳn về mặt chuỗi ký tự.")
    print("  Bộ chấm kiểm bằng ĐẠO HÀM NGƯỢC nên mọi dạng tương đương đều đúng.")

    _, wrong = check("MAE101", item.item_id, "(x**2+1)**4 + C", bank)
    print(f"\n  ✘ (x**2+1)**4 + C  → mã lỗi: {', '.join(wrong.candidate_error_codes) or '—'}")


def scene_cross_check() -> None:
    scene(2, "Kiểm chéo độc lập: hai cách tính khác hẳn nhau phải cho cùng kết quả")

    item = ItemBank.load("MAS291").get("MAS291-BIN-001")
    cross = P.cross_check(item)
    print(f"MAS291 — {item.statement_vi}")
    print(f"  giải tích  : {cross['analytic']:.6f}")
    print(f"  Monte Carlo: {cross['monte_carlo']:.6f} (400.000 lần mô phỏng)")
    print(f"  khớp nhau  : {'CÓ' if cross['agree'] else 'KHÔNG'}")

    item = ItemBank.load("MAD101").get("MAD101-COUNT-002")
    cross = D.cross_check(item)
    print(f"\nMAD101 — {item.statement_vi}")
    print(f"  công thức     : {cross['formula']}")
    print(f"  liệt kê vét cạn: {cross['brute_force']}")
    print(f"  khớp nhau     : {'CÓ' if cross['agree'] else 'KHÔNG'}")
    print("\n  Công thức viết sai thì hai con số lệch nhau ngay — và bài đó bị loại")
    print("  khỏi ngân hàng đề từ lúc sinh, không bao giờ đến tay sinh viên.")


def scene_step() -> None:
    scene(3, "Chỉ đúng bước sai đầu tiên, không chỉ nói 'sai rồi'")
    # Lấy thẳng một ca từ tập lỗi có nhãn, không tự bịa chuỗi bước: bịa tay rất dễ
    # ra một chuỗi VẪN tương đương hàng (đã dính đúng lỗi đó khi viết demo này),
    # và khi ấy demo hoá ra chứng minh điều ngược lại.
    row = _sample_step_error()
    if row is None:
        print("  (chưa có mẫu lỗi mức bước — chạy scripts/build_error_dataset.py MAI391)")
        return

    from src.core.itembank import ITEMS_DIR, load_items

    items = {i.item_id: i for i in load_items(ITEMS_DIR / f"{row['subject'].lower()}_generated.jsonl")}
    item = items[row["item_id"]]
    print(f"Đề: {item.statement_vi}")
    print(f"Đáp án cuối sinh viên nộp: {row['wrong_final_answer']} — ĐÚNG.")
    print("Nhưng trong lời giải có một phép biến đổi hàng tính sai:\n")
    for position, step in enumerate(row["wrong_steps"], start=1):
        print(f"     bước {position}: {step}")
    print()

    result = verifier_for(row["subject"]).verify(item, Submission(
        item_id=item.item_id, final_answer=row["wrong_final_answer"],
        steps=[str(step) for step in row["wrong_steps"]]))
    for step in result.step_results:
        mark = "✔" if step.ok else ("✘" if step.ok is False else "?")
        print(f"  {mark} bước {step.step}: {step.reason[:62]}")
    print(f"\n  → bước sai đầu tiên: {result.first_wrong_step} "
          f"(nhãn thật: {row['wrong_step_index']})")
    print(f"  → mã lỗi: {', '.join(result.candidate_error_codes) or '—'}")
    print("\n  Đáp án cuối vẫn đúng, nhưng lời giải có chỗ hỏng — chỉ chấm đáp án thì bỏ lọt.")


def _sample_step_error() -> dict | None:
    """Một bài làm có lỗi ở mức BƯỚC, lấy từ tập lỗi có nhãn."""
    import json

    from src.core.itembank import ERRORS_DIR

    path = ERRORS_DIR / "mai391_injected.jsonl"
    if not path.exists():
        return None
    for line in path.open(encoding="utf-8"):
        row = json.loads(line)
        if row.get("error_code") == "LA.ROWOP.INVALID" and row.get("wrong_steps"):
            return row
    return None


def scene_hints(use_llm: bool) -> None:
    scene(4, "Gợi ý cho dần, và guardrail chặn câu làm lộ đáp án")
    bank = ItemBank.load("MAE101")
    item, result = check("MAE101", "MAE101-INT-009", "sin(x)/cos(x)**2", bank)
    print(f"Đề: {item.statement_vi}")
    print("Bài làm sai: sin(x)/cos(x)**2\n")

    generator: HintGenerator
    if use_llm:
        from src.core.config import LLMConfig
        from src.llm.client import LLMClient
        from src.rag.hint_retriever import default_hint_retriever
        from src.tutor.llm_hints import LLMHintGenerator

        generator = LLMHintGenerator(LLMClient.from_config(LLMConfig()),
                                     load_course_error_codes("MAE101"), bank.skills,
                                     retriever=default_hint_retriever(bank.skills))
    else:
        generator = HintGenerator(error_codes=load_course_error_codes("MAE101"), skills=bank.skills)

    for level in (HintLevel.PROBE, HintLevel.CONCEPT, HintLevel.PITFALL, HintLevel.LOCATE):
        hint = generator.generate(item, result, level)
        print(f"  mức {int(level)} ({HintLevel(level).label_vi}) [{hint.source}]")
        print(f"     {hint.text[:150]}")

    leaky = f"Đáp án là {item.answer_text} nhé em."
    report = check_leak(leaky, item, HintLevel.PITFALL)
    print(f"\n  Thử một câu cố tình lộ đáp án: «{leaky}»")
    print(f"  → guardrail: {'CHẶN' if report.leaked else 'cho qua'} "
          f"(phát hiện «{report.offending_expression}»)")
    print("  Guardrail không tự phán xét: nó NỘP mảnh đó cho verifier và hỏi có đúng không.")


def scene_adaptive() -> None:
    scene(5, "Chọn bài theo mức thành thạo, không theo thứ tự cố định")
    bank = ItemBank.load("MAD101")
    items = [i for i in bank.items.values() if i.skills]
    tracker: BKTTracker = make_tracker(bank.skills)

    print("Người học A — mới bắt đầu, mọi kỹ năng đều yếu:")
    first = select_next(items, tracker, bank.skills)
    print(f"  → {first.item_id}: {first.statement_vi[:58]} (độ khó {first.difficulty})")

    for skill in bank.skills:
        tracker.set_mastery(skill, 0.9)
    tracker.set_mastery("MAD.GRAPH.EULER", 0.15)
    print("\nNgười học B — đã vững hầu hết, riêng phần đồ thị Euler còn yếu:")
    second = select_next(items, tracker, bank.skills)
    print(f"  → {second.item_id}: {second.statement_vi[:58]} (kỹ năng {', '.join(second.skills)})")


def scene_ask(use_llm: bool) -> None:
    scene(6, "Hỏi lý thuyết: có nguồn, và biết nói 'ngoài phạm vi'")
    from src.rag.ask import answer_question
    from src.rag.hint_retriever import load_index

    index = load_index()
    if index is None:
        print("  (chưa dựng kho RAG — chạy scripts/build_rag_index.py --dense)")
        return

    client = None
    if use_llm:
        from src.core.config import LLMConfig
        from src.llm.client import LLMClient

        client = LLMClient.from_config(LLMConfig())

    for question in ["Chu trình Euler là gì?", "Cách nấu phở bò ngon"]:
        answer = answer_question(question, index, client=client)
        print(f"\n  Hỏi: {question}")
        print(f"  {'[TRONG phạm vi]' if answer.in_scope else '[NGOÀI phạm vi]'} "
              f"{answer.text[:180].strip()}")
        if answer.sources:
            print(f"  nguồn: {answer.sources[0][:70]}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--llm", action="store_true", help="dùng model để diễn đạt gợi ý")
    parser.add_argument("--only", type=int, default=None, help="chạy một cảnh (1-6)")
    args = parser.parse_args()

    scenes = [
        scene_equivalence,
        scene_cross_check,
        scene_step,
        lambda: scene_hints(args.llm),
        scene_adaptive,
        lambda: scene_ask(args.llm),
    ]
    chosen = [scenes[args.only - 1]] if args.only else scenes
    for run in chosen:
        run()
    print(f"\n{'═' * WIDTH}\n Hết demo. Số liệu đầy đủ: docs/results.md\n{'═' * WIDTH}\n")


if __name__ == "__main__":
    main()
