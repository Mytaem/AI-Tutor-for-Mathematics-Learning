"""Sinh câu gợi ý theo từng mức, và engine ghép các mảnh lại.

Hiện tại gợi ý sinh bằng template + dữ liệu từ taxonomy lỗi. Khi ghép LLM vào,
chỉ thay phần sinh văn bản: chính sách leo thang, guardrail và nguồn dữ liệu giữ
nguyên. Nhờ vậy so sánh "template với LLM" trở thành một ablation sạch, và luôn
có sẵn một đường lui chạy được khi model chết giữa buổi bảo vệ.

Engine chỉ đọc ``VerificationResult``, không đọc lại đầu ra thô của bộ giải —
xem README, mục nguyên tắc thiết kế.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from src.core.schema import AnswerType, ErrorCode, Item, Skill, Submission, VerificationResult
from src.tutor.guardrail import LeakReport, check_leak
from src.tutor.hint_policy import HintLevel, HintPolicy, TutorState

PROBES = (
    "Em đọc lại đề một lượt nhé: bài cho gì và hỏi gì?",
    "Trước khi tính, em thử nói xem bài này thuộc dạng nào?",
    "Em thử kiểm tra lại kết quả của mình xem có hợp lý không?",
)

SELF_CHECK = (
    "Với bài nguyên hàm, em có thể tự kiểm tra bằng cách lấy đạo hàm đáp án "
    "xem có ra đúng biểu thức ban đầu không."
)

#: Cách tự kiểm tra theo loại bài. Mỗi loại đáp án có một phép thử ngược riêng —
#: nhắc đúng phép thử đó giúp sinh viên tự phát hiện lỗi mà không lộ đáp án.
SELF_CHECKS: dict[AnswerType, str] = {
    AnswerType.ANTIDERIVATIVE: SELF_CHECK,
    AnswerType.LINEAR_SYSTEM: "Em có thể tự kiểm tra bằng cách thế ngược nghiệm vào từng phương trình của hệ.",
    AnswerType.EIGENVECTOR: "Em tự kiểm tra được: nhân A với vector của em rồi so với λ lần vector đó.",
    AnswerType.ODE_SOLUTION: "Em thử lấy đạo hàm đáp án rồi thế ngược vào phương trình xem có ra đẳng thức không.",
}
GENERIC_SELF_CHECK = "Em thử rà lại từng bước và kiểm tra ngược kết quả của mình nhé."


def self_check_for(item: Item) -> str:
    if item.meta.get("task") == "inverse":
        return "Em tự kiểm tra được: nhân A với ma trận của em xem có ra ma trận đơn vị không."
    return SELF_CHECKS.get(item.answer_type, GENERIC_SELF_CHECK)


@dataclass
class Hint:
    """Một câu gợi ý đã qua kiểm duyệt."""

    level: HintLevel
    text: str
    source: str                      # template | taxonomy | reference | llm
    error_code: str | None = None
    step: int | None = None
    blocked_original: str | None = None  # câu gốc nếu bị guardrail chặn

    @property
    def was_blocked(self) -> bool:
        return self.blocked_original is not None


@dataclass
class TutorResponse:
    """Phản hồi trả về cho giao diện."""

    is_correct: bool
    hint: Hint | None
    verification: VerificationResult
    state: TutorState
    leak_report: LeakReport | None = None
    congratulation: str = ""


class HintGenerator:
    """Sinh văn bản gợi ý cho từng mức."""

    def __init__(
        self,
        error_codes: dict[str, ErrorCode] | None = None,
        skills: dict[str, Skill] | None = None,
        seed: int | None = None,
    ) -> None:
        self.error_codes = error_codes or {}
        self.skills = skills or {}
        self._rng = random.Random(seed)

    def generate(self, item: Item, result: VerificationResult, level: HintLevel) -> Hint:
        builders = {
            HintLevel.PROBE: self._probe,
            HintLevel.CONCEPT: self._concept,
            HintLevel.PITFALL: self._pitfall,
            HintLevel.LOCATE: self._locate,
            HintLevel.CORRECT: self._correct,
            HintLevel.FULL: self._full,
        }
        return builders[level](item, result)

    # ------------------------------------------------------------------

    def _probe(self, item: Item, result: VerificationResult) -> Hint:
        return Hint(HintLevel.PROBE, self._rng.choice(PROBES), "template")

    def _concept(self, item: Item, result: VerificationResult) -> Hint:
        method = item.meta.get("method") or ""
        skill = self.skills.get(item.skills[0]) if item.skills else None

        parts: list[str] = []
        if skill is not None:
            parts.append(f"Bài này thuộc dạng «{skill.name_vi}».")
        if method:
            parts.append(f"Hướng làm: {method}.")
        parts.append("Em nhớ lại công thức của dạng này rồi thử lại nhé.")

        return Hint(HintLevel.CONCEPT, " ".join(parts), "template",
                    error_code=self._primary_code(result))

    def _pitfall(self, item: Item, result: VerificationResult) -> Hint:
        """Cảnh báo đúng cái bẫy mà sinh viên đang mắc, lấy từ taxonomy lỗi."""
        code = self._primary_code(result)
        entry = self.error_codes.get(code) if code else None

        if entry is not None and entry.hint_vi:
            return Hint(HintLevel.PITFALL, entry.hint_vi, "taxonomy", error_code=code)

        # Chưa chẩn đoán được loại lỗi: đưa lời khuyên tự kiểm tra, không đoán bừa.
        return Hint(HintLevel.PITFALL, self_check_for(item), "template", error_code=code)

    def _locate(self, item: Item, result: VerificationResult) -> Hint:
        if result.first_wrong_step is not None:
            step = result.first_wrong_step
            return Hint(
                HintLevel.LOCATE,
                f"Em xem lại bước {step} nhé — chỗ đó chưa tương đương với bước trên. "
                f"Các bước trước đó của em đúng rồi.",
                "reference", step=step, error_code=self._primary_code(result),
            )

        return Hint(
            HintLevel.LOCATE,
            "Đáp án cuối của em chưa đúng. Em thử trình bày từng bước ra để "
            "thầy/cô xem giúp em sai ở chỗ nào nhé.",
            "template", error_code=self._primary_code(result),
        )

    def _correct(self, item: Item, result: VerificationResult) -> Hint:
        code = self._primary_code(result)
        entry = self.error_codes.get(code) if code else None

        parts: list[str] = []
        if result.first_wrong_step is not None:
            parts.append(f"Bước {result.first_wrong_step} của em chưa đúng.")
        if entry is not None:
            parts.append(f"Lỗi ở đây là: {entry.name_vi}. {entry.description_vi}")

        reference = self._reference_step(item, result.first_wrong_step)
        if reference:
            parts.append(f"Bước đó đúng ra phải là: {reference}")

        if not parts:
            parts.append("Em rà lại phép biến đổi cuối cùng nhé, chỗ đó chưa chính xác.")

        return Hint(HintLevel.CORRECT, " ".join(parts), "reference",
                    error_code=code, step=result.first_wrong_step)

    def _full(self, item: Item, result: VerificationResult) -> Hint:
        lines = [f"Lời giải đầy đủ cho bài «{item.statement_vi}»:"]

        if item.reference_solution_steps:
            for step in item.reference_solution_steps:
                explanation = f" — {step.explain_vi}" if step.explain_vi else ""
                lines.append(f"  Bước {step.step}: {step.expr}{explanation}")

        lines.append(f"Đáp án: {item.answer_text}")
        return Hint(HintLevel.FULL, "\n".join(lines), "reference")

    # ------------------------------------------------------------------

    @staticmethod
    def _primary_code(result: VerificationResult) -> str | None:
        return result.candidate_error_codes[0] if result.candidate_error_codes else None

    @staticmethod
    def _reference_step(item: Item, step_number: int | None) -> str | None:
        if step_number is None:
            return None
        for step in item.reference_solution_steps:
            if step.step == step_number:
                return step.expr
        return None


class TutorEngine:
    """Ghép verifier, chính sách leo thang, bộ sinh gợi ý và guardrail."""

    def __init__(
        self,
        verifier,
        generator: HintGenerator | None = None,
        policy: HintPolicy | None = None,
    ) -> None:
        self.verifier = verifier
        self.generator = generator or HintGenerator()
        self.policy = policy or HintPolicy()
        self._states: dict[str, TutorState] = {}

    def state_for(self, item_id: str, key: str | None = None) -> TutorState:
        """Trạng thái gợi ý của MỘT người trên MỘT bài.

        ``key`` phải phân biệt được người học (API truyền ``phiên:bài``). Nếu chỉ
        khoá theo mã bài thì mọi sinh viên dùng CHUNG một thang gợi ý: A bấm
        "gợi ý thêm" ba lần, B mở cùng bài đó sẽ nhận ngay gợi ý mức 4.
        """
        key = key or item_id
        return self._states.setdefault(key, TutorState(item_id=item_id))

    def reset(self, item_id: str, key: str | None = None) -> None:
        self._states.pop(key or item_id, None)

    # ------------------------------------------------------------------

    def submit(
        self,
        item: Item,
        submission: Submission,
        *,
        mastery: float | None = None,
        want_hint: bool = True,
        state_key: str | None = None,
    ) -> TutorResponse:
        """Nhận bài làm, chấm, rồi quyết định có gợi ý gì không."""
        state = self.state_for(item.item_id, state_key)
        result = self.verifier.verify(item, submission)

        state.record_attempt(result.is_correct, tuple(result.candidate_error_codes))

        if result.is_correct:
            return TutorResponse(
                is_correct=True, hint=None, verification=result, state=state,
                congratulation=self._praise(result),
            )

        if not want_hint:
            return TutorResponse(False, None, result, state)

        level = self.policy.decide(state, mastery=mastery)
        return self._respond_with_hint(item, result, state, level)

    def request_hint(
        self,
        item: Item,
        result: VerificationResult,
        *,
        asked_for_solution: bool = False,
        mastery: float | None = None,
        state_key: str | None = None,
    ) -> TutorResponse:
        """Sinh viên chủ động bấm 'gợi ý thêm'."""
        state = self.state_for(item.item_id, state_key)
        level = self.policy.decide(
            state, requested=True, asked_for_solution=asked_for_solution, mastery=mastery
        )
        return self._respond_with_hint(item, result, state, level)

    # ------------------------------------------------------------------

    def _respond_with_hint(
        self, item: Item, result: VerificationResult, state: TutorState, level: HintLevel
    ) -> TutorResponse:
        hint = self.generator.generate(item, result, level)
        report = check_leak(hint.text, item, level)

        if report.leaked:
            # Câu gợi ý lộ đáp án: thay bằng câu an toàn, giữ lại bản gốc để
            # thống kê tỉ lệ rò (EXP-8). Khi ghép LLM, chỗ này sẽ là vòng sinh lại.
            hint = Hint(
                level=level,
                text=self_check_for(item),
                source="fallback",
                error_code=hint.error_code,
                step=hint.step,
                blocked_original=hint.text,
            )

        state.record_hint(level)
        return TutorResponse(False, hint, result, state, leak_report=report)

    @staticmethod
    def _praise(result: VerificationResult) -> str:
        if result.candidate_error_codes:
            return "Đáp án của em đúng rồi. Còn một chi tiết nhỏ cần lưu ý ở dưới nhé."
        return "Chính xác. Em làm tốt lắm!"
