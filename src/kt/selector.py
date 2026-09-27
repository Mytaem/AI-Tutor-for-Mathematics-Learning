"""Chọn bài tập tiếp theo.

Nguyên tắc: bài tốt nhất không phải bài dễ nhất, cũng không phải bài khó nhất,
mà là bài nằm ở rìa khả năng hiện tại của người học — vùng phát triển gần
(zone of proximal development). Bài quá dễ thì chán, quá khó thì nản, cả hai
đều không học được gì.

Cách làm: dùng mô hình năng lực ước lượng xác suất làm đúng, rồi ưu tiên những
bài có xác suất gần 0.75 — đủ khó để phải nghĩ, đủ dễ để không bỏ cuộc.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from src.core.schema import Item
from src.kt.bkt import BKTTracker, probability_correct

#: Xác suất làm đúng lý tưởng cho một bài luyện tập.
TARGET_SUCCESS = 0.75

#: Độ khó dịch xác suất bao nhiêu trên thang logit khi đi từ bài dễ nhất tới khó nhất.
#: 3.0 nghĩa là bài khó nhất (difficulty = 1) kéo xác suất đúng xuống cỡ 0.75 → 0.4.
DIFFICULTY_SCALE = 3.0


@dataclass
class SelectorWeights:
    """Trọng số các tiêu chí. Đổi ở đây để chạy ablation EXP-6."""

    weak_skill: float = 1.0      # ưu tiên kỹ năng còn yếu
    zpd: float = 2.0             # ưu tiên bài vừa sức
    prerequisite: float = 0.5    # ưu tiên bài đã đủ nền tảng
    repetition_penalty: float = 3.0
    coverage: float = 0.0        # ưu tiên kỹ năng ÍT ĐƯỢC LUYỆN trong phiên


def zpd_score(p_correct: float, target: float = TARGET_SUCCESS, width: float = 0.02) -> float:
    """Điểm 1.0 khi xác suất đúng bằng mục tiêu, giảm nhanh khi lệch xa."""
    return math.exp(-((p_correct - target) ** 2) / width)


def expected_success(item: Item, tracker: BKTTracker) -> float:
    """Xác suất làm đúng cả bài.

    Lấy mức thành thạo THẤP NHẤT trong các kỹ năng của bài, không lấy trung
    bình: một bài cần ba kỹ năng mà người học yếu một kỹ năng thì vẫn sẽ sai,
    lấy trung bình sẽ che mất chỗ yếu đó.

    Có tính ĐỘ KHÓ của bài. Bản trước chỉ nhìn mức thành thạo, nên mọi bài của
    cùng một kỹ năng đều cho cùng một xác suất — tiêu chí "vừa sức" khi đó không
    phân biệt nổi bài dễ với bài khó, và chiến lược ZPD thoái hoá thành chọn
    theo kỹ năng yếu. Phát hiện khi chạy EXP-6 trên học sinh mô phỏng.
    """
    if not item.skills:
        return 0.5
    weakest = min(item.skills, key=tracker.mastery)
    # Hỏi thẳng mô hình năng lực, đừng tự áp công thức của BKT: DKT đã trả ra
    # xác suất đúng rồi, đưa qua slip/guess lần nữa là tính hai lần.
    if hasattr(tracker, "probability_for"):
        base = tracker.probability_for(weakest)
    else:
        base = probability_correct(tracker.mastery(weakest))
    return _shift_by_difficulty(base, item.difficulty)


def _shift_by_difficulty(probability: float, difficulty: float) -> float:
    """Dịch xác suất theo độ khó, trên thang logit.

    Bài có ``difficulty = 0.5`` là trung bình nên giữ nguyên; dễ hơn thì kéo xác
    suất lên, khó hơn thì kéo xuống. Làm trên thang logit để kết quả luôn nằm
    trong (0, 1) và không bóp méo ở hai đầu.
    """
    clamped = min(max(probability, 1e-6), 1 - 1e-6)
    logit = math.log(clamped / (1 - clamped))
    return 1.0 / (1.0 + math.exp(-(logit - DIFFICULTY_SCALE * (difficulty - 0.5))))


def prerequisite_readiness(item: Item, tracker: BKTTracker, skills: dict) -> float:
    """Người học đã nắm các kỹ năng tiên quyết của bài này tới đâu?"""
    prerequisites: set[str] = set()
    for skill_id in item.skills:
        skill = skills.get(skill_id)
        if skill is not None:
            prerequisites.update(skill.prerequisites)

    if not prerequisites:
        return 1.0
    return sum(tracker.mastery(p) for p in prerequisites) / len(prerequisites)


def coverage_score(item: Item, practised: dict[str, int] | None) -> float:
    """Kỹ năng của bài này đã luyện bao nhiêu lần rồi? Ít thì điểm cao.

    Cần thiết vì tiêu chí "vừa sức" một mình dẫn tới ĐÀO SÂU MỘT CHỖ: bộ chọn
    bám lấy kỹ năng đang cho xác suất đúng ≈ 0.75 và bỏ quên phần còn lại của
    chương. Đo được trên học sinh mô phỏng ở EXP-6: với chương đồ thị MAD101,
    ZPD thuần chỉ giúp thạo 1.2 kỹ năng trong khi dạy theo thứ tự giáo trình
    được 3.7.
    """
    if not practised or not item.skills:
        return 1.0
    return 1.0 / (1.0 + min(practised.get(skill, 0) for skill in item.skills))


def score_item(
    item: Item,
    tracker: BKTTracker,
    skills: dict,
    recent_item_ids: set[str],
    weights: SelectorWeights | None = None,
    practised: dict[str, int] | None = None,
) -> float:
    weights = weights or SelectorWeights()

    weakness = 1.0 - min(tracker.mastery(s) for s in item.skills) if item.skills else 0.5
    fit = zpd_score(expected_success(item, tracker))
    readiness = prerequisite_readiness(item, tracker, skills)
    penalty = weights.repetition_penalty if item.item_id in recent_item_ids else 0.0

    return (
        weights.weak_skill * weakness
        + weights.zpd * fit
        + weights.prerequisite * readiness
        + weights.coverage * coverage_score(item, practised)
        - penalty
    )


def select_next(
    items: list[Item],
    tracker: BKTTracker,
    skills: dict,
    recent_item_ids: set[str] | None = None,
    weights: SelectorWeights | None = None,
    practised: dict[str, int] | None = None,
) -> Item | None:
    """Bài tập nên cho làm tiếp theo.

    ``practised``: số lần từng kỹ năng đã được luyện trong phiên, để tiêu chí
    phủ kỹ năng hoạt động. Không truyền thì tiêu chí đó vô hiệu.
    """
    if not items:
        return None
    recent_item_ids = recent_item_ids or set()
    return max(items, key=lambda item: score_item(item, tracker, skills, recent_item_ids,
                                                  weights, practised))


def select_random(items: list[Item], rng) -> Item | None:
    """Chọn ngẫu nhiên — nhóm đối chứng của EXP-6."""
    return rng.choice(items) if items else None
