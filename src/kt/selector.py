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


@dataclass
class SelectorWeights:
    """Trọng số các tiêu chí. Đổi ở đây để chạy ablation EXP-6."""

    weak_skill: float = 1.0      # ưu tiên kỹ năng còn yếu
    zpd: float = 2.0             # ưu tiên bài vừa sức
    prerequisite: float = 0.5    # ưu tiên bài đã đủ nền tảng
    repetition_penalty: float = 3.0


def zpd_score(p_correct: float, target: float = TARGET_SUCCESS, width: float = 0.02) -> float:
    """Điểm 1.0 khi xác suất đúng bằng mục tiêu, giảm nhanh khi lệch xa."""
    return math.exp(-((p_correct - target) ** 2) / width)


def expected_success(item: Item, tracker: BKTTracker) -> float:
    """Xác suất làm đúng cả bài.

    Lấy mức thành thạo THẤP NHẤT trong các kỹ năng của bài, không lấy trung
    bình: một bài cần ba kỹ năng mà người học yếu một kỹ năng thì vẫn sẽ sai,
    lấy trung bình sẽ che mất chỗ yếu đó.
    """
    if not item.skills:
        return 0.5
    weakest = min(tracker.mastery(skill) for skill in item.skills)
    return probability_correct(weakest)


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


def score_item(
    item: Item,
    tracker: BKTTracker,
    skills: dict,
    recent_item_ids: set[str],
    weights: SelectorWeights | None = None,
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
        - penalty
    )


def select_next(
    items: list[Item],
    tracker: BKTTracker,
    skills: dict,
    recent_item_ids: set[str] | None = None,
    weights: SelectorWeights | None = None,
) -> Item | None:
    """Bài tập nên cho làm tiếp theo."""
    if not items:
        return None
    recent_item_ids = recent_item_ids or set()
    return max(items, key=lambda item: score_item(item, tracker, skills, recent_item_ids, weights))


def select_random(items: list[Item], rng) -> Item | None:
    """Chọn ngẫu nhiên — nhóm đối chứng của EXP-6."""
    return rng.choice(items) if items else None
