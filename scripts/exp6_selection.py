"""EXP-6 — bốn chiến lược chọn bài, đo trên học sinh mô phỏng.

    python scripts/exp6_selection.py                      # MAE101, chương tích phân
    python scripts/exp6_selection.py --subject MAD101 --prefix MAD.LOGIC
    python scripts/exp6_selection.py --students 100 --steps 80 --seeds 3

Bốn chiến lược:

    random      chọn bừa — nhóm đối chứng
    sequential  theo thứ tự giáo trình — cách dạy truyền thống
    weakest     luôn nhắm kỹ năng yếu nhất, bất kể bài khó hay dễ
    zpd         vùng phát triển gần: ưu tiên bài có xác suất đúng ≈ 0.75

Bốn chỉ số, cố ý đo cả cái LỢI lẫn cái GIÁ:

    tỉ lệ đúng        trải nghiệm học: quá thấp là nản, quá cao là chán
    số kỹ năng thạo   kết quả học thật sự sau phiên
    số bài tới mục tiêu  tốc độ
    sai liên tiếp dài nhất  chỉ số nản chí

Phiên luyện giới hạn trong MỘT chương (tham số ``--prefix``) vì đó mới giống
cách sinh viên ôn thật; trải đều 21 kỹ năng thì 60 bài không đủ để ai thạo được
gì, và mọi chiến lược trông như nhau.

Hạn chế phải ghi vào báo cáo: học sinh ở đây do mô hình sinh ra, không phải
người thật. Kết luận rút ra chỉ nói được về HÀNH VI CỦA THUẬT TOÁN dưới giả
định đó, không nói được về hiệu quả học tập ngoài đời.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.config import ROOT  # noqa: E402
from src.core.itembank import ITEMS_DIR, ItemBank, load_items  # noqa: E402
from src.kt.simulator import STRATEGIES, StudentProfile, simulate_cohort  # noqa: E402


def chapter_items(subject: str, prefix: str):
    """Đề và kỹ năng của một chương."""
    bank = ItemBank.load(subject)
    items = list(bank.items.values())
    generated = ITEMS_DIR / f"{subject.lower()}_generated.jsonl"
    if generated.exists():
        items += load_items(generated)

    skills = {k: v for k, v in bank.skills.items() if k.startswith(prefix)}
    if not skills:
        skills = bank.skills
    chosen = [i for i in items if i.skills and set(i.skills) <= set(skills)]
    return chosen, skills


def summarise(results) -> dict:
    reached = [r.steps_to_mastery for r in results if r.steps_to_mastery is not None]
    return {
        "n": len(results),
        "accuracy": statistics.mean(r.accuracy for r in results),
        "mastered": statistics.mean(r.mastered_skills for r in results),
        "mastered_sd": statistics.pstdev([r.mastered_skills for r in results]),
        "reached_target": len(reached) / len(results),
        "steps_to_target": statistics.mean(reached) if reached else None,
        "wrong_streak": statistics.mean(r.longest_wrong_streak for r in results),
    }


def average(runs: list[dict]) -> dict:
    """Gộp nhiều seed: trung bình, kèm độ lệch để biết chênh lệch có thật không."""
    keys = [k for k in runs[0] if k not in ("n",)]
    merged: dict = {"n": sum(r["n"] for r in runs), "seeds": len(runs)}
    for key in keys:
        values = [r[key] for r in runs if r[key] is not None]
        merged[key] = statistics.mean(values) if values else None
        merged[f"{key}_sd"] = statistics.pstdev(values) if len(values) > 1 else 0.0
    return merged


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--subject", default="MAE101")
    parser.add_argument("--prefix", default="MAE.INT", help="tiền tố mã kỹ năng của chương cần luyện")
    parser.add_argument("--students", type=int, default=60)
    parser.add_argument("--steps", type=int, default=60)
    parser.add_argument("--seeds", type=int, default=3, help="số lần lặp với seed khác nhau")
    parser.add_argument("--no-hint", action="store_true",
                        help="ablation: sai thì chỉ báo sai, không gợi ý (kiểm giả thiết sư phạm)")
    parser.add_argument("--coverage", type=float, default=None,
                        help="trọng số tiêu chí phủ kỹ năng cho chiến lược zpd_coverage")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    if args.coverage is not None:
        from src.kt import simulator
        from src.kt.selector import SelectorWeights

        simulator.ZPD_COVERAGE = SelectorWeights(coverage=args.coverage)

    items, skills = chapter_items(args.subject, args.prefix)
    if not items:
        print(f"Không có đề nào cho {args.subject} với tiền tố kỹ năng {args.prefix!r}")
        raise SystemExit(1)

    print(f"\n{args.subject} — chương {args.prefix}: {len(items)} đề, {len(skills)} kỹ năng")
    print(f"{args.students} học sinh mô phỏng × {args.steps} lượt × {args.seeds} seed"
          f"{' (KHÔNG gợi ý)' if args.no_hint else ''}\n")

    summary: dict[str, dict] = {}
    for strategy in STRATEGIES:
        runs = [
            summarise(simulate_cohort(items, skills, students=args.students, strategy=strategy,
                                      steps=args.steps, seed=1000 + 37 * index,
                                      with_hint=not args.no_hint))
            for index in range(args.seeds)
        ]
        summary[strategy] = average(runs)

    print(f"{'chiến lược':<12}{'tỉ lệ đúng':>12}{'kỹ năng thạo':>14}{'đạt mục tiêu':>14}"
          f"{'số bài':>9}{'sai liên tiếp':>15}")
    for strategy, row in summary.items():
        steps = f"{row['steps_to_target']:.0f}" if row["steps_to_target"] else "—"
        print(f"{strategy:<12}{row['accuracy']:>11.1%}{row['mastered']:>13.1f}"
              f"{row['reached_target']:>13.0%}{steps:>9}{row['wrong_streak']:>14.1f}")

    best_accuracy = max(summary, key=lambda s: summary[s]["accuracy"])
    calmest = min(summary, key=lambda s: summary[s]["wrong_streak"])
    most_mastered = max(summary, key=lambda s: summary[s]["mastered"])
    print(f"\n  tỉ lệ đúng cao nhất: {best_accuracy} | ít nản nhất: {calmest} | "
          f"thạo nhiều kỹ năng nhất: {most_mastered}")

    out = args.out or ROOT / "experiments" / "exp6" / (
        f"{args.subject.lower()}_{args.prefix.lower().replace('.', '_')}"
        f"{'_nohint' if args.no_hint else ''}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "subject": args.subject, "prefix": args.prefix, "items": len(items), "skills": len(skills),
        "students": args.students, "steps": args.steps, "seeds": args.seeds,
        "with_hint": not args.no_hint, "coverage": args.coverage, "profile": StudentProfile().__dict__, "summary": summary,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nĐã ghi {out}\n")


if __name__ == "__main__":
    main()
