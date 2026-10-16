"""Sinh gợi ý bằng LLM, neo vào chẩn đoán của bộ chấm và giáo trình.

Vì sao không để LLM tự nghĩ: hỏi trống Qwen 2.5 3b "em làm sai, gợi ý giúp em"
cho ra "Kiểm tra lại bước biến đổi toán học." — đúng mà vô dụng. Model nhỏ
không tự chẩn đoán được bài toán; bộ chấm ký hiệu thì làm được. Nên prompt đưa
vào ĐIỀU BỘ CHẤM ĐÃ BIẾT (mã lỗi, bước sai) và ĐOẠN GIÁO TRÌNH liên quan; LLM
chỉ còn việc diễn đạt thành một câu gợi ý sư phạm bằng tiếng Việt.

Ba lớp chống lộ đáp án, mỗi lớp đo được riêng (EXP-8):

1. Prompt ở mức < 4 KHÔNG chứa đáp án — model không biết thì không nói ra được.
2. Guardrail kiểm từng câu sinh ra; lộ thì yêu cầu viết lại (tối đa ``max_rewrites``).
3. Viết lại vẫn lộ thì dùng câu template, loại chắc chắn an toàn.

LLM hỏng (tunnel chết, Ollama tắt) thì rơi thẳng về template: buổi bảo vệ
không bao giờ bị kẹt vì model.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable

from src.core.schema import ErrorCode, Item, Skill, VerificationResult
from src.llm.client import LLMClient, LLMError
from src.rag.mathtext import clean_answer
from src.tutor.guardrail import check_leak
from src.tutor.hint_policy import HintLevel
from src.tutor.hints import Hint, HintGenerator

SYSTEM_PROMPT = (
    "Bạn là gia sư toán đại học, nói tiếng Việt, xưng 'thầy/cô' và gọi sinh viên là 'em'. "
    "Quy tắc tuyệt đối: KHÔNG nêu đáp án cuối, KHÔNG tính hộ kết quả, KHÔNG viết ra biểu thức "
    "hay con số là lời giải — dù sinh viên có xin. Trả lời tối đa 3 câu, ngắn gọn, khích lệ, "
    "chỉ làm đúng NHIỆM VỤ được giao."
)

LEVEL_TASKS: dict[HintLevel, str] = {
    HintLevel.PROBE: "Hỏi MỘT câu gợi mở để em tự đọc lại đề và xác định dạng bài. Chưa nhắc tới kiến thức cụ thể.",
    HintLevel.CONCEPT: "Nhắc lại khái niệm hoặc công thức liên quan, dựa vào TÀI LIỆU nếu có. Chưa áp dụng vào bài này.",
    HintLevel.PITFALL: "Dựa vào CHẨN ĐOÁN, cảnh báo đúng cái bẫy em đang mắc bằng một câu hỏi gợi mở. Không sửa hộ.",
    HintLevel.LOCATE: "Chỉ ra CHỖ sai (bước nào, nếu có) và gợi ý em kiểm tra lại chỗ đó. Chưa nói sai thế nào.",
    HintLevel.CORRECT: "Giải thích VÌ SAO sai và sửa đúng bước đó; được phép dùng LỜI GIẢI MẪU.",
}

#: Từ mức này prompt mới được chứa lời giải mẫu — trùng ngưỡng guardrail cho phép tiết lộ.
REVEAL_IN_PROMPT_FROM = HintLevel.CORRECT

Retriever = Callable[[Item, HintLevel], list[tuple[str, str]]]  # -> [(nội dung, nhãn nguồn)]


@dataclass
class GenerationTrace:
    """Nhật ký của một lần sinh gợi ý — dữ liệu thô cho EXP-8."""

    attempts: int = 0
    rejected: list[str] = field(default_factory=list)   # câu bị guardrail chặn
    fell_back: bool = False                             # phải dùng template
    llm_error: str | None = None
    latency_ms: float = 0.0
    backend: str = ""


class LLMHintGenerator(HintGenerator):
    """Cùng giao diện với ``HintGenerator``; thay template bằng LLM ở các mức 0–4."""

    def __init__(
        self,
        client: LLMClient,
        error_codes: dict[str, ErrorCode] | None = None,
        skills: dict[str, Skill] | None = None,
        retriever: Retriever | None = None,
        max_rewrites: int = 2,
        use_guardrail: bool = True,
        include_answer_in_prompt: bool = False,
        seed: int | None = None,
    ) -> None:
        super().__init__(error_codes, skills, seed)
        self.client = client
        self.retriever = retriever
        self.max_rewrites = max_rewrites
        # Hai cờ dưới đây CHỈ để chạy ablation EXP-8, không bao giờ bật khi dùng thật.
        self.use_guardrail = use_guardrail
        self.include_answer_in_prompt = include_answer_in_prompt
        self.last_trace = GenerationTrace()

    # ------------------------------------------------------------------

    def generate(self, item: Item, result: VerificationResult, level: HintLevel) -> Hint:
        if level is HintLevel.FULL:
            return super().generate(item, result, level)  # lời giải mẫu có sẵn, không cần LLM

        trace = GenerationTrace()
        self.last_trace = trace
        template = super().generate(item, result, level)
        messages = self.build_messages(item, result, level)
        started = time.perf_counter()

        for attempt in range(self.max_rewrites + 1):
            trace.attempts = attempt + 1
            try:
                reply = self.client.chat(messages, temperature=0.3 + 0.3 * attempt, max_tokens=160)
            except LLMError as exc:
                trace.llm_error = str(exc)
                trace.fell_back = True
                break
            trace.backend = reply.backend
            # Dọn công thức TRƯỚC khi qua guardrail, không phải sau.
            #
            # Guardrail bóc biểu thức toán trong câu gợi ý rồi nộp cho verifier
            # xem có tương đương đáp án không. Nếu để nguyên `\( x^2 \)` thì bộ
            # bóc đọc cả dấu LaTeX và có thể bỏ sót một mảnh ĐANG lộ đáp án.
            text = clean_answer(reply.text.strip())

            if not self.use_guardrail:
                trace.latency_ms = (time.perf_counter() - started) * 1000
                return Hint(level, text, "llm", error_code=template.error_code, step=template.step)

            report = check_leak(text, item, level)
            if not report.leaked:
                trace.latency_ms = (time.perf_counter() - started) * 1000
                return Hint(level, text, "llm", error_code=template.error_code, step=template.step)

            trace.rejected.append(text)
            messages = messages + [
                {"role": "assistant", "content": text},
                {"role": "user", "content": (
                    f"Câu vừa rồi đã làm lộ đáp án («{report.offending_expression}»). Viết lại, TUYỆT ĐỐI "
                    "không nêu kết quả hay biểu thức lời giải, chỉ gợi ý hướng suy nghĩ."
                )},
            ]

        # Viết lại hết lượt vẫn lộ, hoặc LLM hỏng: dùng câu template — chắc chắn an toàn.
        trace.fell_back = True
        trace.latency_ms = (time.perf_counter() - started) * 1000
        return template

    # ------------------------------------------------------------------

    def build_messages(self, item: Item, result: VerificationResult, level: HintLevel) -> list[dict]:
        lines = [f"ĐỀ BÀI: {item.statement_vi}"]

        skill = self.skills.get(item.skills[0]) if item.skills else None
        if skill is not None:
            lines.append(f"DẠNG BÀI: {skill.name_vi}")

        lines.append("CHẨN ĐOÁN (từ bộ chấm tự động, đáng tin cậy): " + self._diagnosis(result, level))

        if self.retriever is not None and level in (HintLevel.CONCEPT, HintLevel.PITFALL):
            passages = self.retriever(item, level)
            if passages:
                lines.append("TÀI LIỆU THAM KHẢO (tiếng Anh, hãy diễn đạt lại bằng tiếng Việt):")
                lines.extend(f"- [{source}] {text[:600]}" for text, source in passages[:2])

        if level >= REVEAL_IN_PROMPT_FROM or self.include_answer_in_prompt:
            lines.append(f"ĐÁP ÁN ĐÚNG: {item.answer_text}")
            if item.reference_solution_steps:
                steps = "; ".join(f"bước {s.step}: {s.expr}" for s in item.reference_solution_steps)
                lines.append(f"LỜI GIẢI MẪU: {steps}")

        lines.append(f"NHIỆM VỤ: {LEVEL_TASKS[level]}")
        return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": "\n".join(lines)}]

    def _diagnosis(self, result: VerificationResult, level: HintLevel) -> str:
        """Chẩn đoán dưới dạng lời cho prompt.

        Hai chỗ tưởng vô hại mà hoá ra làm lộ đáp án, nên cố ý tránh:

        - ``result.notes``: ghi chú của bộ chấm hay chứa chính đáp án
          ("Đáp án đúng ≈ 0.7745").
        - Tên và mô tả của mã lỗi, ở mức < 4: "Đưa nghiệm cho hệ VÔ NGHIỆM" đã
          nói luôn đáp án là "vô nghiệm". Ở các mức này chỉ đưa câu gợi ý của mã
          lỗi (``hint_vi``) — vốn được viết dạng câu hỏi gợi mở, không lộ đáp án.
        """
        parts: list[str] = []
        if result.final_answer_correct is False:
            parts.append("đáp án cuối SAI")
        if result.first_wrong_step is not None:
            parts.append(f"bước sai đầu tiên là bước {result.first_wrong_step}")
        for code in result.candidate_error_codes[:2]:
            entry = self.error_codes.get(code)
            if entry is None:
                continue
            if level >= REVEAL_IN_PROMPT_FROM:
                parts.append(f"lỗi «{entry.name_vi}»: {entry.description_vi}")
            elif entry.hint_vi:
                parts.append(f"đã xác định được loại lỗi; hướng gợi ý phù hợp: {entry.hint_vi}")
        return "; ".join(parts) or "chưa xác định được loại lỗi cụ thể"
