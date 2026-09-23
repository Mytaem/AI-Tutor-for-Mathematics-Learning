"""EXP-1 — mô hình ngôn ngữ tự giải toán được bao nhiêu phần trăm.

    python scripts/exp1_solving.py --per-subject 15
    python scripts/exp1_solving.py --mode cot --per-subject 15
    python scripts/exp1_solving.py --mode self_consistency --samples 3

Ba cấu hình:

    direct            hỏi thẳng, bắt trả lời ngay đáp án
    cot               cho phép nghĩ ra nháp rồi mới chốt đáp án
    self_consistency  lấy k câu trả lời ở nhiệt độ cao, chọn đáp án đa số

**Ai chấm:** verifier của môn, chấm y hệt cách chấm bài sinh viên — chấp nhận mọi
dạng viết tương đương. Đây là lý do thí nghiệm này có nghĩa: nếu lấy chính mô hình
ngôn ngữ ra chấm thì con số chỉ đo được sự tự tin của nó.

Con số cần cho báo cáo là **khoảng cách**: mô hình tự giải đúng bao nhiêu, so với
việc hệ thống dùng nó để DIỄN ĐẠT còn phần tính toán giao cho SymPy. Khoảng cách đó
chính là lý do tồn tại của cả tầng kiểm chứng.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.config import ROOT, LLMConfig  # noqa: E402
from src.core.itembank import ITEMS_DIR, ItemBank, load_items  # noqa: E402
from src.core.schema import Submission  # noqa: E402
from src.llm.client import LLMClient, LLMError  # noqa: E402
from src.verify.registry import verifier_for  # noqa: E402

SUBJECTS = ("MAE101", "MAI391", "MAS291", "MAD101")

SYSTEM = (
    "Bạn là một máy giải toán. Trả lời NGẮN GỌN, chỉ đưa đáp án cuối cùng, "
    "không giải thích, không viết câu dẫn."
)
SYSTEM_COT = (
    "Bạn là một máy giải toán. Hãy suy luận từng bước ngắn gọn, "
    "rồi kết thúc bằng đúng một dòng có dạng 'ĐÁP ÁN: <đáp án>'."
)

FORMAT_HINT = {
    "expression": "một biểu thức",
    "antiderivative": "một nguyên hàm, nhớ hằng số C",
    "number": "một con số hoặc phân số",
    "set": "các phần tử cách nhau bởi dấu phẩy",
    "matrix": "ma trận kiểu [[a, b], [c, d]] hoặc vector [a, b]",
    "eigenvector": "một vector kiểu [a, b]",
    "linear_system": "bộ nghiệm kiểu [a, b]",
    "boolean": "có hoặc không",
    "text": "một câu trả lời ngắn",
}

ANSWER_LINE = re.compile(r"ĐÁP ÁN\s*[:：]\s*(.+)", re.IGNORECASE)


def extract_answer(text: str) -> str:
    """Bóc đáp án cuối khỏi câu trả lời.

    Model nhỏ rất hay viết thừa dù prompt cấm; lấy dòng 'ĐÁP ÁN:' nếu có, không
    thì lấy dòng cuối cùng có nội dung.
    """
    match = ANSWER_LINE.search(text)
    if match:
        return match.group(1).strip().strip("`$ ")
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    return lines[-1].strip("`$ ") if lines else ""


def sample_items(subject: str, count: int, rng: random.Random):
    """Lấy đề CHÉP TAY trước (chất lượng cao), thiếu thì bù bằng đề sinh tự động."""
    bank = ItemBank.load(subject)
    items = list(bank.items.values())
    rng.shuffle(items)
    if len(items) < count:
        generated = ITEMS_DIR / f"{subject.lower()}_generated.jsonl"
        if generated.exists():
            extra = load_items(generated)
            rng.shuffle(extra)
            items += extra
    return items[:count]


def ask(client: LLMClient, item, mode: str, samples: int, temperature: float) -> list[str]:
    hint = FORMAT_HINT.get(item.answer_type.value, "đáp án")
    question = f"{item.statement_vi}\n\nTrả lời bằng {hint}."
    system = SYSTEM_COT if mode != "direct" else SYSTEM
    messages = [{"role": "system", "content": system}, {"role": "user", "content": question}]

    replies: list[str] = []
    for index in range(samples):
        try:
            reply = client.chat(messages, temperature=temperature if index else 0.0, max_tokens=400)
            replies.append(extract_answer(reply.text))
        except LLMError:
            replies.append("")
    return replies


def majority(answers: list[str]) -> str:
    """Đáp án được nhắc lại nhiều nhất — so theo chuỗi đã chuẩn hoá khoảng trắng."""
    cleaned = [" ".join(a.split()) for a in answers if a.strip()]
    if not cleaned:
        return ""
    return Counter(cleaned).most_common(1)[0][0]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--per-subject", type=int, default=15)
    parser.add_argument("--mode", choices=("direct", "cot", "self_consistency"), default="direct")
    parser.add_argument("--samples", type=int, default=3, help="chỉ dùng cho self_consistency")
    parser.add_argument("--model", default=None)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    if args.model:
        import os
        os.environ["OLLAMA_MODEL"] = args.model

    config = LLMConfig()
    client = LLMClient.from_config(config)
    print(f"\nEXP-1 — {config.cache_model}, chế độ {args.mode}, backend {client.health()['active']}\n")

    rng = random.Random(args.seed)
    samples = args.samples if args.mode == "self_consistency" else 1
    records: list[dict] = []
    by_subject: dict[str, list[bool]] = defaultdict(list)
    started = time.perf_counter()

    for subject in SUBJECTS:
        verifier = verifier_for(subject)
        for item in sample_items(subject, args.per_subject, rng):
            answers = ask(client, item, args.mode, samples, temperature=0.8)
            final = majority(answers) if samples > 1 else answers[0]
            try:
                result = verifier.verify(item, Submission(item_id=item.item_id, final_answer=final))
                correct = result.final_answer_correct is True
            except Exception:
                correct = False
            by_subject[subject].append(correct)
            records.append({"item_id": item.item_id, "subject": subject, "correct": correct,
                            "model_answer": final[:120], "true_answer": item.answer_text})
        done = by_subject[subject]
        print(f"  {subject}: {sum(done)}/{len(done)} đúng  ({time.perf_counter() - started:.0f}s)",
              flush=True)

    total = [ok for values in by_subject.values() for ok in values]
    accuracy = sum(total) / len(total)
    summary = {subject: sum(values) / len(values) for subject, values in by_subject.items()}

    print(f"\n{'môn':<10}{'đúng':>10}")
    for subject, value in summary.items():
        print(f"{subject:<10}{value:>9.1%}")
    print(f"{'TỔNG':<10}{accuracy:>9.1%}  ({sum(total)}/{len(total)} bài, "
          f"{(time.perf_counter() - started) / len(total):.1f}s/bài)")

    out = args.out or ROOT / "experiments" / "exp1" / f"{config.cache_model.replace(':', '_')}_{args.mode}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "model": config.cache_model, "mode": args.mode, "samples": samples,
        "per_subject": args.per_subject, "accuracy": accuracy, "by_subject": summary,
        "records": records,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nĐã ghi {out}\n")


if __name__ == "__main__":
    main()
