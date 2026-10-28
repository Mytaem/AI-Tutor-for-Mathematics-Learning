"""Rà lời giải từng bước trên TOÀN BỘ ngân hàng đề — chạy: python scripts/audit_solutions.py

    python scripts/audit_solutions.py                 # cả 4 môn
    python scripts/audit_solutions.py MAS291 --show 3 # in mẫu lời giải
    python scripts/audit_solutions.py --export data/sft/solutions.jsonl

Mỗi đề: có hàm giải không, và lời giải có qua bộ chấm không (bước cuối ra đúng
đáp án của đề). Lời giải không qua bộ chấm sẽ KHÔNG được hiển thị cho người học,
nên con số "qua kiểm" chính là độ phủ thật sự của gợi ý từng bước.

``--export`` ghi mọi lời giải đã kiểm thành JSONL (đề, bước, đáp án) — tập dữ liệu
lời giải chuẩn hoá dùng để huấn luyện/đánh giá mô hình, mỗi dòng đều đúng theo
cấu tạo vì đã qua bộ chấm.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.api.app import _load_bank  # noqa: E402
from src.solve import solve, solve_unchecked, solver_key  # noqa: E402

SUBJECTS = ("MAE101", "MAD101", "MAI391", "MAS291")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("subjects", nargs="*", default=list(SUBJECTS))
    parser.add_argument("--show", type=int, default=0, help="in N lời giải mẫu mỗi môn")
    parser.add_argument("--export", type=Path, default=None)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    exported = []
    for subject in args.subjects:
        bank = _load_bank(subject)
        no_solver, failed, passed = Counter(), Counter(), Counter()
        examples = {}
        shown = 0
        for item in bank.items.values():
            kind = item.meta.get("template") or item.meta.get("task") or "?"
            key = solver_key(item)
            if key is None:
                no_solver[kind] += 1
                continue
            solution = solve(item)
            if solution is None:
                failed[kind] += 1
                raw = solve_unchecked(item)
                examples.setdefault(kind, (item.item_id, raw.answer if raw else None, item.answer_text))
                continue
            passed[kind] += 1
            if args.export:
                exported.append({"item_id": item.item_id, "subject": subject, "statement": item.statement_vi,
                                 "theory": solution.theory, "formula": solution.formula,
                                 "steps": [asdict(s) for s in solution.steps], "answer": solution.answer})
            if shown < args.show:
                shown += 1
                print(f"\n--- {item.item_id}: {item.statement_vi}")
                print(f"    Kiến thức: {solution.theory}\n    Công thức: {solution.formula}")
                for i, s in enumerate(solution.steps, 1):
                    print(f"    Bước {i}: {s.action}" + (f"  [{s.formula}]" if s.formula else ""))
                    if s.work:
                        print(f"            {s.work}")
                    if s.result:
                        print(f"            ⇒ {s.result}")
        total = len(bank.items)
        ok = sum(passed.values())
        print(f"\n== {subject}: {ok}/{total} đề có lời giải đã kiểm ({100 * ok / total:.1f}%) | "
              f"chưa có hàm giải {sum(no_solver.values())} | lời giải hỏng {sum(failed.values())}")
        for kind, count in no_solver.most_common():
            print(f"   chưa có hàm giải: {kind} ({count})")
        for kind, count in failed.most_common():
            print(f"   HỎNG: {kind} ({count}) ví dụ {examples[kind]}")

    if args.export:
        args.export.parent.mkdir(parents=True, exist_ok=True)
        with args.export.open("w", encoding="utf-8") as handle:
            for row in exported:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"\nGhi {len(exported)} lời giải đã kiểm vào {args.export}")


if __name__ == "__main__":
    main()
