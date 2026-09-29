"""EXP-7b — bỏ RAG khỏi prompt sinh gợi ý thì gợi ý đổi thế nào?

    python scripts/exp8_leakage.py --per-subject 5 --out experiments/exp7/rag_on.json
    python scripts/exp8_leakage.py --per-subject 5 --no-rag --out experiments/exp7/rag_off.json
    python scripts/exp7_rag_ablation.py          # so hai file trên

**Nói trước cái script này KHÔNG đo được:** nó không đo được gợi ý nào hay hơn về
mặt sư phạm. Việc đó cần người chấm (phiếu ở `scripts/build_hint_rating_sheet.py`),
và không nên giả vờ đo bằng máy.

Cái nó đo được, và đều là câu hỏi thật:

    lộ đáp án      đưa thêm đoạn giáo trình vào prompt có làm model lộ nhiều hơn?
    về template    RAG có làm guardrail chặn nhiều hơn, tức là gợi ý khó dùng hơn?
    độ dài         gợi ý có dài lê thê ra không
    bám giáo trình gợi ý có thật sự dùng thuật ngữ trong đoạn được cung cấp không
    độ trễ         cái giá phải trả mỗi lượt

Chỉ số "bám giáo trình" là một phép đếm thô: tỉ lệ gợi ý chứa ít nhất một thuật
ngữ chuyên môn (từ dài, viết hoa hoặc ký hiệu toán) xuất hiện trong đoạn trích.
Nó không nói gợi ý đúng hay sai — chỉ nói model có ngó tới tài liệu hay không.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.config import ROOT  # noqa: E402

EXP7 = ROOT / "experiments" / "exp7"
#: Từ được coi là "thuật ngữ": đủ dài để không phải từ nối, hoặc có ký hiệu toán.
TERM = re.compile(r"[A-Za-zÀ-ỹ]{6,}|[∫∑√λ∂]")


def load(path: Path) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def grounding_rate(records: list[dict]) -> float:
    """Tỉ lệ gợi ý có ít nhất một thuật ngữ trùng với đoạn giáo trình được cấp.

    Đoạn trích không nằm trong bản ghi thí nghiệm nên phải truy xuất lại. Làm
    được vì bộ truy xuất tất định: cùng (đề, mức) luôn ra cùng đoạn.
    """
    from src.core.itembank import ITEMS_DIR, ItemBank, load_items
    from src.rag.hint_retriever import default_hint_retriever
    from src.tutor.hint_policy import HintLevel

    banks: dict[str, ItemBank] = {}
    items: dict[str, object] = {}
    retrievers: dict[str, object] = {}
    checked = grounded = 0

    for record in records:
        subject = record["subject"]
        if subject not in banks:
            banks[subject] = ItemBank.load(subject)
            items.update({i.item_id: i for i in banks[subject].items.values()})
            generated = ITEMS_DIR / f"{subject.lower()}_generated.jsonl"
            if generated.exists():
                items.update({i.item_id: i for i in load_items(generated)})
            retrievers[subject] = default_hint_retriever(banks[subject].skills)

        item = items.get(record["item_id"])
        if item is None:
            continue
        passages = retrievers[subject](item, HintLevel(record["level"]))
        if not passages:
            continue                      # mức 0 và 3 không truy xuất, bỏ qua
        checked += 1
        terms = {term.lower() for text, _ in passages for term in TERM.findall(text)}
        if terms & {term.lower() for term in TERM.findall(record["text"])}:
            grounded += 1
    return grounded / checked if checked else 0.0


def summarise(data: dict, condition: str = "full") -> dict:
    records = [r for r in data["records"] if r["condition"] == condition]
    live = [r["latency_ms"] for r in records if r["backend"] not in ("", "cache")]
    return {
        "n": len(records),
        "leak_rate": sum(r["leaked"] for r in records) / len(records),
        "fallback_rate": sum(r["fell_back"] for r in records) / len(records),
        "mean_attempts": statistics.mean(r["attempts"] for r in records),
        "mean_length": statistics.mean(len(r["text"]) for r in records),
        "grounding": grounding_rate(records),
        "median_latency_ms": statistics.median(live) if live else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--on", type=Path, default=EXP7 / "rag_on.json")
    parser.add_argument("--off", type=Path, default=EXP7 / "rag_off.json")
    args = parser.parse_args()

    on, off = load(args.on), load(args.off)
    missing = [str(path) for path, data in ((args.on, on), (args.off, off)) if data is None]
    if missing:
        print("Thiếu dữ liệu: " + ", ".join(missing))
        print("Chạy hai lệnh exp8_leakage ghi ở đầu file này trước.")
        raise SystemExit(1)

    rows = {"có RAG": summarise(on), "không RAG": summarise(off)}
    print(f"\nEXP-7b — bỏ RAG khỏi prompt gợi ý ({on['model']}, {rows['có RAG']['n']} lượt mỗi bên)\n")
    print(f"{'cấu hình':<12}{'lộ đáp án':>11}{'về template':>13}{'lượt TB':>9}"
          f"{'độ dài':>9}{'bám giáo trình':>16}{'trễ (s)':>9}")
    for name, values in rows.items():
        latency = f"{values['median_latency_ms'] / 1000:.1f}" if values["median_latency_ms"] else "—"
        grounding = f"{values['grounding']:.0%}" if values["grounding"] else "—"
        print(f"{name:<12}{values['leak_rate']:>10.1%}{values['fallback_rate']:>13.1%}"
              f"{values['mean_attempts']:>9.2f}{values['mean_length']:>9.0f}"
              f"{grounding:>16}{latency:>9}")

    print("\n  Chất lượng sư phạm KHÔNG đo ở đây — cần phiếu chấm tay "
          "(scripts/build_hint_rating_sheet.py).")

    out = EXP7 / "rag_ablation.json"
    out.write_text(json.dumps({"model": on["model"], "summary": rows}, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print(f"\nĐã ghi {out}\n")


if __name__ == "__main__":
    main()
