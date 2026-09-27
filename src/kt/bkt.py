"""Bayesian Knowledge Tracing — mô hình năng lực cơ sở.

Bốn tham số cho mỗi kỹ năng:

- ``p_init``  xác suất đã nắm được kỹ năng từ trước khi luyện
- ``p_learn`` xác suất học được sau mỗi lần làm bài
- ``p_slip``  đã nắm được nhưng vẫn làm sai (bất cẩn)
- ``p_guess`` chưa nắm được nhưng làm đúng (đoán mò)

Vì sao bắt đầu bằng BKT chứ không nhảy thẳng lên DKT:

- **Giải thích được**: hiển thị cho sinh viên "em đã nắm 72% kỹ năng đổi biến"
  là con số có nghĩa, còn vector ẩn của LSTM thì không.
- **Chạy được ngay với rất ít dữ liệu**, trong khi DKT cần hàng nghìn chuỗi.
- **Làm baseline cho EXP-5**: không có baseline thì con số AUC của DKT vô nghĩa.

DKT/SAKT sẽ thay thế ở Gate 3; giao diện ``update``/``mastery`` giữ nguyên để
đổi mô hình mà không phải sửa API.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BKTParams:
    """Tham số BKT. Giá trị mặc định lấy theo khoảng thường gặp trong literature."""

    p_init: float = 0.25
    p_learn: float = 0.15
    p_slip: float = 0.10
    p_guess: float = 0.20

    def __post_init__(self) -> None:
        for name in ("p_init", "p_learn", "p_slip", "p_guess"):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} phải nằm trong [0, 1], nhận {value}")
        # slip + guess >= 1 làm mô hình mất ý nghĩa: quan sát "đúng" khi đó lại
        # là bằng chứng cho việc CHƯA nắm được kỹ năng.
        if self.p_slip + self.p_guess >= 1.0:
            raise ValueError("p_slip + p_guess phải nhỏ hơn 1")


def posterior(prior: float, correct: bool, params: BKTParams) -> float:
    """Xác suất đã nắm kỹ năng, sau khi quan sát một lần làm bài."""
    if correct:
        numerator = prior * (1 - params.p_slip)
        denominator = numerator + (1 - prior) * params.p_guess
    else:
        numerator = prior * params.p_slip
        denominator = numerator + (1 - prior) * (1 - params.p_guess)

    if denominator == 0:
        return prior
    return numerator / denominator


def transition(posterior_value: float, params: BKTParams) -> float:
    """Cập nhật sau khi học: đã làm bài thì có cơ hội học được."""
    return posterior_value + (1 - posterior_value) * params.p_learn


def update(prior: float, correct: bool, params: BKTParams | None = None) -> float:
    """Một bước BKT đầy đủ: quan sát rồi học."""
    params = params or BKTParams()
    return transition(posterior(prior, correct, params), params)


def probability_correct(mastery: float, params: BKTParams | None = None) -> float:
    """Xác suất làm đúng lần tới — đầu vào cho việc chọn bài theo vùng phát triển gần."""
    params = params or BKTParams()
    return mastery * (1 - params.p_slip) + (1 - mastery) * params.p_guess


class BKTTracker:
    """Theo dõi mức thành thạo nhiều kỹ năng của một người học."""

    def __init__(
        self,
        params: BKTParams | None = None,
        per_skill: dict[str, BKTParams] | None = None,
    ) -> None:
        self.params = params or BKTParams()
        self.per_skill = per_skill or {}
        self._mastery: dict[str, float] = {}

    def params_for(self, skill_id: str) -> BKTParams:
        return self.per_skill.get(skill_id, self.params)

    def mastery(self, skill_id: str) -> float:
        return self._mastery.get(skill_id, self.params_for(skill_id).p_init)

    def set_mastery(self, skill_id: str, value: float) -> None:
        self._mastery[skill_id] = min(max(value, 0.0), 1.0)

    def observe(self, skill_ids: list[str], correct: bool) -> dict[str, float]:
        """Cập nhật sau một lần làm bài.

        Một bài thường dùng nhiều kỹ năng cùng lúc. Ở đây gán kết quả cho TẤT CẢ
        kỹ năng của bài — đây là giới hạn đã biết của BKT (bài sai vì kỹ năng nào
        thì mô hình không biết). Chính điểm yếu này là một lý do chuyển sang DKT,
        và cần nêu trong báo cáo.
        """
        updated: dict[str, float] = {}
        for skill_id in skill_ids:
            new_value = update(self.mastery(skill_id), correct, self.params_for(skill_id))
            self.set_mastery(skill_id, new_value)
            updated[skill_id] = new_value
        return updated

    def probability_for(self, skill_id: str) -> float:
        """Xác suất làm đúng kỹ năng này ở lượt kế.

        Có phương thức này để bộ chọn bài hỏi được mà không cần biết đang dùng mô
        hình nào: BKT phải đi qua slip/guess, còn DKT đã trả thẳng xác suất.
        """
        return probability_correct(self.mastery(skill_id), self.params_for(skill_id))

    def snapshot(self) -> dict[str, float]:
        return dict(self._mastery)

    def weakest(self, candidates: list[str], limit: int = 3) -> list[str]:
        return sorted(candidates, key=self.mastery)[:limit]
