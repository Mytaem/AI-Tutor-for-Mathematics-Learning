"""Xuất phiếu chấm tay chất lượng gợi ý (L2) — chạy: python scripts/build_hint_rating_sheet.py

    python scripts/build_hint_rating_sheet.py --per-subject 10
    python scripts/build_hint_rating_sheet.py --llm           # gợi ý do model sinh
    python scripts/build_hint_rating_sheet.py --kappa data/eval/hint_ratings_filled.csv

Vì sao chấm tay chứ không để LLM chấm: giám khảo ở đây phải phán xét về SƯ PHẠM
("gợi ý này có dẫn dắt hay làm hộ?"), mà model duy nhất chạy được ở máy lại cùng
họ với model sinh ra gợi ý — nó chấm chính nó. Ba người chấm độc lập rồi báo cáo
Cohen's kappa giữa từng cặp mới là bằng chứng dùng được.

Phiếu ra dạng CSV mở bằng Excel được, mỗi dòng một gợi ý, bốn cột điểm 1–5:

    dung_toan      gợi ý có nói gì sai về toán không
    khong_lo       có giữ được đáp án không (mức < 4 mà lộ là 1 điểm)
    su_pham        có dẫn dắt để người học tự nghĩ không, hay làm hộ
    tieng_viet     câu tiếng Việt có tự nhiên, đúng vai thầy–trò không

Cột ``ghi_chu`` để người chấm viết lý do khi cho điểm thấp — phần này vào mục phân
tích lỗi của báo cáo.
"""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.config import ROOT, LLMConfig  # noqa: E402
from src.core.itembank import ERRORS_DIR, ITEMS_DIR, ItemBank, load_course_error_codes, load_items  # noqa: E402
from src.core.schema import Submission  # noqa: E402
from src.tutor.hint_policy import HintLevel  # noqa: E402
from src.tutor.hints import HintGenerator  # noqa: E402
from src.verify.registry import verifier_for  # noqa: E402

SUBJECTS = ("MAE101", "MAI391", "MAS291", "MAD101")
LEVELS = (HintLevel.CONCEPT, HintLevel.PITFALL, HintLevel.LOCATE, HintLevel.CORRECT)
OUTPUT = ROOT / "data" / "eval"
COLUMNS = ["stt", "mon", "item_id", "de_bai", "bai_lam_sai", "muc", "nguon", "goi_y",
           "dung_toan", "khong_lo", "su_pham", "tieng_viet", "ghi_chu"]


def wrong_attempts(subject: str, count: int, rng: random.Random) -> list[dict]:
    rows = [json.loads(line) for line
            in (ERRORS_DIR / f"{subject.lower()}_injected.jsonl").open(encoding="utf-8")]
    rng.shuffle(rows)
    seen: set[str] = set()
    chosen = []
    for row in rows:                      # mỗi mã lỗi nhiều nhất một bài, cho phủ rộng
        if row["error_code"] in seen:
            continue
        seen.add(row["error_code"])
        chosen.append(row)
        if len(chosen) == count:
            break
    return chosen


def build_rows(per_subject: int, use_llm: bool, seed: int) -> list[dict]:
    rng = random.Random(seed)
    rows: list[dict] = []

    for subject in SUBJECTS:
        bank = ItemBank.load(subject)
        items = dict(bank.items)
        generated = ITEMS_DIR / f"{subject.lower()}_generated.jsonl"
        if generated.exists():
            items.update({i.item_id: i for i in load_items(generated)})

        codes = load_course_error_codes(subject)
        if use_llm:
            from src.llm.client import LLMClient
            from src.rag.hint_retriever import default_hint_retriever
            from src.tutor.llm_hints import LLMHintGenerator

            generator = LLMHintGenerator(LLMClient.from_config(LLMConfig()), codes, bank.skills,
                                         retriever=default_hint_retriever(bank.skills))
        else:
            generator = HintGenerator(error_codes=codes, skills=bank.skills)

        verifier = verifier_for(subject)
        for attempt in wrong_attempts(subject, per_subject, rng):
            item = items.get(attempt["item_id"])
            if item is None:
                continue
            result = verifier.verify(item, Submission(
                item_id=item.item_id, final_answer=attempt["wrong_final_answer"]))
            for level in LEVELS:
                hint = generator.generate(item, result, level)
                rows.append({
                    "mon": subject, "item_id": item.item_id,
                    "de_bai": item.statement_vi,
                    "bai_lam_sai": attempt["wrong_final_answer"],
                    "muc": int(level), "nguon": hint.source, "goi_y": hint.text,
                })
    return rows


def write_sheet(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:   # BOM để Excel đọc đúng
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        for position, row in enumerate(rows, start=1):
            writer.writerow({"stt": position, **row})


# --------------------------------------------------------------------------
# Độ đồng thuận giữa người chấm
# --------------------------------------------------------------------------

def cohen_kappa(first: list[int], second: list[int]) -> float:
    """Kappa cho thang điểm rời rạc.

    Dùng kappa chứ không dùng "tỉ lệ trùng nhau" vì hai người cùng cho điểm 4 cho
    gần hết mọi câu thì tỉ lệ trùng rất cao mà chẳng nói lên điều gì; kappa trừ
    đi phần trùng do ngẫu nhiên.
    """
    pairs = [(a, b) for a, b in zip(first, second) if a and b]
    if not pairs:
        return 0.0
    labels = sorted({value for pair in pairs for value in pair})
    observed = sum(1 for a, b in pairs if a == b) / len(pairs)
    expected = sum(
        (sum(1 for a, _ in pairs if a == label) / len(pairs))
        * (sum(1 for _, b in pairs if b == label) / len(pairs))
        for label in labels
    )
    if expected >= 1.0:
        # Cả hai người chỉ dùng đúng một mức điểm: trùng nhau 100% nhưng kappa
        # KHÔNG xác định (mẫu số bằng 0). Trả 1.0 ở đây là tự khen — báo cáo
        # phải nói rõ thang điểm bị dồn về một mức.
        return float("nan")
    return (observed - expected) / (1 - expected)


def report_kappa(path: Path) -> None:
    """Đọc phiếu ĐÃ CHẤM (mỗi người một file hoặc một cột hậu tố _1, _2, _3)."""
    rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
    axes = ["dung_toan", "khong_lo", "su_pham", "tieng_viet"]
    raters = sorted({key.rsplit("_", 1)[-1] for row in rows for key in row
                     if key.startswith("dung_toan_")})
    if not raters:
        print("Phiếu chưa có cột dạng 'dung_toan_1', 'dung_toan_2'... — chưa tính kappa được.")
        return

    print(f"\n{len(rows)} gợi ý, {len(raters)} người chấm\n")
    for axis in axes:
        scores = {
            rater: [int(row.get(f"{axis}_{rater}") or 0) for row in rows] for rater in raters
        }
        values = [v for rater in raters for v in scores[rater] if v]
        mean = sum(values) / len(values) if values else 0.0
        kappas = [cohen_kappa(scores[a], scores[b]) for a, b in itertools.combinations(raters, 2)]
        shown = ", ".join("—" if k != k else f"{k:.2f}" for k in kappas)   # k != k: NaN
        print(f"{axis:<12} điểm TB {mean:.2f}  |  kappa từng cặp: {shown}")
        if any(k != k for k in kappas):
            print(f"{'':<12} (— nghĩa là người chấm chỉ dùng đúng một mức điểm, kappa không xác định)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--per-subject", type=int, default=8)
    parser.add_argument("--llm", action="store_true", help="gợi ý do model sinh thay vì template")
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument("--kappa", type=Path, default=None, help="tính kappa từ phiếu đã chấm")
    args = parser.parse_args()

    if args.kappa:
        report_kappa(args.kappa)
        return

    rows = build_rows(args.per_subject, args.llm, args.seed)
    path = OUTPUT / ("hint_ratings_llm.csv" if args.llm else "hint_ratings_template.csv")
    write_sheet(rows, path)

    print(f"\n{len(rows)} gợi ý ({args.per_subject} bài × 4 mức × 4 môn), nguồn: "
          f"{'model' if args.llm else 'template'}")
    print(f"Đã ghi {path}")
    print("\nCách dùng: gửi file này cho 3 người chấm (mỗi người một bản sao), chấm 1–5 "
          "trên bốn cột, rồi gộp lại thành các cột dung_toan_1, dung_toan_2, ... và chạy:")
    print(f"  python scripts/build_hint_rating_sheet.py --kappa {path.parent}/hint_ratings_filled.csv\n")


if __name__ == "__main__":
    main()
