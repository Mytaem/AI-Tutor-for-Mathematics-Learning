"""Khởi tạo năng lực cho người học mới, và bài kiểm tra đầu vào.

Vấn đề: BKT gán cho mọi kỹ năng cùng một tiên nghiệm ``p_init``. Với người học
mới, mọi kỹ năng có mức thành thạo bằng nhau, nên điểm vùng phát triển gần cũng
bằng nhau, và bộ chọn bài gần như chọn tuỳ ý trong vài lượt đầu. Nếu để vậy mà
thu dữ liệu người dùng thật thì những lượt đầu của mỗi người đều là nhiễu.

Ba cơ chế xử lý, theo thứ tự hiệu quả:

1. **Tiên nghiệm theo độ sâu trong đồ thị tiên quyết.** Kỹ năng nền tảng (không
   cần kỹ năng nào trước nó) nhiều khả năng đã biết; kỹ năng nằm sâu thì chưa.
   Miễn phí, không tốn lượt hỏi nào.
2. **Lan truyền ngược lên tiên quyết.** Giải được bài đổi biến thì đương nhiên
   biết quy tắc hàm hợp — một câu trả lời cho thông tin về nhiều kỹ năng.
3. **Bài kiểm tra đầu vào.** Vài câu chọn theo độ BẤT ĐỊNH cao nhất, không phải
   theo vùng phát triển gần: lúc này mục tiêu là ĐO, chưa phải là DẠY.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.core.schema import Item, Skill
from src.kt.bkt import BKTTracker

#: Tiên nghiệm cho kỹ năng nền tảng (độ sâu 0).
BASE_PRIOR = 0.45
#: Mỗi tầng sâu thêm thì tiên nghiệm giảm đi bấy nhiêu.
DEPTH_DECAY = 0.07
#: Không bao giờ cho tiên nghiệm xuống dưới mức này.
FLOOR_PRIOR = 0.12

#: Số câu của bài kiểm tra đầu vào. Đủ để định vị, đủ ngắn để không ai bỏ ngang.
PLACEMENT_LENGTH = 6

#: Làm đúng một bài thì tiên quyết của nó được nâng lên ít nhất mức này.
PREREQUISITE_FLOOR = 0.6


def skill_depths(skills: dict[str, Skill]) -> dict[str, int]:
    """Độ sâu của mỗi kỹ năng trong đồ thị tiên quyết.

    Độ sâu 0 nghĩa là không cần kỹ năng nào trước đó. Giả định đồ thị là DAG —
    ``ItemBank.prerequisite_cycles`` đã kiểm tra điều này, và có test cho nó.
    """
    depths: dict[str, int] = {}

    def depth_of(skill_id: str, visiting: frozenset[str] = frozenset()) -> int:
        if skill_id in depths:
            return depths[skill_id]
        if skill_id in visiting:
            return 0  # chu trình: đã có test chặn, ở đây chỉ để không treo

        skill = skills.get(skill_id)
        parents = [p for p in (skill.prerequisites if skill else []) if p in skills]
        value = 0 if not parents else 1 + max(
            depth_of(parent, visiting | {skill_id}) for parent in parents
        )
        depths[skill_id] = value
        return value

    for skill_id in skills:
        depth_of(skill_id)
    return depths


def initial_mastery(skills: dict[str, Skill]) -> dict[str, float]:
    """Tiên nghiệm cho từng kỹ năng, suy từ vị trí trong đồ thị tiên quyết."""
    depths = skill_depths(skills)
    return {
        skill_id: max(FLOOR_PRIOR, BASE_PRIOR - DEPTH_DECAY * depth)
        for skill_id, depth in depths.items()
    }


def make_tracker(skills: dict[str, Skill], saved: dict[str, float] | None = None) -> BKTTracker:
    """Dựng tracker: tiên nghiệm từ đồ thị, rồi đè lên bằng dữ liệu đã lưu."""
    tracker = BKTTracker()
    for skill_id, value in initial_mastery(skills).items():
        tracker.set_mastery(skill_id, value)
    for skill_id, value in (saved or {}).items():
        tracker.set_mastery(skill_id, value)
    return tracker


def propagate_prerequisites(
    tracker: BKTTracker,
    skills: dict[str, Skill],
    demonstrated: list[str],
    floor: float = PREREQUISITE_FLOOR,
) -> dict[str, float]:
    """Làm đúng một bài thì nâng luôn các kỹ năng tiên quyết của nó.

    Giải được tích phân đổi biến thì nhất định đã biết quy tắc hàm hợp — không
    có lý do gì bắt sinh viên chứng minh lại điều đó bằng một bài riêng.

    Số đo trên ngân hàng MAE101 (13 kỹ năng, 6 câu đo): làm đúng hết thì cập
    nhật được 10/13 kỹ năng, đúng/sai xen kẽ 9/13, sai hết chỉ 6/13 — vì lan
    truyền chỉ chạy khi làm đúng.

    Chỉ NÂNG, không bao giờ hạ: bài làm sai không nói lên điều gì về tiên quyết
    (có thể họ nắm chắc tiên quyết nhưng vẫn chưa học phần mới).
    """
    updated: dict[str, float] = {}
    queue = list(demonstrated)
    seen: set[str] = set()

    while queue:
        skill_id = queue.pop()
        skill = skills.get(skill_id)
        if skill is None:
            continue
        for parent in skill.prerequisites:
            if parent in seen or parent not in skills:
                continue
            seen.add(parent)
            if tracker.mastery(parent) < floor:
                tracker.set_mastery(parent, floor)
                updated[parent] = floor
            queue.append(parent)

    return updated


# --------------------------------------------------------------------------
# Bài kiểm tra đầu vào
# --------------------------------------------------------------------------

def uncertainty(mastery: float) -> float:
    """Độ bất định về một kỹ năng. Cao nhất khi mức thành thạo quanh 0.5."""
    return 1.0 - 2.0 * abs(mastery - 0.5)


@dataclass
class PlacementConfig:
    length: int = PLACEMENT_LENGTH
    #: Phạt bài dùng kỹ năng đã hỏi rồi, để phủ rộng thay vì đào sâu một chỗ.
    coverage_weight: float = 1.5


def placement_score(
    item: Item,
    tracker: BKTTracker,
    covered_skills: set[str],
    config: PlacementConfig | None = None,
) -> float:
    """Bài này cho biết thêm được bao nhiêu thông tin?

    Khác hẳn tiêu chí lúc luyện tập: ở đây KHÔNG nhắm vào bài vừa sức, mà nhắm
    vào bài mà ta đang mù mờ nhất về kết quả. Bài chắc chắn làm được hoặc chắc
    chắn làm sai đều không cho thêm thông tin nào.
    """
    config = config or PlacementConfig()
    if not item.skills:
        return 0.0

    information = sum(uncertainty(tracker.mastery(s)) for s in item.skills) / len(item.skills)
    fresh = sum(1 for s in item.skills if s not in covered_skills) / len(item.skills)
    return information + config.coverage_weight * fresh


def select_placement_item(
    items: list[Item],
    tracker: BKTTracker,
    covered_skills: set[str],
    exclude: set[str] | None = None,
    config: PlacementConfig | None = None,
) -> Item | None:
    """Câu tiếp theo của bài kiểm tra đầu vào."""
    exclude = exclude or set()
    pool = [item for item in items if item.item_id not in exclude]
    if not pool:
        return None
    return max(pool, key=lambda item: placement_score(item, tracker, covered_skills, config))


def is_placement_done(answered: int, config: PlacementConfig | None = None) -> bool:
    return answered >= (config or PlacementConfig()).length
