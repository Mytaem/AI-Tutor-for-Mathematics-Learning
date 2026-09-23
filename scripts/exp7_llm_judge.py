"""EXP-7a — thay bộ chấm ký hiệu bằng mô hình ngôn ngữ thì sai bao nhiêu?

    python scripts/exp7_llm_judge.py --pairs 60
    python scripts/exp7_llm_judge.py --pairs 60 --model qwen2.5:7b-instruct

Đây là ablation quan trọng nhất của cả đồ án: bỏ tầng kiểm chứng ký hiệu đi thì
chuyện gì xảy ra. Bộ dữ liệu cân bằng: một nửa là ĐÁP ÁN ĐÚNG (lấy từ ngân hàng
đề), một nửa là bài làm SAI (lấy từ tập lỗi có nhãn). Cả hai đều có nhãn chắc
chắn, nên đo được thẳng.

Hai loại sai KHÔNG tương đương nhau về hậu quả, nên báo cáo tách riêng:

- **Báo đúng cho bài sai** (false accept) — nguy hiểm nhất: sinh viên tưởng mình
  làm đúng và mang lỗi đó đi tiếp. Bộ chấm ký hiệu không bao giờ mắc lỗi này trừ
  khi chính nó có lỗi.
- **Báo sai cho bài đúng** (false reject) — khó chịu và làm mất lòng tin, nhưng
  còn sửa được bằng cách cho làm lại.

Bộ chấm ký hiệu được chạy trên đúng bộ dữ liệu đó để có con số so sánh.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.config import ROOT, LLMConfig  # noqa: E402
from src.core.itembank import ERRORS_DIR, ITEMS_DIR, ItemBank, load_items  # noqa: E402
from src.core.schema import Submission  # noqa: E402
from src.llm.client import LLMClient, LLMError  # noqa: E402
from src.verify.registry import verifier_for  # noqa: E402

SUBJECTS = ("MAE101", "MAI391", "MAS291", "MAD101")

JUDGE_SYSTEM = (
    "Bạn là giám khảo chấm toán. Đọc đề bài và bài làm của sinh viên, quyết định bài "
    "làm ĐÚNG hay SAI. Chấp nhận mọi cách viết tương đương về mặt toán học. "
    "Trả lời duy nhất một từ: ĐÚNG hoặc SAI."
)


def build_pairs(count_per_subject: int, rng: random.Random) -> list[dict]:
    """Bộ dữ liệu cân bằng: một nửa đúng, một nửa sai, nhãn chắc chắn."""
    pairs: list[dict] = []
    for subject in SUBJECTS:
        bank = ItemBank.load(subject)
        items = dict(bank.items)
        generated = ITEMS_DIR / f"{subject.lower()}_generated.jsonl"
        if generated.exists():
            items.update({i.item_id: i for i in load_items(generated)})

        wrong_rows = [json.loads(line) for line
                      in (ERRORS_DIR / f"{subject.lower()}_injected.jsonl").open(encoding="utf-8")]
        wrong_rows = [row for row in wrong_rows if row["item_id"] in items]
        rng.shuffle(wrong_rows)
        for row in wrong_rows[: count_per_subject // 2]:
            pairs.append({"subject": subject, "item_id": row["item_id"],
                          "answer": row["wrong_final_answer"], "truth": False,
                          "error_code": row["error_code"]})

        chosen = rng.sample(sorted(items), min(count_per_subject - count_per_subject // 2, len(items)))
        for item_id in chosen:
            pairs.append({"subject": subject, "item_id": item_id,
                          "answer": items[item_id].answer_text, "truth": True, "error_code": None})

    rng.shuffle(pairs)
    return pairs


def judge_with_llm(client: LLMClient, statement: str, answer: str) -> bool | None:
    messages = [
        {"role": "system", "content": JUDGE_SYSTEM},
        {"role": "user", "content": f"ĐỀ BÀI: {statement}\nBÀI LÀM: {answer}\n\nĐÚNG hay SAI?"},
    ]
    try:
        text = client.chat(messages, temperature=0.0, max_tokens=8).text.strip().upper()
    except LLMError:
        return None
    if "ĐÚNG" in text or "DUNG" in text:
        return True
    if "SAI" in text:
        return False
    return None


def rates(results: list[tuple[bool, bool | None]]) -> dict:
    """Độ chính xác, tỉ lệ báo đúng cho bài sai, tỉ lệ báo sai cho bài đúng."""
    total = len(results)
    correct = sum(1 for truth, guess in results if guess is truth)
    wrong_items = [(t, g) for t, g in results if t is False]
    right_items = [(t, g) for t, g in results if t is True]
    return {
        "n": total,
        "accuracy": correct / total if total else 0.0,
        "false_accept": (sum(1 for _, g in wrong_items if g is True) / len(wrong_items)
                         if wrong_items else 0.0),
        "false_reject": (sum(1 for _, g in right_items if g is False) / len(right_items)
                         if right_items else 0.0),
        "no_answer": sum(1 for _, g in results if g is None) / total if total else 0.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pairs", type=int, default=40, help="số cặp MỖI MÔN (một nửa đúng, một nửa sai)")
    parser.add_argument("--model", default=None)
    parser.add_argument("--seed", type=int, default=5)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    if args.model:
        import os
        os.environ["OLLAMA_MODEL"] = args.model

    config = LLMConfig()
    client = LLMClient.from_config(config)
    rng = random.Random(args.seed)
    pairs = build_pairs(args.pairs, rng)
    print(f"\nEXP-7a — {config.cache_model}: {len(pairs)} cặp "
          f"({sum(1 for p in pairs if p['truth'])} đúng / {sum(1 for p in pairs if not p['truth'])} sai)\n")

    banks = {subject: ItemBank.load(subject) for subject in SUBJECTS}
    generated = {}
    for subject in SUBJECTS:
        path = ITEMS_DIR / f"{subject.lower()}_generated.jsonl"
        if path.exists():
            generated.update({i.item_id: i for i in load_items(path)})

    def item_of(pair):
        return generated.get(pair["item_id"]) or banks[pair["subject"]].get(pair["item_id"])

    llm_results: list[tuple[bool, bool | None]] = []
    symbolic_results: list[tuple[bool, bool | None]] = []
    records = []
    started = time.perf_counter()

    for position, pair in enumerate(pairs, start=1):
        item = item_of(pair)
        guess = judge_with_llm(client, item.statement_vi, pair["answer"])
        llm_results.append((pair["truth"], guess))

        result = verifier_for(pair["subject"]).verify(
            item, Submission(item_id=item.item_id, final_answer=pair["answer"]))
        symbolic_results.append((pair["truth"], result.final_answer_correct))

        records.append({**pair, "llm": guess, "symbolic": result.final_answer_correct})
        if position % 20 == 0:
            print(f"  {position}/{len(pairs)} ({time.perf_counter() - started:.0f}s)", flush=True)

    llm = rates(llm_results)
    symbolic = rates(symbolic_results)

    print(f"\n{'bộ chấm':<22}{'chính xác':>11}{'báo đúng cho bài SAI':>24}{'báo sai cho bài ĐÚNG':>24}")
    print(f"{'mô hình ngôn ngữ':<22}{llm['accuracy']:>10.1%}{llm['false_accept']:>23.1%}"
          f"{llm['false_reject']:>23.1%}")
    print(f"{'kiểm chứng ký hiệu':<22}{symbolic['accuracy']:>10.1%}{symbolic['false_accept']:>23.1%}"
          f"{symbolic['false_reject']:>23.1%}")
    if llm["no_answer"]:
        print(f"\n  (mô hình không ra được ĐÚNG/SAI ở {llm['no_answer']:.1%} số lượt)")

    out = args.out or ROOT / "experiments" / "exp7" / f"judge_{config.cache_model.replace(':', '_')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"model": config.cache_model, "pairs": len(pairs),
                               "llm": llm, "symbolic": symbolic, "records": records},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nĐã ghi {out}\n")


if __name__ == "__main__":
    main()
