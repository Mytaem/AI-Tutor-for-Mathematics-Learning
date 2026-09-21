"""Chính sách leo thang gợi ý.

Viết thành hàm thuần tuý (state + sự kiện -> mức gợi ý), tách hẳn khỏi phần sinh
văn bản. Ba lý do:

- **Ablation được**: EXP-7 cần so "có ladder" với "trả đáp án luôn" — chỉ cần đổi
  một cờ trong config, không phải sửa code.
- **Test được**: kiểm tra luật leo thang mà không cần gọi LLM.
- **Giải thích được**: khi bảo vệ, chính sách là một bảng luật đọc ra được, chứ
  không phải "model tự quyết".

Nguyên tắc sư phạm nằm sau các luật này: học sinh phải được tự nghĩ trước. Gợi ý
đến quá sớm hoặc quá thẳng sẽ biến bài luyện tập thành bài chép đáp án.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum


class HintLevel(IntEnum):
    """Sáu mức gợi ý, càng lên càng lộ nhiều."""

    PROBE = 0     # khơi gợi, chưa nói gì về nội dung
    CONCEPT = 1   # nhắc lại khái niệm/công thức liên quan
    PITFALL = 2   # cảnh báo cái bẫy đúng với loại lỗi đang mắc
    LOCATE = 3    # chỉ ra bước sai, chưa nói sai thế nào
    CORRECT = 4   # sửa bước đó và giải thích vì sao
    FULL = 5      # lời giải đầy đủ

    @property
    def label_vi(self) -> str:
        return {
            HintLevel.PROBE: "Khơi gợi",
            HintLevel.CONCEPT: "Nhắc khái niệm",
            HintLevel.PITFALL: "Cảnh báo bẫy",
            HintLevel.LOCATE: "Chỉ bước sai",
            HintLevel.CORRECT: "Sửa và giải thích",
            HintLevel.FULL: "Lời giải đầy đủ",
        }[self]


@dataclass
class PolicyConfig:
    """Tham số của chính sách. Đổi ở đây để chạy ablation."""

    enabled: bool = True
    #: Số lần sai liên tiếp cùng một loại lỗi trước khi tự động leo thang.
    repeat_threshold: int = 2
    #: Số lần sinh viên phải xin lời giải đầy đủ thì mới được cấp.
    solution_requests_required: int = 2
    #: Ngưỡng thành thạo để giảm/tăng mức trợ giúp ban đầu.
    high_mastery: float = 0.75
    low_mastery: float = 0.35
    #: Mức cao nhất mà leo thang TỰ ĐỘNG được phép chạm tới.
    auto_ceiling: HintLevel = HintLevel.CORRECT


@dataclass
class TutorState:
    """Trạng thái một phiên làm bài."""

    item_id: str
    attempts: int = 0
    consecutive_wrong: int = 0
    last_error_codes: tuple[str, ...] = ()
    last_hint_level: HintLevel | None = None
    solution_requests: int = 0
    hints_given: list[HintLevel] = field(default_factory=list)

    def record_attempt(self, correct: bool, error_codes: tuple[str, ...] = ()) -> None:
        self.attempts += 1
        if correct:
            self.consecutive_wrong = 0
        else:
            # Chỉ tính là "lặp lại" khi sai cùng một loại lỗi. Sinh viên sửa được
            # lỗi cũ rồi mắc lỗi mới là đang tiến bộ, không nên bị leo thang.
            same_mistake = bool(error_codes) and error_codes == self.last_error_codes
            self.consecutive_wrong = self.consecutive_wrong + 1 if same_mistake else 1
        self.last_error_codes = error_codes

    def record_hint(self, level: HintLevel) -> None:
        self.last_hint_level = level
        self.hints_given.append(level)


class HintPolicy:
    """Quyết định mức gợi ý tiếp theo."""

    def __init__(self, config: PolicyConfig | None = None) -> None:
        self.config = config or PolicyConfig()

    def decide(
        self,
        state: TutorState,
        *,
        requested: bool = False,
        asked_for_solution: bool = False,
        mastery: float | None = None,
    ) -> HintLevel:
        """Mức gợi ý nên đưa ra lúc này.

        ``requested``        — sinh viên bấm "gợi ý thêm".
        ``asked_for_solution`` — sinh viên đòi xem lời giải đầy đủ.
        ``mastery``          — mức thành thạo kỹ năng liên quan, None nếu chưa biết.
        """
        config = self.config

        # Ablation: tắt ladder thì trả thẳng lời giải, dùng làm nhóm đối chứng.
        if not config.enabled:
            return HintLevel.FULL

        if asked_for_solution:
            state.solution_requests += 1
            if state.solution_requests >= config.solution_requests_required:
                return HintLevel.FULL
            # Lần đòi đầu tiên: chưa cho, đẩy lên một mức để họ thử tiếp.
            return self._bounded(self._escalate(state))

        if state.last_hint_level is None:
            return self._starting_level(state, mastery)

        if requested or self._stuck_on_same_mistake(state):
            return self._bounded(self._escalate(state))

        # Chưa có tín hiệu nào cho thấy cần thêm trợ giúp: giữ nguyên mức.
        return state.last_hint_level

    # ------------------------------------------------------------------

    def _starting_level(self, state: TutorState, mastery: float | None) -> HintLevel:
        """Mức gợi ý đầu tiên, tuỳ theo đã làm thử chưa và mức thành thạo."""
        if state.attempts == 0:
            return HintLevel.PROBE

        if mastery is None:
            return HintLevel.CONCEPT
        if mastery >= self.config.high_mastery:
            # Nắm vững kỹ năng này mà vẫn sai thì nhiều khả năng chỉ là bất cẩn —
            # một câu khơi gợi đủ để họ tự soát lại, không cần giảng lại lý thuyết.
            return HintLevel.PROBE
        if mastery <= self.config.low_mastery:
            return HintLevel.PITFALL
        return HintLevel.CONCEPT

    def _stuck_on_same_mistake(self, state: TutorState) -> bool:
        return state.consecutive_wrong >= self.config.repeat_threshold

    @staticmethod
    def _escalate(state: TutorState) -> HintLevel:
        """Chỉ leo đúng MỘT mức mỗi lượt."""
        if state.last_hint_level is None:
            return HintLevel.CONCEPT
        return HintLevel(min(state.last_hint_level + 1, HintLevel.FULL))

    def _bounded(self, level: HintLevel) -> HintLevel:
        """Chặn trần: leo thang tự động không bao giờ chạm tới lời giải đầy đủ."""
        return HintLevel(min(level, self.config.auto_ceiling))
