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

from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.core.config import AppConfig, load_config
from src.core.itembank import ERRORS_DIR, ITEMS_DIR, ItemBank, load_error_codes
from src.core.schema import Item, Submission, VerificationResult
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
from src.api.db import Store


# ==========================================================================
# Mô hình dữ liệu cho HTTP
# ==========================================================================

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

    @classmethod
    def of(cls, item: Item) -> PublicItem:
        return cls(
            item_id=item.item_id,
            subject=item.subject.value,
            skills=list(item.skills),
            statement_vi=item.statement_vi,
            statement_latex=item.statement_latex,
            answer_type=item.answer_type.value,
            variable=item.variable,
            bounds=item.bounds,
            difficulty=item.difficulty,
        )


class StartSessionRequest(BaseModel):
    user_id: str = Field(min_length=1)
    subject: str = "MAE101"


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
    session_id: str
    item_id: str
    final_answer: str | None = None
    steps: list[str] = Field(default_factory=list)


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
    session_id: str
    item_id: str
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
    ) -> None:
        self.store = store
        self.banks = banks
        self.engines = engines
        self.default_subject = default_subject

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
        return make_tracker(skills, self.store.load_mastery(user_id))

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
            first_item=PublicItem.of(item) if item else None,
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

    def pick_item(self, user_id: str, subject: str | None = None) -> Item | None:
        subject = subject or self.default_subject
        bank = self.bank_for(subject)
        items = list(bank.items.values())
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

        changes = tracker.observe(item.skills, response.is_correct)

        if response.is_correct:
            # Làm đúng bài đổi biến thì đương nhiên đã nắm quy tắc hàm hợp.
            # Lan truyền ngược lên tiên quyết giúp một câu trả lời cho thông tin
            # về nhiều kỹ năng (đo được: 6 câu đúng cập nhật 10/13 kỹ năng).
            changes.update(propagate_prerequisites(tracker, bank.skills, item.skills))

        self.store.save_mastery(user_id, changes)

        if response.hint is not None:
            self.store.record_hint(request.session_id, item.item_id, response.hint)

        result = self._to_attempt_response(response, changes)
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

        query = "SELECT COUNT(*) AS total, SUM(is_correct) AS correct FROM attempts WHERE user_id = ?"
        params: tuple = (user_id,)
        if subject:
            query += " AND subject = ?"
            params += (subject,)
        rows = self.store._connection.execute(query, params).fetchone()  # noqa: SLF001

        return ProgressResponse(
            user_id=user_id,
            skills=skills,
            attempts=rows["total"] or 0,
            correct=rows["correct"] or 0,
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
            text=hint.text,
            source=hint.source,
            error_code=hint.error_code,
            step=hint.step,
        )

    def _to_attempt_response(self, response: Any, changes: dict[str, float]) -> AttemptResponse:
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
            message=response.congratulation or "",
            hint=self._to_hint(response.hint) if response.hint else None,
            mastery_changes={k: round(v, 4) for k, v in changes.items()},
        )


# ==========================================================================
# Ứng dụng
# ==========================================================================

def build_service(config: AppConfig | None = None, store: Store | None = None) -> TutorService:
    """Dựng dịch vụ cho mọi môn vừa có verifier vừa có ngân hàng đề."""
    config = config or load_config()
    banks: dict[str, ItemBank] = {}
    engines: dict[str, TutorEngine] = {}

    for subject in supported_subjects():
        code = subject.value
        if not (ITEMS_DIR / f"{code.lower()}.jsonl").exists():
            continue
        bank = ItemBank.load(code)
        errors_path = ERRORS_DIR / f"{code.lower()}.json"
        generator = HintGenerator(
            error_codes=load_error_codes(errors_path) if errors_path.exists() else {},
            skills=bank.skills,
        )
        banks[code] = bank
        engines[code] = TutorEngine(verifier_for(code), generator)

    return TutorService(store or Store(config.database_path), banks, engines, config.subject_default)


def create_app(service: TutorService | None = None) -> FastAPI:
    state: dict[str, Any] = {"service": service}

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if state["service"] is None:
            state["service"] = build_service()
        yield

    app = FastAPI(title="AI Tutor for Mathematics Learning", version="0.2.0", lifespan=lifespan)

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
        }

    @app.get("/subjects")
    def subjects(service: TutorService = Depends(get_service)) -> list[str]:
        return service.subjects

    @app.post("/session/start", response_model=StartSessionResponse)
    def start_session(
        request: StartSessionRequest, service: TutorService = Depends(get_service)
    ) -> StartSessionResponse:
        try:
            return service.start_session(request.user_id, request.subject)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.get("/item/next", response_model=PublicItem)
    def next_item(
        user_id: str, subject: str | None = None, service: TutorService = Depends(get_service)
    ) -> PublicItem:
        try:
            item = service.pick_item(user_id, subject)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc
        if item is None:
            raise HTTPException(404, "Ngân hàng đề trống")
        return PublicItem.of(item)

    @app.post("/attempt", response_model=AttemptResponse)
    def attempt(
        request: AttemptRequest, service: TutorService = Depends(get_service)
    ) -> AttemptResponse:
        try:
            return service.submit(request)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.post("/hint", response_model=HintOut)
    def hint(request: HintRequest, service: TutorService = Depends(get_service)) -> HintOut:
        try:
            return service.request_hint(request)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.get("/progress", response_model=ProgressResponse)
    def progress(
        user_id: str, subject: str | None = None, service: TutorService = Depends(get_service)
    ) -> ProgressResponse:
        try:
            return service.progress(user_id, subject)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc

    return app


app = create_app()
