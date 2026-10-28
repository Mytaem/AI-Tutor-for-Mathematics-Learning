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


def _solution(item: Item):
    from src.solve import solve

    return solve(item)


def _detail(number: int, step, *, with_result: bool) -> list[str]:
    """Một bước dạng nhiều dòng: việc cần làm, công thức, phép tính, kết quả."""
    lines = [f"Bước {number}: {step.action}"]
    if step.formula:
        lines.append(f"   Công thức: {step.formula}")
    if step.work:
        lines.append(f"   {step.work}")
    if with_result and step.result:
        lines.append(f"   ⇒ {step.result}")
    return lines


def _norm(text: str) -> str:
    return " ".join(text.lower().split())


def _lower_first(text: str) -> str:
    # Chỉ hạ chữ đầu của một TỪ thường ("Tính" -> "tính"); ký hiệu như "D", "det" giữ nguyên.
    if len(text) > 1 and text[0].isupper() and text[1].islower():
        return text[0].lower() + text[1:]
    return text


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

    # Các mức dưới đây dựng từ LỜI GIẢI ĐÃ KIỂM (src/solve): chương, kiến thức,
    # công thức và các bước cụ thể của chính bài này. Mỗi dòng qua guardrail
    # riêng — dòng nào lộ đáp án ở mức đó thì bỏ dòng đó, không bỏ cả gợi ý.

    def _where(self, item: Item) -> str:
        from src.core.syllabus import display_name

        skill = self.skills.get(item.skills[0]) if item.skills else None
        if skill is None:
            return ""
        return f"Bài thuộc chương «{display_name(item.subject.value, skill.chapter)}», phần «{skill.name_vi}»."

    @staticmethod
    def _safe(lines: list[str], item: Item, level: HintLevel) -> list[str]:
        return [line for line in lines if line and not check_leak(line, item, level).leaked]

    def _probe(self, item: Item, result: VerificationResult) -> Hint:
        solution = _solution(item)
        if solution is None:
            return Hint(HintLevel.PROBE, self._rng.choice(PROBES), "template")
        lines = self._safe([
            self._where(item),
            f"Em xác định lại: đề cho những dữ kiện gì, và hỏi gì? "
            f"Việc đầu tiên cần làm là: {_lower_first(solution.steps[0].action)}.",
        ], item, HintLevel.PROBE)
        return Hint(HintLevel.PROBE, "\n".join(lines) or self._rng.choice(PROBES), "solution")

    def _concept(self, item: Item, result: VerificationResult) -> Hint:
        solution = _solution(item)
        if solution is not None:
            lines = self._safe([
                self._where(item),
                f"Kiến thức cần dùng: {solution.theory}",
                f"Công thức: {solution.formula}" if solution.formula else "",
            ], item, HintLevel.CONCEPT)
            if lines:
                return Hint(HintLevel.CONCEPT, "\n".join(lines), "solution",
                            error_code=self._primary_code(result))
        return self._concept_template(item, result)

    def _concept_template(self, item: Item, result: VerificationResult) -> Hint:
        method = item.meta.get("method") or ""
        skill = self.skills.get(item.skills[0]) if item.skills else None

        name = skill.name_vi if skill is not None else ""
        parts: list[str] = []
        if name and method and _norm(method) not in _norm(name) and _norm(name) not in _norm(method):
            parts.append(f"Bài này thuộc phần «{name}», cụ thể là dạng «{method}».")
        elif method or name:
            parts.append(f"Bài này thuộc dạng «{method or name}».")
        parts.append("Em viết ra công thức hoặc định nghĩa của dạng này trước, "
                     "rồi áp từng số liệu của đề vào nhé.")

        return Hint(HintLevel.CONCEPT, " ".join(parts), "template",
                    error_code=self._primary_code(result))

    def _pitfall(self, item: Item, result: VerificationResult) -> Hint:
        """Cảnh báo đúng cái bẫy mà sinh viên đang mắc, lấy từ taxonomy lỗi."""
        code = self._primary_code(result)
        entry = self.error_codes.get(code) if code else None
        solution = _solution(item)

        lines: list[str] = []
        if entry is not None and entry.hint_vi:
            lines.append(entry.hint_vi)
        if solution is not None:
            lines.append("Các bước làm bài này:")
            lines += [f"Bước {i}: {s.action}" + (f" — dùng {s.formula}" if s.formula else "")
                      for i, s in enumerate(solution.steps, start=1)]
        lines = self._safe(lines, item, HintLevel.PITFALL)
        if lines:
            # Có chẩn đoán thì câu đầu là cái bẫy ĐÚNG loại lỗi đang mắc: nguồn chính là taxonomy.
            source = "taxonomy" if entry is not None and entry.hint_vi else "solution"
            return Hint(HintLevel.PITFALL, "\n".join(lines), source, error_code=code)

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

        solution = _solution(item)
        if solution is not None:
            # Làm mẫu bước đầu tiên có số của chính đề; các bước sau chỉ nêu việc cần làm.
            first, rest = solution.steps[0], solution.steps[1:]
            lines = self._safe(
                ["Thầy làm mẫu bước đầu, em làm tiếp nhé:", *_detail(1, first, with_result=True)]
                + [f"Bước {i}: {s.action}" for i, s in enumerate(rest, start=2)],
                item, HintLevel.LOCATE)
            if len(lines) > 1:
                return Hint(HintLevel.LOCATE, "\n".join(lines), "solution", step=1,
                            error_code=self._primary_code(result))

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
            parts.append(f"Chỗ sai là «{entry.name_vi}»: {_lower_first(entry.description_vi)}")

        reference = self._reference_step(item, result.first_wrong_step)
        if reference:
            parts.append(f"Bước đó đúng ra phải là: {reference}")

        solution = _solution(item)
        if solution is not None:
            # Mọi bước có số, trừ KẾT QUẢ của bước cuối: em tự làm phép tính sau cùng.
            *head, last = solution.steps
            lines = parts + ["Làm lại theo các bước:"]
            for i, step in enumerate(head, start=1):
                lines += _detail(i, step, with_result=True)
            lines += _detail(len(solution.steps), last, with_result=False)
            return Hint(HintLevel.CORRECT, "\n".join(lines), "solution",
                        error_code=code, step=result.first_wrong_step)

        if not parts:
            parts.append("Em rà lại phép biến đổi cuối cùng nhé, chỗ đó chưa chính xác.")

        return Hint(HintLevel.CORRECT, " ".join(parts), "reference",
                    error_code=code, step=result.first_wrong_step)

    def _full(self, item: Item, result: VerificationResult) -> Hint:
        solution = _solution(item)
        if solution is not None:
            lines = [f"Lời giải đầy đủ cho bài «{item.statement_vi}»:", f"Kiến thức: {solution.theory}"]
            for i, step in enumerate(solution.steps, start=1):
                lines += _detail(i, step, with_result=True)
            lines.append(f"Đáp án: {item.answer_text}")
            return Hint(HintLevel.FULL, "\n".join(lines), "solution")

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
