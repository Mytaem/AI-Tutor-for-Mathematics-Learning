"""FastAPI orchestrator — ghép verifier, tutor engine, mô hình năng lực và bộ chọn bài.

Nguyên tắc bảo mật quan trọng nhất của tầng này: **đáp án không bao giờ rời khỏi
server trước khi sinh viên được phép thấy nó**. Nếu endpoint trả bài tập kèm luôn
lời giải thì mọi thứ phía trên — hint ladder, guardrail chống lộ đáp án — đều vô
nghĩa, vì chỉ cần mở tab Network của trình duyệt là đọc được. Vì vậy có lớp
``PublicItem`` riêng, cố ý KHÔNG chứa ``answer``, ``integrand`` và
``reference_solution_steps``.

Tầng dịch vụ (``TutorService``) tách khỏi tầng HTTP để test được mà không cần
dựng server.
"""

from __future__ import annotations

import csv
import io
import os
import secrets
import sqlite3
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.core.config import AppConfig, load_config
from src.core.itembank import (
    ITEMS_DIR,
    SKILLS_DIR,
    ItemBank,
    load_course_error_codes,
    load_items,
    load_skills,
)
from src.core.pretty import pretty_math
from src.core.schema import AnswerType, Item, Submission, VerificationResult
from src.kt.bkt import BKTTracker
from src.kt.coldstart import (
    PLACEMENT_LENGTH,
    is_placement_done,
    make_tracker,
    propagate_prerequisites,
    select_placement_item,
)
from src.kt.selector import select_next
from src.tutor.hint_policy import HintLevel
from src.tutor.hints import HintGenerator, TutorEngine
from src.verify.registry import supported_subjects, verifier_for
from src.api.auth import (
    COOKIE_NAME,
    SESSION_DAYS,
    AuthError,
    LoginLimiter,
    check_password_rules,
    hash_password,
    new_token,
    normalize_email,
    token_digest,
    verify_or_waste_time,
    verify_password,
)
from src.api.db import Store
from src.api.mailer import Mailer


# ==========================================================================
# Mô hình dữ liệu cho HTTP
# ==========================================================================

# Giới hạn đầu vào được đặt ngay ở biên HTTP. Bộ chấm và RAG đều phải phân tích
# chuỗi người dùng gửi lên; nếu để chuỗi hoặc danh sách bước không giới hạn, một
# request lỗi có thể giữ CPU/RAM rất lâu và làm API mất phản hồi cho mọi người.
UserId = Annotated[str, Field(min_length=1, max_length=128)]
ObjectId = Annotated[str, Field(min_length=1, max_length=160)]
AnswerText = Annotated[str, Field(max_length=8_000)]
SolutionStep = Annotated[str, Field(max_length=4_000)]
QuestionText = Annotated[str, Field(min_length=1, max_length=4_000)]

class RegisterRequest(BaseModel):
    email: Annotated[str, Field(max_length=254)]
    password: Annotated[str, Field(max_length=256)]
    display_name: Annotated[str, Field(max_length=80)] = ""


class LoginRequest(BaseModel):
    email: Annotated[str, Field(max_length=254)]
    password: Annotated[str, Field(max_length=256)]


class PasswordChangeRequest(BaseModel):
    current_password: Annotated[str, Field(max_length=256)]
    new_password: Annotated[str, Field(max_length=256)]


class UserOut(BaseModel):
    user_id: str
    email: str
    display_name: str
    email_verified: bool = False


class TokenRequest(BaseModel):
    token: Annotated[str, Field(min_length=10, max_length=200)]


class ResetRequest(BaseModel):
    token: Annotated[str, Field(min_length=10, max_length=200)]
    new_password: Annotated[str, Field(max_length=256)]


class ForgotRequest(BaseModel):
    email: Annotated[str, Field(max_length=254)]


class DeleteAccountRequest(BaseModel):
    password: Annotated[str, Field(max_length=256)]


#: Địa chỉ web mà link trong email trỏ tới (trang /verify, /reset).
APP_URL = os.environ.get("APP_URL", "http://localhost:3000").rstrip("/")
VERIFY_TTL_S = 48 * 3600
RESET_TTL_S = 3600


@dataclass
class Identity:
    """Ai đang gọi: một tài khoản (``user_id``) hoặc một dịch vụ tin cậy (bot)."""

    user_id: str | None
    trusted: bool = False


#: Khoá cho dịch vụ nội bộ (bot Telegram) — gọi API thay mặt người dùng của nó,
#: không có cookie. Để trống thì không dịch vụ nào được gọi thay ai.
SERVICE_TOKEN = os.environ.get("SERVICE_TOKEN", "").strip()


#: Ngân sách cho model ở /ask, phải nhỏ hơn MODEL_TIMEOUT_MS (120 s) của web.
ASK_LLM_TIMEOUT_S = 100.0


class PublicItem(BaseModel):
    """Bài tập ở dạng gửi cho client — ĐÃ LƯỢC BỎ mọi thông tin về đáp án."""

    item_id: str
    subject: str
    skills: list[str]
    statement_vi: str
    statement_latex: str = ""
    answer_type: str
    variable: str
    bounds: tuple[str, str] | None = None
    difficulty: float
    #: Tên hiển thị cho người học — mã nội bộ (MAE.LIM.INDET) không nói gì với họ.
    skill_names: list[str] = []
    chapter_vi: str = ""
    topic_vi: str = ""

    @classmethod
    def of(cls, item: Item, bank: ItemBank | None = None) -> PublicItem:
        from src.core.syllabus import TASK_NAMES_VI, display_name

        skills = [bank.skills[s] for s in item.skills if bank and s in bank.skills]
        topic = item.meta.get("method") or TASK_NAMES_VI.get(item.meta.get("task") or "", "")
        return cls(
            item_id=item.item_id,
            subject=item.subject.value,
            skills=list(item.skills),
            skill_names=[s.name_vi for s in skills],
            chapter_vi=display_name(item.subject.value, skills[0].chapter) if skills else "",
            topic_vi=topic,
            statement_vi=pretty_math(item.statement_vi),
            statement_latex=item.statement_latex,
            answer_type=item.answer_type.value,
            variable=item.variable,
            bounds=item.bounds,
            difficulty=item.difficulty,
        )


class StartSessionRequest(BaseModel):
    #: Chỉ dùng cho bot (khoá dịch vụ). Người dùng web lấy danh tính từ phiên đăng nhập.
    user_id: UserId | None = None
    subject: Annotated[str, Field(min_length=1, max_length=16)] = "MAE101"


class StartSessionResponse(BaseModel):
    session_id: str
    user_id: str
    subject: str
    first_item: PublicItem | None
    #: Còn trong giai đoạn đo đầu vào không — giao diện nên nói rõ cho sinh viên
    #: biết đây là bài đo, không phải bài luyện, để họ không nản khi gặp câu khó.
    placement_mode: bool = False
    placement_remaining: int = 0


class AttemptRequest(BaseModel):
    session_id: ObjectId
    item_id: ObjectId
    final_answer: AnswerText | None = None
    steps: list[SolutionStep] = Field(default_factory=list, max_length=100)


class StepResultOut(BaseModel):
    step: int
    ok: bool | None
    reason: str


class HintOut(BaseModel):
    level: int
    level_label: str
    text: str
    source: str
    error_code: str | None = None
    step: int | None = None


class AttemptResponse(BaseModel):
    is_correct: bool
    final_answer_correct: bool | None
    first_wrong_step: int | None
    step_results: list[StepResultOut]
    error_codes: list[str]
    message: str
    hint: HintOut | None = None
    mastery_changes: dict[str, float] = Field(default_factory=dict)
    placement_mode: bool = False
    placement_remaining: int = 0


class HintRequest(BaseModel):
    session_id: ObjectId
    item_id: ObjectId
    asked_for_solution: bool = False


class SkillProgress(BaseModel):
    skill_id: str
    name_vi: str
    mastery: float


class ProgressResponse(BaseModel):
    user_id: str
    skills: list[SkillProgress]
    attempts: int
    correct: int


class TopicOut(BaseModel):
    """Dạng bài — tầng hẹp nhất người học chọn được."""

    topic_id: str
    name_vi: str
    items: int


class LessonOut(BaseModel):
    """Bài — chính là một kỹ năng."""

    skill_id: str
    name_vi: str
    items: int
    mastery: float | None = None
    topics: list[TopicOut] = Field(default_factory=list)


class ChapterOut(BaseModel):
    chapter: str
    name_vi: str
    items: int
    skills: int
    mastery: float | None = None
    lessons: list[LessonOut] = Field(default_factory=list)


class SyllabusResponse(BaseModel):
    """Cả cây nội dung của một môn trong MỘT lời gọi.

    Trả cả cây chứ không để giao diện gọi vòng theo từng chương: cây chỉ cỡ
    trăm nút, mà gọi vòng thì mỗi lần mở một chương lại chờ mạng một nhịp.
    """

    subject: str
    items: int
    chapters: list[ChapterOut] = Field(default_factory=list)


class SubjectStats(BaseModel):
    subject: str
    attempts: int
    learners: int
    correct: int
    unreadable: int
    accuracy: float | None = None


class ErrorCodeCount(BaseModel):
    error_code: str
    count: int


class HintLevelCount(BaseModel):
    level: int
    count: int


class LearnerRow(BaseModel):
    user_id: str
    attempts: int
    correct: int
    subjects: int
    last_seen: float | None = None


class AdminOverview(BaseModel):
    """Bảng điều khiển cho giảng viên: ai đang học, sai ở đâu, xin gợi ý bao nhiêu."""

    totals: dict[str, int]
    subjects: list[SubjectStats] = Field(default_factory=list)
    top_error_codes: list[ErrorCodeCount] = Field(default_factory=list)
    hint_levels: list[HintLevelCount] = Field(default_factory=list)
    learners: list[LearnerRow] = Field(default_factory=list)
    bank: dict[str, int] = Field(default_factory=dict)


class AskRequest(BaseModel):
    question: QuestionText
    subject: Annotated[str, Field(max_length=16)] | None = None
    chapter: Annotated[str, Field(max_length=128)] | None = None


class AskResponse(BaseModel):
    """Trả lời câu hỏi lý thuyết, LUÔN kèm nguồn để người đọc tự kiểm."""

    answer: str
    sources: list[str] = Field(default_factory=list)
    in_scope: bool = True
    used_llm: bool = False


# ==========================================================================
# Tầng dịch vụ
# ==========================================================================

class TutorService:
    """Toàn bộ nghiệp vụ, không dính gì tới HTTP.

    Giữ một ngân hàng đề và một tutor engine cho MỖI môn. Engine của từng môn
    mang verifier riêng (lấy qua registry), còn mọi thứ ở tầng này — mô hình
    năng lực, bài đo đầu vào, bộ chọn bài, lưu trữ — dùng chung, không biết gì
    về tích phân hay ma trận. Đây chính là điều cần chứng minh ở Gate 2: thêm
    môn mới không phải sửa tầng này.
    """

    def __init__(
        self,
        store: Store,
        banks: dict[str, ItemBank],
        engines: dict[str, TutorEngine],
        default_subject: str = "MAE101",
        config: AppConfig | None = None,
    ) -> None:
        self.store = store
        self.banks = banks
        self.engines = engines
        self.default_subject = default_subject
        self.config = config or AppConfig()

    # Giữ tương thích với mã gọi cũ chỉ biết một môn.
    @property
    def bank(self) -> ItemBank:
        return self.banks[self.default_subject]

    @property
    def engine(self) -> TutorEngine:
        return self.engines[self.default_subject]

    @property
    def subjects(self) -> list[str]:
        return sorted(self.banks)

    def bank_for(self, subject: str | None) -> ItemBank:
        subject = subject or self.default_subject
        if subject not in self.banks:
            raise LookupError(f"Chưa hỗ trợ môn {subject!r}. Các môn hiện có: {', '.join(self.subjects)}")
        return self.banks[subject]

    def all_skills(self) -> dict:
        merged: dict = {}
        for bank in self.banks.values():
            merged.update(bank.skills)
        return merged

    # ------------------------------------------------------------------

    def tracker_for(self, user_id: str, subject: str | None = None) -> BKTTracker:
        """Mô hình năng lực hiện tại.

        Người mới chưa có bản ghi nào thì tiên nghiệm lấy từ đồ thị tiên quyết,
        không dùng một giá trị phẳng cho mọi kỹ năng — nếu phẳng thì bộ chọn bài
        gần như chọn tuỳ ý trong vài lượt đầu. Mã kỹ năng có tiền tố môn nên
        mức thành thạo của các môn không đè lên nhau.
        """
        skills = self.bank_for(subject).skills if subject else self.all_skills()
        saved = self.store.load_mastery(user_id)

        if self.config.kt_model == "dkt" and subject:
            tracker = self._dkt_tracker(user_id, subject, skills, saved)
            if tracker is not None:
                return tracker
        return make_tracker(skills, saved)

    def _dkt_tracker(self, user_id: str, subject: str, skills: dict, saved: dict):
        """Mô hình DKT đã huấn luyện, nạp lại lịch sử làm bài của người này.

        DKT không giữ trạng thái giữa các lần gọi như BKT: nó suy ra năng lực từ
        CẢ CHUỖI, nên mỗi lần dựng lại phải phát lại lịch sử từ CSDL. Thiếu mô
        hình của môn thì trả None để quay về BKT — không được hỏng chỉ vì chưa
        huấn luyện xong.
        """
        from src.kt.coldstart import initial_mastery
        from src.kt.dkt_tracker import load_tracker

        prior = {**initial_mastery(skills), **saved}
        tracker = load_tracker(subject, prior)
        if tracker is None:
            return None
        bank = self.bank_for(subject)
        for item_id, correct in self.store.attempt_history(user_id, subject):
            item = bank.items.get(item_id)
            if item is not None and item.skills:
                tracker.observe(list(item.skills), correct)
        return tracker

    def in_placement(self, user_id: str, subject: str) -> bool:
        return not is_placement_done(self.store.attempt_count(user_id, subject))

    def placement_remaining(self, user_id: str, subject: str) -> int:
        return max(0, PLACEMENT_LENGTH - self.store.attempt_count(user_id, subject))

    def start_session(self, user_id: str, subject: str) -> StartSessionResponse:
        self.bank_for(subject)  # báo lỗi sớm nếu môn chưa hỗ trợ
        session_id = self.store.create_session(user_id, subject)
        item = self.pick_item(user_id, subject)
        return StartSessionResponse(
            session_id=session_id,
            user_id=user_id,
            subject=subject,
            first_item=PublicItem.of(item, self.bank_for(subject)) if item else None,
            placement_mode=self.in_placement(user_id, subject),
            placement_remaining=self.placement_remaining(user_id, subject),
        )

    def covered_skills(self, user_id: str, subject: str) -> set[str]:
        bank = self.bank_for(subject)
        covered: set[str] = set()
        for item_id in self.store.attempted_item_ids(user_id, subject):
            if item_id in bank.items:
                covered.update(bank.items[item_id].skills)
        return covered

    def syllabus(self, user_id: str | None, subject: str | None = None) -> SyllabusResponse:
        """Cây môn → chương → bài → dạng bài, kèm số đề và mức thành thạo."""
        from src.core.syllabus import chapters_of

        subject = subject or self.default_subject
        bank = self.bank_for(subject)
        items = list(bank.items.values())
        tracker = self.tracker_for(user_id, subject) if user_id else None

        def mastery_of(skill_ids) -> float | None:
            """Mức thành thạo của một nhóm kỹ năng = mức của kỹ năng YẾU NHẤT.

            Lấy min chứ không lấy trung bình: một chương có 3 kỹ năng vững và 1
            kỹ năng rỗng thì trung bình vẫn đẹp, và người học sẽ bỏ qua đúng
            chỗ cần luyện.
            """
            if tracker is None or not skill_ids:
                return None
            return round(min(tracker.mastery(s) for s in skill_ids), 4)

        chapters = [
            ChapterOut(
                chapter=chapter.chapter,
                name_vi=chapter.name_vi,
                items=chapter.items,
                skills=chapter.skills,
                mastery=mastery_of(chapter.skill_ids),
                lessons=[
                    LessonOut(
                        skill_id=lesson.skill_id,
                        name_vi=lesson.name_vi,
                        items=lesson.items,
                        mastery=mastery_of([lesson.skill_id]),
                        topics=[
                            TopicOut(topic_id=t.topic_id, name_vi=t.name_vi, items=t.items)
                            for t in lesson.topics
                        ],
                    )
                    for lesson in chapter.lessons
                ],
            )
            for chapter in chapters_of(bank, items, deep=True)
        ]
        return SyllabusResponse(subject=subject, items=len(items), chapters=chapters)

    def pick_item(
        self,
        user_id: str,
        subject: str | None = None,
        chapter: str | None = None,
        skill: str | None = None,
        topic: str | None = None,
    ) -> Item | None:
        from src.core.syllabus import filter_items

        subject = subject or self.default_subject
        bank = self.bank_for(subject)
        items = filter_items(bank, list(bank.items.values()), chapter, skill, topic)
        if not items:
            # Nói rõ phạm vi nào rỗng chứ không trả "hết đề": người học vừa tự
            # chọn phạm vi đó, họ cần biết là chọn hẹp quá, không phải hệ hỏng.
            raise LookupError(
                "Không có đề nào trong phạm vi đã chọn "
                f"({' / '.join(x for x in (chapter, skill, topic) if x) or subject}). "
                "Em thử chọn rộng hơn một bậc nhé."
            )
        tracker = self.tracker_for(user_id, subject)

        if self.in_placement(user_id, subject):
            # Giai đoạn đo: chọn bài cho nhiều THÔNG TIN nhất, không phải bài
            # vừa sức nhất. Bài chắc chắn đúng hoặc chắc chắn sai đều vô ích.
            return select_placement_item(
                items, tracker,
                covered_skills=self.covered_skills(user_id, subject),
                exclude=self.store.attempted_item_ids(user_id, subject),
            )

        return select_next(
            items, tracker, bank.skills,
            recent_item_ids=self.store.recent_item_ids(user_id, subject=subject),
        )

    # ------------------------------------------------------------------

    def submit(self, request: AttemptRequest) -> AttemptResponse:
        session = self._require_session(request.session_id)
        item = self._require_item(request.item_id)
        subject = item.subject.value
        user_id = session["user_id"]
        bank = self.banks[subject]

        tracker = self.tracker_for(user_id, subject)
        mastery_before = min((tracker.mastery(s) for s in item.skills), default=None)

        response = self.engines[subject].submit(
            item,
            Submission(
                item_id=item.item_id,
                final_answer=request.final_answer,
                steps=request.steps,
                raw_text=request.final_answer or "",
            ),
            mastery=mastery_before,
            state_key=self._state_key(request.session_id, item.item_id),
        )

        self.store.record_attempt(
            request.session_id, user_id, item.item_id,
            request.final_answer or "", request.steps, response.verification,
            subject=subject,
        )

        # Bộ chấm trả ``final_answer_correct = None`` nghĩa là nó TỪ CHỐI kết
        # luận (không đọc nổi bài làm), không phải kết luận "sai". Cập nhật năng
        # lực ở đây là ghi một lỗi ĐỊNH DẠNG thành lỗ hổng KIẾN THỨC: đo được là
        # mức thành thạo tụt đúng bằng một bài sai thật (0,45 → 0,23).
        verification = response.verification
        reached_verdict = (verification.final_answer_correct is not None
                           or verification.first_wrong_step is not None)
        changes = tracker.observe(item.skills, response.is_correct) if reached_verdict else {}

        if response.is_correct:
            # Làm đúng bài đổi biến thì đương nhiên đã nắm quy tắc hàm hợp.
            # Lan truyền ngược lên tiên quyết giúp một câu trả lời cho thông tin
            # về nhiều kỹ năng (đo được: 6 câu đúng cập nhật 10/13 kỹ năng).
            changes.update(propagate_prerequisites(tracker, bank.skills, item.skills))

        self.store.save_mastery(user_id, changes)

        if response.hint is not None:
            self.store.record_hint(request.session_id, item.item_id, response.hint)

        result = self._to_attempt_response(response, changes, item)
        result.placement_mode = self.in_placement(user_id, subject)
        result.placement_remaining = self.placement_remaining(user_id, subject)
        return result

    def request_hint(self, request: HintRequest) -> HintOut:
        session = self._require_session(request.session_id)
        item = self._require_item(request.item_id)
        subject = item.subject.value

        verification = self._last_verification(request.session_id, request.item_id)
        if verification is None:
            raise LookupError("Chưa có bài làm nào cho bài tập này trong phiên")

        tracker = self.tracker_for(session["user_id"], subject)
        mastery = min((tracker.mastery(s) for s in item.skills), default=None)

        response = self.engines[subject].request_hint(
            item, verification,
            asked_for_solution=request.asked_for_solution,
            mastery=mastery,
            state_key=self._state_key(request.session_id, item.item_id),
        )
        self.store.record_hint(request.session_id, item.item_id, response.hint)
        return self._to_hint(response.hint)

    def ask(self, question: str, subject: str | None = None, chapter: str | None = None):
        """Hỏi đáp lý thuyết. Kho RAG và model đều là tuỳ chọn — thiếu thì vẫn trả lời được."""
        from src.rag.ask import answer_question
        from src.rag.hint_retriever import load_index

        client = None
        if self.config.llm_ask:
            from src.llm.client import LLMClient

            from dataclasses import replace

            # Một lần gọi, không thử lại, và gói gọn dưới mức chờ 120 s của web
            # (MODEL_TIMEOUT_MS). Trước đây 90 s × 3 lần thử = 4–6 phút: web đã báo
            # lỗi từ lâu mà server vẫn cày, còn chặn hàng đợi của Ollama cho người sau.
            # Hết giờ thì answer_question tự trả nguyên đoạn giáo trình.
            client = LLMClient.from_config(replace(
                self.config.llm, max_retries=0,
                timeout_seconds=min(self.config.llm.timeout_seconds, ASK_LLM_TIMEOUT_S)))

        # Chọn chương thì thu hẹp truy xuất về đúng các kỹ năng của chương đó.
        # Đây là chỗ bộ lọc metadata đáng giá nhất: hỏi "kiểm định" mà không lọc
        # thì đoạn về hồi quy cũng chen vào vì dùng chung thuật ngữ thống kê.
        skill_ids = None
        if chapter and subject:
            from src.core.syllabus import skills_in_chapter

            skill_ids = sorted(skills_in_chapter(self.bank_for(subject), chapter)) or None

        return answer_question(
            question, load_index(), subject=subject, skill_ids=skill_ids, client=client
        )

    def progress(self, user_id: str, subject: str | None = None) -> ProgressResponse:
        skills_by_id = self.bank_for(subject).skills if subject else self.all_skills()
        tracker = self.tracker_for(user_id, subject)

        skills = [
            SkillProgress(
                skill_id=skill_id,
                name_vi=skill.name_vi,
                mastery=round(tracker.mastery(skill_id), 4),
            )
            for skill_id, skill in sorted(skills_by_id.items())
        ]

        attempts, correct = self.store.progress_counts(user_id, subject)

        return ProgressResponse(
            user_id=user_id,
            skills=skills,
            attempts=attempts,
            correct=correct,
        )

    # ------------------------------------------------------------------

    @staticmethod
    def _state_key(session_id: str, item_id: str) -> str:
        """Trạng thái gợi ý riêng cho từng người trên từng bài — xem ``TutorEngine.state_for``."""
        return f"{session_id}:{item_id}"

    def _require_session(self, session_id: str):
        session = self.store.get_session(session_id)
        if session is None:
            raise LookupError(f"Không có phiên {session_id!r}")
        return session

    def _require_item(self, item_id: str) -> Item:
        """Tìm bài theo mã. Tiền tố mã bài (``MAE101-...``) cho biết nó thuộc môn nào."""
        subject = item_id.split("-", 1)[0]
        bank = self.banks.get(subject)
        if bank is None or item_id not in bank.items:
            raise LookupError(f"Không có bài tập {item_id!r}")
        return bank.items[item_id]

    def _last_verification(self, session_id: str, item_id: str) -> VerificationResult | None:
        for row in reversed(self.store.attempts_for_session(session_id)):
            if row["item_id"] == item_id:
                return VerificationResult.model_validate_json(row["verifier_json"])
        return None

    @staticmethod
    def _to_hint(hint: Any) -> HintOut:
        return HintOut(
            level=int(hint.level),
            level_label=HintLevel(hint.level).label_vi,
            text=pretty_math(hint.text),
            source=hint.source,
            error_code=hint.error_code,
            step=hint.step,
        )

    #: Dạng đáp án mong đợi, nói bằng lời — hiện khi bộ chấm không đọc nổi bài làm.
    #:
    #: Ví dụ trong đây dùng CHỮ CÁI làm chỗ trống (``[a, b]``, ``a/b``) chứ không
    #: dùng số cụ thể. Bản đầu viết "nghiệm dạng [2, 1]" và lập tức bị test chống
    #: lộ đáp án bắt: [2, 1] đúng là đáp án của một bài giải hệ trong ngân hàng.
    ANSWER_FORMATS = {
        AnswerType.EXPRESSION: "một biểu thức theo biến của đề, ví dụ dạng a*x**2 + b",
        AnswerType.ANTIDERIVATIVE: "một nguyên hàm, nhớ cộng hằng số C",
        AnswerType.NUMBER: "một con số; phân số viết kiểu a/b",
        AnswerType.SET: "các phần tử cách nhau bởi dấu phẩy",
        AnswerType.MATRIX: "ma trận kiểu [[a, b], [c, d]], vector kiểu [a, b]",
        AnswerType.VECTOR_DIRECTION: "một vector kiểu [a, b]",
        AnswerType.EIGENVECTOR: "một vector kiểu [a, b]",
        AnswerType.LINEAR_SYSTEM: "bộ nghiệm kiểu [a, b]; hệ không giải được thì nói rõ bằng lời",
        AnswerType.BOOLEAN: "một câu khẳng định hoặc phủ định",
        AnswerType.ODE_SOLUTION: "nghiệm kèm hằng số tự do, kiểu C1*f(x)",
        AnswerType.TEXT: "một câu trả lời bằng lời",
    }

    def _verdict(self, verification: Any, item: Item | None = None) -> str:
        """Một câu ngắn nói bài sai ở đâu, KHÔNG nói sai thế nào.

        Cố ý không dùng ``verification.notes``: ghi chú của bộ chấm hay chứa
        chính đáp án ("Đáp án đúng ≈ 0.7745"), đẩy ra client là lộ đáp án ngay
        trước cả khi thang gợi ý kịp làm việc.
        """
        if verification.first_wrong_step is not None:
            return f"Bước {verification.first_wrong_step} chưa đúng. Em xem lại chỗ đó nhé."
        if verification.final_answer_correct is False:
            return "Đáp án cuối chưa đúng. Em thử lại nhé."
        # Không đọc nổi bài làm thì phải nói rõ cần viết thế nào, chứ nói trống
        # "chưa kiểm chứng được" thì sinh viên nộp lại y hệt và lại tắc.
        form = self.ANSWER_FORMATS.get(item.answer_type) if item else None
        if form:
            return f"Thầy chưa đọc được đáp án của em. Em viết dưới dạng {form} nhé."
        return "Chưa kiểm chứng được bài làm — em thử viết rõ đáp án cuối xem."

    def _to_attempt_response(self, response: Any, changes: dict[str, float],
                             item: Item | None = None) -> AttemptResponse:
        verification = response.verification
        return AttemptResponse(
            is_correct=response.is_correct,
            final_answer_correct=verification.final_answer_correct,
            first_wrong_step=verification.first_wrong_step,
            step_results=[
                StepResultOut(step=s.step, ok=s.ok, reason=s.reason)
                for s in verification.step_results
            ],
            error_codes=list(verification.candidate_error_codes),
            message=response.congratulation or self._verdict(verification, item),
            hint=self._to_hint(response.hint) if response.hint else None,
            mastery_changes={k: round(v, 4) for k, v in changes.items()},
        )


# ==========================================================================
# Ứng dụng
# ==========================================================================

def _load_bank(code: str) -> ItemBank:
    """Ngân hàng đề của một môn: đề chép tay CỘNG đề sinh tự động.

    Bộ chọn bài cần nhiều đề mới chọn được bài vừa sức — với 40 đề chép tay thì
    tiêu chí "vừa sức" gần như không có gì để chọn. Đề sinh tự động đã được
    verifier xác nhận từng bài lúc sinh nên dùng thẳng được.
    """
    items = load_items(ITEMS_DIR / f"{code.lower()}.jsonl")
    generated = ITEMS_DIR / f"{code.lower()}_generated.jsonl"
    if generated.exists():
        items += load_items(generated)
    return ItemBank(items, load_skills(SKILLS_DIR / f"{code.lower()}.json"))


def _make_generator(config: AppConfig, code: str, bank: ItemBank) -> HintGenerator:
    """Bộ sinh gợi ý cho một môn.

    Bảng mã lỗi phải ĐẦY ĐỦ của môn — MAE101 gồm cả mã giải tích lẫn mã đại số
    tuyến tính LA.*, thiếu một phần thì gợi ý mức 2 không có câu cảnh báo.
    """
    error_codes = load_course_error_codes(code)
    if not config.llm_hints:
        return HintGenerator(error_codes=error_codes, skills=bank.skills)

    # Nhập muộn: kéo theo kho RAG và tầng model, không cần khi chạy bằng template.
    from src.llm.client import LLMClient
    from src.rag.hint_retriever import default_hint_retriever
    from src.tutor.llm_hints import LLMHintGenerator

    return LLMHintGenerator(
        LLMClient.from_config(config.llm),
        error_codes=error_codes,
        skills=bank.skills,
        retriever=default_hint_retriever(bank.skills),
    )


def build_service(config: AppConfig | None = None, store: Store | None = None) -> TutorService:
    """Dựng dịch vụ cho mọi môn vừa có verifier vừa có ngân hàng đề."""
    config = config or load_config()
    banks: dict[str, ItemBank] = {}
    engines: dict[str, TutorEngine] = {}

    for subject in supported_subjects():
        code = subject.value
        if not (ITEMS_DIR / f"{code.lower()}.jsonl").exists():
            continue
        bank = _load_bank(code)
        # Bảng mã lỗi ĐẦY ĐỦ của môn — MAE101 gồm cả mã giải tích lẫn mã đại số
        # tuyến tính LA.*, thiếu một phần thì gợi ý mức 2 không có câu cảnh báo.
        generator = _make_generator(config, code, bank)
        banks[code] = bank
        engines[code] = TutorEngine(verifier_for(code), generator)

    return TutorService(store or Store(config.database_path), banks, engines,
                        config.subject_default, config)


#: Origin được phép gọi API. Mặc định là web chạy ở máy mình; khi đưa lên
#: tunnel hay máy khác thì thêm qua biến môi trường ``CORS_ORIGINS``
#: (các origin cách nhau bởi dấu phẩy), chứ không mở "*" — mở toàn bộ thì
#: `allow_credentials` mất tác dụng và trình duyệt lại chặn lần nữa.
CORS_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if origin.strip()
]


#: Khoá cho các endpoint quản trị. **Không đặt thì phần quản trị TẮT hoàn toàn.**
#:
#: Cố ý chọn mặc định là tắt chứ không phải mở: dữ liệu ở đó là bài làm của
#: người thật. "Chưa cấu hình" mà lại mở sẵn là kiểu lỗ hổng tệ nhất, vì không
#: ai nhận ra cho tới lúc muộn.
#:
#: Nói thẳng giới hạn của cách này: một khoá dùng chung, không có tài khoản, không
#: phân quyền nhiều mức. Đủ cho một đồ án chạy trong mạng nội bộ, và đủ để chặn
#: người tò mò mở đúng đường link. Đưa ra Internet thật thì phải thay bằng đăng
#: nhập có tài khoản — điều này phải ghi vào mục Hạn chế của báo cáo.
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "").strip()


def create_app(service: TutorService | None = None, mailer: Mailer | None = None) -> FastAPI:
    state: dict[str, Any] = {"service": service}
    mail = mailer or Mailer()
    owns_service = service is None

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if state["service"] is None:
            state["service"] = build_service()
            # Dựng sẵn 70 thẻ kiến thức ở nền (~15 s): người hỏi đầu tiên không phải chờ.
            import threading

            from src.knowledge.cards import all_cards

            threading.Thread(target=all_cards, name="warm-knowledge-cards", daemon=True).start()
        try:
            yield
        finally:
            # App production tự tạo Store thì cũng phải tự đóng. Service được
            # inject trong test hoặc notebook vẫn thuộc quyền sở hữu của caller.
            if owns_service and state["service"] is not None:
                state["service"].store.close()

    app = FastAPI(title="AI Tutor for Mathematics Learning", version="0.2.0", lifespan=lifespan)

    # Web chạy ở cổng 3000, API ở cổng 8000 — với trình duyệt đó là hai origin
    # khác nhau, nên THIẾU ĐOẠN NÀY thì mọi nút bấm trên web đều chết im lặng:
    # giao diện hiện ra đầy đủ nhưng không chức năng nào chạy.
    #
    # Lỗi này lọt qua toàn bộ test vì `TestClient` và `curl` không thi hành
    # same-origin policy — chỉ trình duyệt thật mới chặn. Bài học đáng ghi vào
    # báo cáo: test xanh không thay được một lần mở thật bằng trình duyệt.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def production_headers(request: Request, call_next):
        """Bảo vệ phản hồi API và không cho cache dữ liệu người học."""
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        # Nhiều endpoint nhận user_id qua query hoặc trả tiến độ/bài làm. Tắt
        # cache toàn API tránh proxy dùng nhầm phản hồi của người này cho người khác.
        response.headers["Cache-Control"] = "no-store"
        if request.url.path.startswith("/admin/"):
            response.headers["Pragma"] = "no-cache"
        return response

    def get_service() -> TutorService:
        if state["service"] is None:
            raise HTTPException(503, "Dịch vụ chưa khởi tạo xong")
        return state["service"]

    # ------------------------------------------------------------------

    @app.get("/health")
    def health(service: TutorService = Depends(get_service)) -> dict[str, Any]:
        """Trạng thái hệ thống — kiểm tra ngay trước khi demo."""
        return {
            "status": "ok",
            "subjects": {
                code: {"items": len(bank.items), "skills": len(bank.skills)}
                for code, bank in sorted(service.banks.items())
            },
            "items": sum(len(bank.items) for bank in service.banks.values()),
            "skills": sum(len(bank.skills) for bank in service.banks.values()),
            "database": service.store.stats(),
            # Bản bán phải là true: chưa có SMTP thì quên mật khẩu không tới được ai.
            "email_configured": mail.configured,
        }

    @app.get("/subjects")
    def subjects(service: TutorService = Depends(get_service)) -> list[str]:
        return service.subjects

    # ------------------------------------------------------------------
    # Tài khoản và danh tính
    # ------------------------------------------------------------------

    login_limiter = LoginLimiter()
    signup_limiter = LoginLimiter(limit=10, window_s=60 * 60)

    def identity_optional(
        request: Request,
        x_service_token: str = Header(default=""),
        service: TutorService = Depends(get_service),
    ) -> Identity | None:
        token = request.cookies.get(COOKIE_NAME, "")
        auth = request.headers.get("authorization", "")
        if not token and auth.lower().startswith("bearer "):
            token = auth[7:].strip()
        if token:
            user = service.store.user_for_token(token_digest(token))
            if user is not None:
                return Identity(user["user_id"])
        if SERVICE_TOKEN and x_service_token and secrets.compare_digest(x_service_token, SERVICE_TOKEN):
            return Identity(None, trusted=True)
        return None

    def identity(found: Identity | None = Depends(identity_optional)) -> Identity:
        if found is None:
            raise HTTPException(401, "Bạn cần đăng nhập để tiếp tục")
        return found

    def resolve_user(who: Identity, claimed: str | None) -> str:
        """Tài khoản thì luôn là chính nó — ``user_id`` gửi kèm bị bỏ qua, không
        ai xem được tiến độ người khác bằng cách đổi tham số. Chỉ dịch vụ tin cậy
        mới được nói mình gọi thay ai."""
        if who.user_id:
            return who.user_id
        if not claimed:
            raise HTTPException(422, "Thiếu user_id")
        return claimed

    def require_own_session(who: Identity, service: TutorService, session_id: str) -> None:
        if who.trusted:
            return
        row = service.store.get_session(session_id)
        if row is not None and row["user_id"] != who.user_id:
            raise HTTPException(403, "Phiên luyện tập này không thuộc tài khoản của bạn")

    def client_ip(request: Request) -> str:
        return request.client.host if request.client else "?"

    def open_session(request: Request, response: Response, service: TutorService, user_id: str) -> None:
        token = new_token()
        service.store.add_token(token_digest(token), user_id, SESSION_DAYS * 86400)
        response.set_cookie(
            COOKIE_NAME, token, max_age=SESSION_DAYS * 86400, path="/",
            httponly=True, samesite="lax", secure=request.url.scheme == "https",
        )

    def user_out(row) -> UserOut:
        return UserOut(user_id=row["user_id"], email=row["email"], display_name=row["display_name"],
                       email_verified=bool(row["email_verified"]))

    mail_limiter = LoginLimiter(limit=5, window_s=60 * 60)

    def send_verification(tasks: BackgroundTasks, service: TutorService, user) -> None:
        token = new_token()
        service.store.add_email_token(token_digest(token), user["user_id"], "verify", VERIFY_TTL_S)
        tasks.add_task(
            mail.send, user["email"], "Xác thực email tài khoản Numeris",
            f"Chào {user['display_name']},\n\n"
            f"Bấm vào link dưới đây để xác thực email cho tài khoản Numeris của bạn:\n\n"
            f"{APP_URL}/verify?token={token}\n\n"
            "Link có hiệu lực trong 48 giờ. Nếu bạn không đăng ký Numeris, hãy bỏ qua thư này.\n",
        )

    @app.post("/auth/register", response_model=UserOut, status_code=201)
    def register(body: RegisterRequest, request: Request, response: Response, tasks: BackgroundTasks,
                 service: TutorService = Depends(get_service)) -> UserOut:
        ip_key = f"ip:{client_ip(request)}"
        wait = signup_limiter.retry_after(ip_key)
        if wait:
            raise HTTPException(429, "Đăng ký quá nhiều lần, vui lòng thử lại sau",
                                headers={"Retry-After": str(wait)})
        try:
            email = normalize_email(body.email)
            check_password_rules(body.password)
        except AuthError as exc:
            raise HTTPException(422, str(exc)) from exc
        name = " ".join(body.display_name.split()) or email.split("@")[0]
        try:
            user_id = service.store.create_user(email, name, hash_password(body.password))
        except sqlite3.IntegrityError as exc:
            raise HTTPException(409, "Email này đã được đăng ký — hãy đăng nhập") from exc
        signup_limiter.failed(ip_key)          # đếm số lần đăng ký thành công theo IP
        open_session(request, response, service, user_id)
        user = service.store.user_by_id(user_id)
        send_verification(tasks, service, user)
        return user_out(user)

    @app.post("/auth/login", response_model=UserOut)
    def login(body: LoginRequest, request: Request, response: Response,
              service: TutorService = Depends(get_service)) -> UserOut:
        email = (body.email or "").strip().lower()
        keys = (f"ip:{client_ip(request)}", f"email:{email}")
        wait = login_limiter.retry_after(*keys)
        if wait:
            raise HTTPException(429, f"Sai quá nhiều lần. Thử lại sau {max(1, wait // 60)} phút",
                                headers={"Retry-After": str(wait)})
        user = service.store.user_by_email(email)
        if not verify_or_waste_time(body.password, user["password_hash"] if user else None):
            login_limiter.failed(*keys)
            # Cùng một câu cho "không có email" và "sai mật khẩu": không để lộ
            # email nào đã đăng ký.
            raise HTTPException(401, "Email hoặc mật khẩu không đúng")
        login_limiter.succeeded(*keys)
        open_session(request, response, service, user["user_id"])
        return user_out(user)

    @app.post("/auth/logout", status_code=204)
    def logout(request: Request, service: TutorService = Depends(get_service)) -> Response:
        token = request.cookies.get(COOKIE_NAME)
        if token:
            service.store.delete_token(token_digest(token))
        response = Response(status_code=204)
        response.delete_cookie(COOKIE_NAME, path="/")
        return response

    @app.get("/auth/me", response_model=UserOut)
    def me(who: Identity = Depends(identity), service: TutorService = Depends(get_service)) -> UserOut:
        if not who.user_id:
            raise HTTPException(401, "Bạn cần đăng nhập để tiếp tục")
        return user_out(service.store.user_by_id(who.user_id))

    @app.post("/auth/password", status_code=204)
    def change_password(body: PasswordChangeRequest, request: Request,
                        who: Identity = Depends(identity),
                        service: TutorService = Depends(get_service)) -> Response:
        user = service.store.user_by_id(who.user_id) if who.user_id else None
        if user is None:
            raise HTTPException(401, "Bạn cần đăng nhập để tiếp tục")
        if not verify_password(body.current_password, user["password_hash"]):
            raise HTTPException(403, "Mật khẩu hiện tại không đúng")
        try:
            check_password_rules(body.new_password)
        except AuthError as exc:
            raise HTTPException(422, str(exc)) from exc
        service.store.set_password(user["user_id"], hash_password(body.new_password))
        # Đổi mật khẩu thì đăng xuất mọi thiết bị khác — lý do hay gặp nhất để
        # đổi mật khẩu chính là nghi bị lộ.
        current = request.cookies.get(COOKIE_NAME)
        service.store.delete_tokens_of(user["user_id"], keep=token_digest(current) if current else None)
        return Response(status_code=204)

    @app.post("/auth/verify", response_model=UserOut)
    def verify_email(body: TokenRequest, service: TutorService = Depends(get_service)) -> UserOut:
        user_id = service.store.use_email_token(token_digest(body.token), "verify")
        if user_id is None:
            raise HTTPException(400, "Link xác thực không hợp lệ hoặc đã hết hạn — hãy gửi lại link mới")
        service.store.mark_email_verified(user_id)
        return user_out(service.store.user_by_id(user_id))

    @app.post("/auth/verify/resend", status_code=202)
    def resend_verification(tasks: BackgroundTasks, who: Identity = Depends(identity),
                            service: TutorService = Depends(get_service)) -> dict[str, bool]:
        user = service.store.user_by_id(who.user_id) if who.user_id else None
        if user is None:
            raise HTTPException(401, "Bạn cần đăng nhập để tiếp tục")
        if user["email_verified"]:
            return {"sent": False}
        key = f"verify:{user['user_id']}"
        if mail_limiter.retry_after(key):
            raise HTTPException(429, "Bạn vừa gửi nhiều lần, vui lòng đợi rồi thử lại")
        mail_limiter.failed(key)
        send_verification(tasks, service, user)
        return {"sent": True}

    @app.post("/auth/forgot", status_code=202)
    def forgot_password(body: ForgotRequest, request: Request, tasks: BackgroundTasks,
                        service: TutorService = Depends(get_service)) -> dict[str, bool]:
        email = (body.email or "").strip().lower()
        keys = (f"forgot-ip:{client_ip(request)}", f"forgot:{email}")
        if mail_limiter.retry_after(*keys):
            raise HTTPException(429, "Bạn vừa yêu cầu nhiều lần, vui lòng đợi rồi thử lại")
        mail_limiter.failed(*keys)
        user = service.store.user_by_email(email)
        if user is not None:
            token = new_token()
            service.store.add_email_token(token_digest(token), user["user_id"], "reset", RESET_TTL_S)
            tasks.add_task(
                mail.send, user["email"], "Đặt lại mật khẩu Numeris",
                f"Chào {user['display_name']},\n\n"
                "Có yêu cầu đặt lại mật khẩu cho tài khoản Numeris của bạn. Bấm vào link dưới "
                f"đây để đặt mật khẩu mới:\n\n{APP_URL}/reset?token={token}\n\n"
                "Link có hiệu lực trong 1 giờ và chỉ dùng được một lần. Nếu không phải bạn "
                "yêu cầu, hãy bỏ qua thư này — mật khẩu hiện tại vẫn giữ nguyên.\n",
            )
        # Trả cùng một câu dù email có tồn tại hay không: không để lộ ai đã đăng ký.
        return {"sent": True}

    @app.post("/auth/reset", status_code=204)
    def reset_password(body: ResetRequest, service: TutorService = Depends(get_service)) -> Response:
        try:
            check_password_rules(body.new_password)   # kiểm TRƯỚC để mật khẩu yếu không đốt mất link
        except AuthError as exc:
            raise HTTPException(422, str(exc)) from exc
        user_id = service.store.use_email_token(token_digest(body.token), "reset")
        if user_id is None:
            raise HTTPException(400, "Link đặt lại mật khẩu không hợp lệ hoặc đã hết hạn — hãy yêu cầu link mới")
        service.store.set_password(user_id, hash_password(body.new_password))
        service.store.delete_tokens_of(user_id)        # đăng xuất mọi thiết bị
        service.store.mark_email_verified(user_id)     # mở được thư tức là sở hữu email
        return Response(status_code=204)

    @app.get("/auth/export")
    def export_my_data(who: Identity = Depends(identity),
                       service: TutorService = Depends(get_service)) -> Response:
        if not who.user_id:
            raise HTTPException(401, "Bạn cần đăng nhập để tiếp tục")
        import json

        body = json.dumps(service.store.export_user(who.user_id), ensure_ascii=False, indent=2)
        return Response(body, media_type="application/json", headers={
            "Content-Disposition": 'attachment; filename="numeris-du-lieu-cua-toi.json"'})

    @app.post("/auth/delete", status_code=204)
    def delete_account(body: DeleteAccountRequest, who: Identity = Depends(identity),
                       service: TutorService = Depends(get_service)) -> Response:
        user = service.store.user_by_id(who.user_id) if who.user_id else None
        if user is None:
            raise HTTPException(401, "Bạn cần đăng nhập để tiếp tục")
        if not verify_password(body.password, user["password_hash"]):
            raise HTTPException(403, "Mật khẩu không đúng")
        service.store.delete_user(user["user_id"])
        response = Response(status_code=204)
        response.delete_cookie(COOKIE_NAME, path="/")
        return response

    # ------------------------------------------------------------------

    @app.post("/session/start", response_model=StartSessionResponse)
    def start_session(
        request: StartSessionRequest,
        who: Identity = Depends(identity),
        service: TutorService = Depends(get_service),
    ) -> StartSessionResponse:
        try:
            return service.start_session(resolve_user(who, request.user_id), request.subject)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.get("/item/next", response_model=PublicItem)
    def next_item(
        user_id: str | None = None,
        subject: str | None = None,
        chapter: str | None = None,
        skill: str | None = None,
        topic: str | None = None,
        who: Identity = Depends(identity),
        service: TutorService = Depends(get_service),
    ) -> PublicItem:
        try:
            item = service.pick_item(resolve_user(who, user_id), subject, chapter, skill, topic)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc
        if item is None:
            raise HTTPException(404, "Ngân hàng đề trống")
        return PublicItem.of(item, service.bank_for(item.subject.value))

    @app.get("/syllabus", response_model=SyllabusResponse)
    def syllabus(
        subject: str | None = None,
        user_id: str | None = None,
        who: Identity | None = Depends(identity_optional),
        service: TutorService = Depends(get_service),
    ) -> SyllabusResponse:
        """Cây môn → chương → bài → dạng bài, để người học chọn dần cho hẹp.

        ``user_id`` là tuỳ chọn: có thì kèm mức thành thạo từng nhánh, không có
        thì vẫn trả được cây — trang chọn môn cần cây trước khi có phiên.
        """
        # Cây môn học là công khai; mức thành thạo kèm theo chỉ của chính mình.
        if who is None:
            user_id = None
        elif who.user_id:
            user_id = who.user_id
        try:
            return service.syllabus(user_id, subject)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.post("/attempt", response_model=AttemptResponse)
    def attempt(
        request: AttemptRequest,
        who: Identity = Depends(identity),
        service: TutorService = Depends(get_service),
    ) -> AttemptResponse:
        require_own_session(who, service, request.session_id)
        try:
            return service.submit(request)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.post("/hint", response_model=HintOut)
    def hint(request: HintRequest, who: Identity = Depends(identity),
             service: TutorService = Depends(get_service)) -> HintOut:
        require_own_session(who, service, request.session_id)
        try:
            return service.request_hint(request)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.post("/ask", response_model=AskResponse)
    def ask(request: AskRequest, who: Identity = Depends(identity),
            service: TutorService = Depends(get_service)) -> AskResponse:
        """Hỏi đáp lý thuyết dựa trên giáo trình.

        Không tìm được đoạn nào đủ liên quan thì trả lời "ngoài phạm vi" chứ
        không đoán — câu hỏi ngoài 4 môn không được nhận một đoạn văn nghe có vẻ
        đúng.
        """
        if not request.question.strip():
            raise HTTPException(422, "Câu hỏi trống")
        result = service.ask(request.question, request.subject, request.chapter)
        return AskResponse(answer=pretty_math(result.text), sources=result.sources,
                           in_scope=result.in_scope, used_llm=result.used_llm)

    # ------------------------------------------------------------------
    # Thẻ kiến thức — công khai: tra công thức không cần đăng nhập
    # ------------------------------------------------------------------

    @app.get("/knowledge")
    def knowledge_index(subject: str | None = None) -> list[dict[str, Any]]:
        from src.knowledge.cards import SUBJECTS, all_cards

        if subject and subject not in SUBJECTS:
            raise HTTPException(404, f"Môn {subject} chưa được hỗ trợ")
        return [{"skill_id": c.skill_id, "subject": c.subject, "chapter_vi": c.chapter_vi,
                 "name_vi": c.name_vi, "name_en": c.name_en, "formula": c.formulas[0] if c.formulas else "",
                 "item_count": c.item_count} for c in all_cards(subject)]

    @app.get("/knowledge/match")
    def knowledge_match(q: Annotated[str, Field(min_length=1, max_length=500)],
                        subject: str | None = None) -> list[dict[str, Any]]:
        from src.knowledge.cards import match_cards

        return [card.to_dict() for card in match_cards(q, subject)]

    @app.get("/knowledge/{skill_id}")
    def knowledge_card(skill_id: str) -> dict[str, Any]:
        from src.knowledge.cards import card_by_id

        card = card_by_id(skill_id)
        if card is None:
            raise HTTPException(404, "Không có thẻ kiến thức này")
        return card.to_dict()

    # ------------------------------------------------------------------
    # Quản trị — dành cho giảng viên, không phải cho sinh viên
    # ------------------------------------------------------------------

    def require_admin(x_admin_token: str = Header(default="")) -> None:
        """Chặn ở TẦNG SERVER, không phải ở giao diện.

        Phía web có chuyển đổi "sinh viên / quản trị", nhưng đó chỉ là điều
        hướng cho tiện — bất kỳ ai cũng sửa được biến trong trình duyệt. Chỗ
        duy nhất chặn được thật là ngay đây.
        """
        if not ADMIN_TOKEN:
            raise HTTPException(
                403,
                "Phần quản trị đang tắt. Đặt biến môi trường ADMIN_TOKEN rồi khởi động lại API.",
            )
        # compare_digest: so sánh thời gian hằng, không để lộ khoá qua thời gian phản hồi.
        if not secrets.compare_digest(x_admin_token, ADMIN_TOKEN):
            raise HTTPException(401, "Khoá quản trị không đúng")

    @app.get("/admin/enabled")
    def admin_enabled() -> dict[str, bool]:
        """Phần quản trị có được bật hay không — KHÔNG cần khoá.

        Giao diện cần biết để ẩn hẳn mục quản trị khi chưa cấu hình, thay vì
        hiện ra rồi bắt người dùng bấm vào mới nhận lỗi 403.
        """
        return {"enabled": bool(ADMIN_TOKEN)}

    @app.get("/admin/overview", response_model=AdminOverview)
    def admin_overview(
        _: None = Depends(require_admin), service: TutorService = Depends(get_service)
    ) -> AdminOverview:
        store = service.store
        return AdminOverview(
            totals=store.stats(),
            subjects=[SubjectStats(**row) for row in store.per_subject_stats()],
            top_error_codes=[ErrorCodeCount(**row) for row in store.top_error_codes()],
            hint_levels=[HintLevelCount(**row) for row in store.hint_level_usage()],
            learners=[LearnerRow(**row) for row in store.learners()],
            bank={code: len(bank.items) for code, bank in sorted(service.banks.items())},
        )

    @app.get("/admin/attempts")
    def admin_attempts(
        limit: int = 50,
        subject: str | None = None,
        _: None = Depends(require_admin),
        service: TutorService = Depends(get_service),
    ) -> list[dict]:
        return service.store.recent_attempts(min(max(limit, 1), 500), subject)

    @app.get("/admin/export.csv")
    def admin_export(
        subject: str | None = None,
        _: None = Depends(require_admin),
        service: TutorService = Depends(get_service),
    ) -> Response:
        """Xuất bài làm ra CSV để phân tích ngoài hệ thống.

        Có endpoint này vì phần đánh giá của đồ án cần dữ liệu thô: đây là
        đường ngắn nhất từ log người dùng thật sang `scripts/label_real_errors.py`.
        """
        # Xuất dữ liệu là đường đưa log người dùng sang bước gán nhãn/đánh giá.
        # Không được âm thầm cắt 500 dòng như trang xem nhanh của quản trị viên.
        rows = service.store.recent_attempts(None, subject)
        buffer = io.StringIO()
        writer = csv.DictWriter(
            buffer,
            fieldnames=["attempt_id", "user_id", "subject", "item_id", "answer",
                        "verdict", "error_codes", "created_at"],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({**row, "error_codes": " ".join(row["error_codes"])})
        # utf-8-sig: thiếu BOM thì Excel trên Windows mở ra tiếng Việt thành ký tự lạ.
        return Response(
            content=buffer.getvalue().encode("utf-8-sig"),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="attempts.csv"'},
        )

    @app.get("/progress", response_model=ProgressResponse)
    def progress(
        user_id: str | None = None,
        subject: str | None = None,
        who: Identity = Depends(identity),
        service: TutorService = Depends(get_service),
    ) -> ProgressResponse:
        try:
            return service.progress(resolve_user(who, user_id), subject)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc

    return app


app = create_app()
