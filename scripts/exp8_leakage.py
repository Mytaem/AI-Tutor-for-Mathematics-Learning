"""EXP-8 — gợi ý của LLM có làm lộ đáp án không, và guardrail giúp được bao nhiêu.

    python scripts/exp8_leakage.py                          # 6 ca/môn, qwen2.5:3b qua Ollama
    python scripts/exp8_leakage.py --per-subject 10 --model qwen2.5:7b-instruct

Mỗi ca là một bài làm sai lấy từ tập lỗi có nhãn (data/errors/*_injected.jsonl),
xin gợi ý ở các mức 0–3 (những mức KHÔNG được lộ đáp án), dưới 4 cấu hình:

    raw            prompt không có đáp án, không guardrail   → model tự lộ bao nhiêu?
    raw+answer     prompt CÓ đáp án, không guardrail         → giá trị của lớp phòng vệ 1
    full           prompt không có đáp án, guardrail + viết lại (hệ thống thật)
    full+answer    prompt có đáp án, guardrail + viết lại    → guardrail chịu tải được tới đâu

Lượt đầu của ``full`` trùng prompt với ``raw`` nên lấy ngay từ cache, không tốn
thêm lời gọi model; tương tự ``full+answer`` với ``raw+answer``.

Lưu ý khi đọc số: tỉ lệ lộ của ``full`` đo bằng CHÍNH guardrail nên bằng 0 theo
cấu tạo. Con số có nghĩa ở đó là số lần phải viết lại và tỉ lệ rơi về template.
Để có thước đo độc lập, script ghi thêm ``substring_leak`` (đáp án chuẩn xuất hiện
nguyên văn) và lưu toàn bộ câu sinh ra để chấm tay.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.config import ROOT, LLMConfig  # noqa: E402
from src.core.itembank import ERRORS_DIR, ItemBank, load_course_error_codes  # noqa: E402
from src.core.schema import Submission  # noqa: E402
from src.llm.client import LLMClient  # noqa: E402
from src.rag.hint_retriever import default_hint_retriever  # noqa: E402
from src.tutor.guardrail import check_leak  # noqa: E402
from src.tutor.hint_policy import HintLevel  # noqa: E402
from src.tutor.llm_hints import LLMHintGenerator  # noqa: E402
from src.verify.registry import verifier_for  # noqa: E402

SUBJECTS = ("MAE101", "MAI391", "MAS291", "MAD101")
CONDITIONS = {
    "raw": dict(use_guardrail=False, include_answer_in_prompt=False),
    "raw+answer": dict(use_guardrail=False, include_answer_in_prompt=True),
    "full": dict(use_guardrail=True, include_answer_in_prompt=False),
    "full+answer": dict(use_guardrail=True, include_answer_in_prompt=True),
}


def sample_cases(subject: str, bank: ItemBank, n: int, rng: random.Random) -> list[dict]:
    """Mỗi mã lỗi tối đa một ca, mỗi đề tối đa một ca — để mẫu nhỏ mà vẫn phủ rộng."""
    rows = [json.loads(line) for line in (ERRORS_DIR / f"{subject.lower()}_injected.jsonl").open(encoding="utf-8")]
    rows = [r for r in rows if r["item_id"] in bank.items]
    rng.shuffle(rows)
    picked, codes, items = [], set(), set()
    for row in rows:
        if row["error_code"] in codes or row["item_id"] in items:
            continue
        picked.append(row)
        codes.add(row["error_code"])
        items.add(row["item_id"])
        if len(picked) == n:
            break
    return picked


def memoised(retriever):
    cache: dict[tuple[str, int], list] = {}

    def wrapped(item, level):
        key = (item.item_id, int(level))
        if key not in cache:
            cache[key] = retriever(item, level)
        return cache[key]

    return wrapped


def steps_of(row: dict) -> list[str]:
    return [s["expr"] if isinstance(s, dict) else str(s) for s in row.get("wrong_steps") or []]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--per-subject", type=int, default=6)
    parser.add_argument("--levels", default="0,1,2,3")
    parser.add_argument("--model", default=None, help="đặt OLLAMA_MODEL, vd qwen2.5:7b-instruct")
    parser.add_argument("--max-rewrites", type=int, default=2)
    parser.add_argument("--seed", type=int, default=8)
    parser.add_argument("--no-rag", action="store_true", help="bỏ đoạn giáo trình khỏi prompt")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    if args.model:
        os.environ["OLLAMA_MODEL"] = args.model
    config = LLMConfig()
    client = LLMClient.from_config(config)
    health = client.health()
    print(f"Model: {config.cache_model} — backend đang sống: {health['active']}")
    if health["active"] in (None, "cache"):
        print("  (không có model sống: chỉ những câu đã có trong cache mới trả lời được)")

    levels = [HintLevel(int(x)) for x in args.levels.split(",")]
    rng = random.Random(args.seed)
    records: list[dict] = []
    started = time.perf_counter()

    for subject in SUBJECTS:
        bank = ItemBank.load(subject)
        verifier = verifier_for(subject)
        error_codes = load_course_error_codes(subject)
        # Một lần truy xuất dùng chung cho cả 4 cấu hình: prompt của chúng chỉ
        # khác ở chỗ có đáp án hay không, phần giáo trình thì giống hệt nhau.
        retriever = None if args.no_rag else memoised(default_hint_retriever(bank.skills))
        generators = {
            name: LLMHintGenerator(client, error_codes, bank.skills, retriever=retriever,
                                   max_rewrites=args.max_rewrites, seed=args.seed, **flags)
            for name, flags in CONDITIONS.items()
        }
        cases = sample_cases(subject, bank, args.per_subject, rng)
        print(f"\n{subject}: {len(cases)} ca × {len(levels)} mức × {len(CONDITIONS)} cấu hình")

        for row in cases:
            item = bank.get(row["item_id"])
            result = verifier.verify(item, Submission(
                item_id=item.item_id, final_answer=row["wrong_final_answer"], steps=steps_of(row)))
            for level in levels:
                for name, gen in generators.items():
                    hint = gen.generate(item, result, level)
                    trace = gen.last_trace
                    leaked = check_leak(hint.text, item, level)
                    answer = (item.answer_text or "").lower()
                    records.append({
                        "subject": subject, "item_id": item.item_id, "error_code": row["error_code"],
                        "level": int(level), "condition": name, "text": hint.text, "source": hint.source,
                        "leaked": leaked.leaked, "offending": leaked.offending_expression,
                        "substring_leak": len(answer) >= 4 and answer in hint.text.lower(),
                        "attempts": trace.attempts, "rejected": trace.rejected, "fell_back": trace.fell_back,
                        "llm_error": trace.llm_error, "backend": trace.backend, "latency_ms": trace.latency_ms,
                    })
                mark = "".join("L" if r["leaked"] else "." for r in records[-len(CONDITIONS):])
                print(f"  {item.item_id:<22} mức {int(level)}  [{mark}]  {time.perf_counter() - started:6.0f}s", flush=True)

    summary = summarise(records)
    print_table(summary)

    out = args.out or ROOT / "experiments" / "exp8" / f"{config.cache_model.replace(':', '_').replace('/', '_')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "model": config.cache_model, "per_subject": args.per_subject, "levels": args.levels,
        "max_rewrites": args.max_rewrites, "seed": args.seed, "rag": not args.no_rag, "summary": summary, "records": records,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nĐã ghi {len(records)} bản ghi vào {out}")


def summarise(records: list[dict]) -> dict:
    summary: dict[str, dict] = {}
    for name in CONDITIONS:
        rows = [r for r in records if r["condition"] == name]
        if not rows:
            continue
        live = [r["latency_ms"] for r in rows if r["backend"] not in ("", "cache")]
        summary[name] = {
            "n": len(rows),
            "leak_rate": sum(r["leaked"] for r in rows) / len(rows),
            "substring_leak_rate": sum(r["substring_leak"] for r in rows) / len(rows),
            "llm_rate": sum(r["source"] == "llm" for r in rows) / len(rows),
            "fallback_rate": sum(r["fell_back"] for r in rows) / len(rows),
            "llm_error_rate": sum(r["llm_error"] is not None for r in rows) / len(rows),
            "mean_attempts": statistics.mean(r["attempts"] for r in rows),
            "median_latency_ms": statistics.median(live) if live else None,
            "leak_rate_by_level": {
                lv: sum(r["leaked"] for r in rows if r["level"] == lv) / max(1, sum(r["level"] == lv for r in rows))
                for lv in sorted({r["level"] for r in rows})
            },
        }
    return summary


def print_table(summary: dict) -> None:
    print(f"\n{'cấu hình':<13}{'n':>5}{'lộ (guardrail)':>16}{'lộ (nguyên văn)':>17}"
          f"{'dùng LLM':>10}{'về template':>13}{'lượt TB':>9}{'trễ (s)':>9}")
    for name, s in summary.items():
        latency = f"{s['median_latency_ms'] / 1000:.1f}" if s["median_latency_ms"] else "—"
        print(f"{name:<13}{s['n']:>5}{s['leak_rate']:>16.1%}{s['substring_leak_rate']:>17.1%}"
              f"{s['llm_rate']:>10.1%}{s['fallback_rate']:>13.1%}{s['mean_attempts']:>9.2f}{latency:>9}")


if __name__ == "__main__":
    main()
