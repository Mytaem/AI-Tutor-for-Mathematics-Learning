"""Dựng tập dữ liệu huấn luyện cho bộ phân loại mã lỗi (EXP-3, Phần H).

Bài toán: cho đề bài, đáp án đúng và bài làm sai của sinh viên → đoán MÃ LỖI.
Đây là tầng neural, chỉ chạy khi tầng ký hiệu không kết luận được; lúc đó hệ
thống vẫn biết đáp án đúng, nên prompt có quyền chứa nó (khác hẳn prompt sinh
gợi ý, nơi đáp án là thứ phải giấu).

Ba quyết định về dữ liệu, đều ảnh hưởng thẳng tới con số báo cáo:

1. **Chia theo ĐỀ, không theo mẫu.** Một đề đẻ ra nhiều mẫu lỗi khác nhau; chia
   theo mẫu thì cùng một đề nằm cả ở train lẫn test, mô hình học thuộc đề và
   macro-F1 đẹp giả.
2. **Phân tầng theo mã lỗi.** Mã hiếm phải có mặt ở cả ba tập, nếu không thì
   macro-F1 tính trên tập test thiếu lớp, không so sánh được giữa các lần chạy.
3. **Giới hạn số mẫu mỗi mã.** Dữ liệu tự sinh lệch rất nặng (mã nhiều nhất gấp
   trăm lần mã ít nhất); không chặn trần thì mô hình chỉ cần đoán vài mã phổ
   biến là đã có accuracy cao, trong khi macro-F1 vẫn tệ.
"""

from __future__ import annotations

import json
import random
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from src.core.itembank import ERRORS_DIR, ErrorCode, load_course_error_codes

SUBJECTS = ("MAE101", "MAI391", "MAS291", "MAD101")

INSTRUCTION = (
    "Bạn là trợ giảng toán. Dưới đây là một bài tập, đáp án đúng và bài làm SAI của "
    "sinh viên. Hãy xác định MÃ LỖI mô tả đúng nhất kiểu sai lầm đó. "
    "Chỉ trả lời bằng đúng một mã lỗi trong danh sách, không giải thích."
)


@dataclass
class Example:
    """Một mẫu huấn luyện."""

    item_id: str
    subject: str
    error_code: str
    tier: str
    prompt: str
    completion: str

    def to_json(self) -> dict:
        return {
            "item_id": self.item_id, "subject": self.subject, "error_code": self.error_code,
            "tier": self.tier, "prompt": self.prompt, "completion": self.completion,
        }


def load_rows(subjects=SUBJECTS) -> list[dict]:
    rows: list[dict] = []
    for subject in subjects:
        path = ERRORS_DIR / f"{subject.lower()}_injected.jsonl"
        if path.exists():
            rows += [json.loads(line) for line in path.open(encoding="utf-8")]
    return rows


def code_menu(codes: dict[str, ErrorCode], subject: str) -> str:
    """Danh sách mã lỗi của môn, kèm tên — mô hình chọn trong đây chứ không bịa."""
    return "\n".join(f"- {code}: {entry.name_vi}" for code, entry in sorted(codes.items()))


def build_prompt(row: dict, menu: str) -> str:
    parts = [
        INSTRUCTION,
        f"\nMÔN: {row['subject']}",
        f"ĐỀ BÀI: {row['statement_vi']}",
        f"ĐÁP ÁN ĐÚNG: {row['correct_answer']}",
        f"BÀI LÀM CỦA SINH VIÊN: {row['wrong_final_answer']}",
    ]
    if row.get("wrong_steps"):
        steps = "; ".join(str(s) for s in row["wrong_steps"])
        parts.append(f"CÁC BƯỚC SINH VIÊN VIẾT: {steps}")
    parts.append(f"\nDANH SÁCH MÃ LỖI:\n{menu}")
    parts.append("\nMÃ LỖI:")
    return "\n".join(parts)


def build_examples(rows: list[dict] | None = None) -> list[Example]:
    rows = rows if rows is not None else load_rows()
    menus = {subject: code_menu(load_course_error_codes(subject), subject) for subject in SUBJECTS}
    return [
        Example(
            item_id=row["item_id"], subject=row["subject"], error_code=row["error_code"],
            tier=row.get("tier", ""), prompt=build_prompt(row, menus[row["subject"]]),
            completion=row["error_code"],
        )
        for row in rows
        if row["subject"] in menus
    ]


def cap_per_code(examples: list[Example], limit: int, seed: int = 20260923) -> list[Example]:
    """Chặn trần số mẫu mỗi mã lỗi để tập dữ liệu bớt lệch."""
    rng = random.Random(seed)
    grouped: dict[str, list[Example]] = defaultdict(list)
    for example in examples:
        grouped[example.error_code].append(example)

    kept: list[Example] = []
    for code, group in grouped.items():
        rng.shuffle(group)
        kept += group[:limit]
    rng.shuffle(kept)
    return kept


def split_by_item(
    examples: list[Example],
    ratios: tuple[float, float, float] = (0.7, 0.15, 0.15),
    seed: int = 20260923,
) -> tuple[list[Example], list[Example], list[Example]]:
    """Chia theo ĐỀ và phân tầng theo mã lỗi.

    Với mỗi mã lỗi, các ĐỀ mang mã đó được chia theo tỉ lệ; nhờ vậy mã hiếm vẫn
    có mặt ở cả ba tập, mà không đề nào nằm ở hai tập cùng lúc.
    """
    rng = random.Random(seed)
    by_code: dict[str, list[str]] = defaultdict(list)
    for example in examples:
        if example.item_id not in by_code[example.error_code]:
            by_code[example.error_code].append(example.item_id)

    assignment: dict[str, str] = {}
    for code in sorted(by_code):
        items = sorted(set(by_code[code]) - set(assignment))   # đề đã chia rồi thì giữ nguyên
        rng.shuffle(items)
        first = max(1, round(len(items) * ratios[0]))
        second = first + max(1, round(len(items) * ratios[1])) if len(items) > 2 else first
        for position, item_id in enumerate(items):
            assignment[item_id] = ("train" if position < first
                                   else "validation" if position < second else "test")

    buckets: dict[str, list[Example]] = {"train": [], "validation": [], "test": []}
    for example in examples:
        buckets[assignment.get(example.item_id, "train")].append(example)
    return buckets["train"], buckets["validation"], buckets["test"]


def write_jsonl(examples: list[Example], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for example in examples:
            handle.write(json.dumps(example.to_json(), ensure_ascii=False) + "\n")


def load_jsonl(path: str | Path) -> list[Example]:
    return [Example(**json.loads(line)) for line in Path(path).open(encoding="utf-8")]


def label_distribution(examples: list[Example]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for example in examples:
        counts[example.error_code] += 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))
