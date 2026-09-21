"""Nạp và tra cứu ngân hàng bài tập + cây kỹ năng.

Ngân hàng đề để ở dạng JSONL (mỗi dòng một bài) thay vì một file JSON lớn: dễ
nối thêm bài do máy sinh, dễ xem diff trên git, và một dòng hỏng không làm chết
cả file.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from src.core.schema import ErrorCode, Item, Skill, Subject

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
ITEMS_DIR = DATA_DIR / "items"
SKILLS_DIR = DATA_DIR / "skills"
ERRORS_DIR = DATA_DIR / "errors"


class ItemBankError(ValueError):
    """Dữ liệu ngân hàng đề không hợp lệ."""


def load_items(path: str | Path) -> list[Item]:
    """Nạp các bài tập từ file JSONL, báo rõ số dòng khi gặp lỗi."""
    path = Path(path)
    items: list[Item] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            try:
                items.append(Item.model_validate(json.loads(line)))
            except Exception as exc:
                raise ItemBankError(f"{path.name} dòng {line_number}: {exc}") from exc
    return items


def write_items(items: list[Item], path: str | Path) -> None:
    """Ghi ngân hàng đề ra JSONL. Bỏ các trường rỗng cho file gọn và dễ đọc diff."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for item in items:
            payload = item.model_dump(mode="json", exclude_defaults=True)
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def load_skills(path: str | Path) -> list[Skill]:
    path = Path(path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [Skill.model_validate(entry) for entry in raw]


def load_error_codes(path: str | Path) -> dict[str, ErrorCode]:
    """Nạp bảng phân loại lỗi, tra cứu theo mã."""
    path = Path(path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    codes = [ErrorCode.model_validate(entry) for entry in raw]
    return {code.code: code for code in codes}


#: Bảng mã lỗi của từng môn, theo MẢNG KIẾN THỨC môn đó gồm — khớp với cách
#: ghép bộ chấm trong ``src/verify/registry.py``.
COURSE_TAXONOMIES: dict[str, list[str]] = {
    "MAE101": ["mae101.json", "linear_algebra.json"],
    "MAI391": ["mai391.json", "linear_algebra.json"],
    "MAS291": ["mas291.json"],
    "MAD101": ["mad101.json"],
}


def course_taxonomy_paths(subject: Subject | str) -> list[Path]:
    code = subject.value if isinstance(subject, Subject) else subject
    names = COURSE_TAXONOMIES.get(code, [f"{code.lower()}.json"])
    return [ERRORS_DIR / name for name in names if (ERRORS_DIR / name).exists()]


def load_course_error_codes(subject: Subject | str) -> dict[str, ErrorCode]:
    """Mọi mã lỗi có thể gặp trong một môn = hợp các bảng mã lỗi của các mảng nó gồm."""
    codes: dict[str, ErrorCode] = {}
    for path in course_taxonomy_paths(subject):
        codes.update(load_error_codes(path))
    return codes


class ItemBank:
    """Tra cứu bài tập theo mã, theo kỹ năng, theo độ khó."""

    def __init__(self, items: list[Item], skills: list[Skill]) -> None:
        self.items = {item.item_id: item for item in items}
        self.skills = {skill.skill_id: skill for skill in skills}

        self._by_skill: dict[str, list[str]] = defaultdict(list)
        for item in items:
            for skill_id in item.skills:
                self._by_skill[skill_id].append(item.item_id)

    @classmethod
    def load(cls, subject: Subject | str) -> ItemBank:
        """Nạp ngân hàng đề của một môn theo quy ước đặt tên file."""
        code = subject.value if isinstance(subject, Subject) else subject
        stem = code.lower()
        return cls(
            items=load_items(ITEMS_DIR / f"{stem}.jsonl"),
            skills=load_skills(SKILLS_DIR / f"{stem}.json"),
        )

    # ------------------------------------------------------------------

    def get(self, item_id: str) -> Item:
        if item_id not in self.items:
            raise KeyError(f"Không có bài tập {item_id!r}")
        return self.items[item_id]

    def by_skill(self, skill_id: str) -> list[Item]:
        return [self.items[i] for i in self._by_skill.get(skill_id, [])]

    def by_difficulty(self, low: float = 0.0, high: float = 1.0) -> list[Item]:
        return [item for item in self.items.values() if low <= item.difficulty <= high]

    # ------------------------------------------------------------------
    # Kiểm tra tính nhất quán
    # ------------------------------------------------------------------

    def unknown_skill_references(self) -> list[tuple[str, str]]:
        """Các bài tập tham chiếu tới kỹ năng không tồn tại — lỗi gõ nhầm mã."""
        problems: list[tuple[str, str]] = []
        for item in self.items.values():
            for skill_id in item.skills:
                if skill_id not in self.skills:
                    problems.append((item.item_id, skill_id))
        return problems

    def prerequisite_cycles(self) -> list[list[str]]:
        """Tìm chu trình trong đồ thị tiên quyết.

        Cây kỹ năng bắt buộc phải là DAG: nếu A cần B mà B lại cần A thì bộ chọn
        bài sẽ không bao giờ tìm được điểm bắt đầu cho người học mới.
        """
        cycles: list[list[str]] = []
        WHITE, GREY, BLACK = 0, 1, 2
        color = dict.fromkeys(self.skills, WHITE)

        def visit(node: str, stack: list[str]) -> None:
            color[node] = GREY
            stack.append(node)
            for parent in self.skills[node].prerequisites:
                if parent not in self.skills:
                    continue
                if color[parent] == GREY:
                    cycles.append(stack[stack.index(parent):] + [parent])
                elif color[parent] == WHITE:
                    visit(parent, stack)
            stack.pop()
            color[node] = BLACK

        for skill_id in self.skills:
            if color[skill_id] == WHITE:
                visit(skill_id, [])
        return cycles

    def orphan_prerequisites(self) -> list[tuple[str, str]]:
        """Kỹ năng tiên quyết trỏ tới mã không tồn tại."""
        problems: list[tuple[str, str]] = []
        for skill in self.skills.values():
            for parent in skill.prerequisites:
                if parent not in self.skills:
                    problems.append((skill.skill_id, parent))
        return problems
