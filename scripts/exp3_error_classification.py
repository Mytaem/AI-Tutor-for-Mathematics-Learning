"""EXP-3 — phân loại mã lỗi: prompting so với fine-tune.

    python scripts/exp3_error_classification.py --limit 100            # zero-shot
    python scripts/exp3_error_classification.py --shots 4 --limit 100  # few-shot
    python scripts/exp3_error_classification.py --model qwen2.5:7b-instruct

Đo trên ``data/sft/test.jsonl`` (dựng bằng ``scripts/build_sft_dataset.py``).

Chỉ số chính là **macro-F1**, không phải accuracy: dữ liệu lệch nặng, đoán vài mã
phổ biến là đã có accuracy khá cao trong khi phần lớn mã lỗi không bao giờ được
nhận ra. Macro-F1 tính trung bình F1 của từng mã nên mã hiếm có trọng số ngang mã
phổ biến.

Ngoài ra in thêm ba thứ hay bị bỏ qua:

- tỉ lệ mô hình trả về mã KHÔNG tồn tại (bịa mã) — prompting rất hay dính;
- tỉ lệ đúng TẦNG lỗi (E-CONCEPT, E-PROCEDURE...) dù sai mã cụ thể: sai mã nhưng
  đúng tầng vẫn còn dùng được để chọn câu gợi ý;
- độ trễ trung bình mỗi mẫu, để biết có gắn vào đường phục vụ thật được không.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.config import ROOT, LLMConfig  # noqa: E402
from src.core.itembank import load_course_error_codes  # noqa: E402
from src.data_gen.sft_dataset import Example, load_jsonl  # noqa: E402
from src.llm.client import LLMClient, LLMError  # noqa: E402

SFT_DIR = ROOT / "data" / "sft"
CODE_PATTERN = re.compile(r"\b[A-Z]{2,4}(?:\.[A-Z0-9_]+)+\b")


def extract_code(text: str, valid: set[str]) -> str | None:
    """Lấy mã lỗi từ câu trả lời tự do của mô hình.

    Model nhỏ hay trả lời dài dòng ("Mã lỗi là MAE.INT.NOCONST vì...") nên phải
    bóc mã ra; chỉ nhận mã có thật trong bảng phân loại, mã bịa coi như trả lời sai.
    """
    for candidate in CODE_PATTERN.findall(text.upper()):
        if candidate in valid:
            return candidate
    return None


def macro_f1(pairs: list[tuple[str, str | None]]) -> tuple[float, dict[str, float]]:
    """Macro-F1 tự cài — trung bình F1 trên các lớp CÓ MẶT trong nhãn thật."""
    true_positive: dict[str, int] = defaultdict(int)
    predicted: dict[str, int] = defaultdict(int)
    actual: dict[str, int] = defaultdict(int)

    for truth, guess in pairs:
        actual[truth] += 1
        if guess is not None:
            predicted[guess] += 1
            if guess == truth:
                true_positive[truth] += 1

    per_class: dict[str, float] = {}
    for code in actual:
        precision = true_positive[code] / predicted[code] if predicted[code] else 0.0
        recall = true_positive[code] / actual[code]
        per_class[code] = (2 * precision * recall / (precision + recall)
                           if precision + recall else 0.0)
    return (sum(per_class.values()) / len(per_class) if per_class else 0.0), per_class


def few_shot_prefix(train: list[Example], shots: int, seed: int) -> str:
    """Vài ví dụ mẫu lấy từ train, mỗi ví dụ một mã lỗi khác nhau."""
    if shots <= 0:
        return ""
    rng = random.Random(seed)
    by_code: dict[str, list[Example]] = defaultdict(list)
    for example in train:
        by_code[example.error_code].append(example)
    codes = rng.sample(sorted(by_code), min(shots, len(by_code)))

    blocks = []
    for code in codes:
        sample = rng.choice(by_code[code])
        # Chỉ lấy phần đề + bài làm, bỏ danh sách mã (dài) khỏi ví dụ mẫu.
        body = sample.prompt.split("DANH SÁCH MÃ LỖI:")[0].split("MÔN:", 1)[-1].strip()
        blocks.append(f"MÔN: {body}\nMÃ LỖI: {code}")
    return "VÍ DỤ MẪU:\n\n" + "\n\n".join(blocks) + "\n\n---\n\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=100, help="số mẫu test đem đo")
    parser.add_argument("--shots", type=int, default=0, help="số ví dụ mẫu (0 = zero-shot)")
    parser.add_argument("--model", default=None, help="đặt OLLAMA_MODEL")
    parser.add_argument("--seed", type=int, default=3)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    if args.model:
        import os
        os.environ["OLLAMA_MODEL"] = args.model

    config = LLMConfig()
    client = LLMClient.from_config(config)
    print(f"Model: {config.cache_model} — backend: {client.health()['active']}")

    test = load_jsonl(SFT_DIR / "test.jsonl")
    train = load_jsonl(SFT_DIR / "train.jsonl")
    rng = random.Random(args.seed)
    rng.shuffle(test)
    test = test[: args.limit]

    codes = {subject: load_course_error_codes(subject)
             for subject in ("MAE101", "MAI391", "MAS291", "MAD101")}
    valid = {code for table in codes.values() for code in table}
    tiers = {code: entry.tier.value if hasattr(entry.tier, "value") else str(entry.tier)
             for table in codes.values() for code, entry in table.items()}

    prefix = few_shot_prefix(train, args.shots, args.seed)
    pairs: list[tuple[str, str | None]] = []
    records = []
    started = time.perf_counter()

    for position, example in enumerate(test, start=1):
        messages = [{"role": "user", "content": prefix + example.prompt}]
        try:
            reply = client.chat(messages, temperature=0.0, max_tokens=24)
            text = reply.text.strip()
        except LLMError as exc:
            text = f"<lỗi: {exc}>"
        guess = extract_code(text, valid)
        pairs.append((example.error_code, guess))
        records.append({"item_id": example.item_id, "truth": example.error_code,
                        "guess": guess, "raw": text[:120]})
        if position % 20 == 0:
            correct = sum(1 for t, g in pairs if t == g)
            print(f"  {position}/{len(test)} — đúng {correct}/{position} "
                  f"({time.perf_counter() - started:.0f}s)", flush=True)

    score, per_class = macro_f1(pairs)
    accuracy = sum(1 for truth, guess in pairs if truth == guess) / len(pairs)
    invalid = sum(1 for _, guess in pairs if guess is None) / len(pairs)
    tier_hit = sum(1 for truth, guess in pairs
                   if guess is not None and tiers.get(guess) == tiers.get(truth)) / len(pairs)
    elapsed = time.perf_counter() - started

    label = f"{'few-shot ' + str(args.shots) if args.shots else 'zero-shot'}"
    print(f"\n{label} — {config.cache_model}, {len(pairs)} mẫu")
    print(f"  macro-F1        {score:.3f}")
    print(f"  accuracy        {accuracy:.3f}")
    print(f"  đúng tầng lỗi   {tier_hit:.3f}")
    print(f"  không ra mã hợp lệ {invalid:.1%}")
    print(f"  trễ trung bình  {elapsed / len(pairs):.1f}s/mẫu")

    best = sorted(per_class.items(), key=lambda kv: -kv[1])[:5]
    print(f"  mã nhận ra tốt nhất: {', '.join(f'{c} {v:.2f}' for c, v in best if v > 0) or '—'}")

    out = args.out or ROOT / "experiments" / "exp3" / (
        f"{config.cache_model.replace(':', '_')}_{'few' + str(args.shots) if args.shots else 'zero'}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "model": config.cache_model, "shots": args.shots, "n": len(pairs),
        "macro_f1": score, "accuracy": accuracy, "tier_accuracy": tier_hit,
        "invalid_rate": invalid, "seconds_per_sample": elapsed / len(pairs),
        "per_class_f1": per_class, "records": records,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nĐã ghi {out}\n")


if __name__ == "__main__":
    main()
