"""Luồng hội thoại của bot, tách hẳn khỏi thư viện Telegram.

Vì sao tách: ``aiogram`` đòi token, mạng và vòng lặp polling, nên nếu nhét logic
vào handler thì không test được gì ngoài việc "bot khởi động không lỗi". Ở đây
mỗi hành động là một hàm thuần nhận trạng thái và trả về **văn bản cần gửi**,
nên test chạy được toàn bộ kịch bản hội thoại mà không cần Telegram lẫn server.

Quy ước: mọi hàm trả về ``Reply`` gồm văn bản và danh sách nút. Handler chỉ việc
đổ ra Telegram.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.bot.client import ApiError, TutorApi

SUBJECT_NAMES = {
    "MAE101": "Toán kỹ thuật (giải tích, đại số tuyến tính)",
    "MAD101": "Toán rời rạc (logic, tổ hợp, đồ thị)",
    "MAI391": "Toán cho học máy (ma trận, gradient, PCA)",
    "MAS291": "Xác suất thống kê",
}

WELCOME = (
    "Chào em! Đây là gia sư toán có kiểm chứng — bài làm được chấm bằng SymPy và "
    "mô phỏng, không phải do mô hình ngôn ngữ đoán.\n\n"
    "Lệnh dùng được:\n"
    "/subject — chọn môn\n"
    "/practice — nhận bài tập\n"
    "/hint — xin gợi ý (cho dần từng mức)\n"
    "/explain <khái niệm> — hỏi lý thuyết, có trích nguồn giáo trình\n"
    "/progress — xem mức thành thạo\n"
    "/stop — kết thúc\n\n"
    "Chọn môn trước nhé: /subject"
)


@dataclass
class Reply:
    """Một lượt trả lời: văn bản, kèm các nút bấm nếu có."""

    text: str
    buttons: list[str] = field(default_factory=list)


@dataclass
class ChatState:
    """Trạng thái một cuộc trò chuyện. Khoá theo chat_id của Telegram."""

    user_id: str
    subject: str | None = None
    session_id: str | None = None
    item_id: str | None = None
    statement: str | None = None
    hint_level: int | None = None


class Dialog:
    """Toàn bộ nghiệp vụ hội thoại của bot."""

    def __init__(self, api: TutorApi | None = None) -> None:
        self.api = api or TutorApi()
        self.states: dict[int, ChatState] = {}

    def state_for(self, chat_id: int, user_id: str) -> ChatState:
        if chat_id not in self.states:
            self.states[chat_id] = ChatState(user_id=user_id)
        return self.states[chat_id]

    # ------------------------------------------------------------------

    async def start(self, chat_id: int, user_id: str) -> Reply:
        self.state_for(chat_id, user_id)
        return Reply(WELCOME)

    async def choose_subject(self, chat_id: int, user_id: str) -> Reply:
        self.state_for(chat_id, user_id)
        try:
            subjects = await self.api.subjects()
        except ApiError as exc:
            return Reply(f"Hệ thống đang bận: {exc}")
        lines = [f"/{code.lower()} — {SUBJECT_NAMES.get(code, code)}" for code in subjects]
        return Reply("Em muốn luyện môn nào?\n" + "\n".join(lines), buttons=subjects)

    async def set_subject(self, chat_id: int, user_id: str, subject: str) -> Reply:
        state = self.state_for(chat_id, user_id)
        try:
            session = await self.api.start_session(state.user_id, subject)
        except ApiError as exc:
            return Reply(f"Không mở được phiên: {exc}")

        state.subject = session["subject"]
        state.session_id = session["session_id"]
        note = ""
        if session.get("placement_mode"):
            note = (f"\n\n(Vài câu đầu là bài ĐO ĐẦU VÀO, còn {session['placement_remaining']} câu. "
                    "Khó dễ lẫn lộn là bình thường, em cứ làm hết sức.)")
        item = session.get("first_item")
        if item:
            return self._present(state, item, prefix=f"Đã chọn {state.subject}.{note}\n\n")
        return Reply(f"Đã chọn {state.subject}.{note} Gõ /practice để nhận bài.")

    async def practice(self, chat_id: int, user_id: str) -> Reply:
        state = self.state_for(chat_id, user_id)
        if not state.subject or not state.session_id:
            return Reply("Em chọn môn trước đã nhé: /subject")
        try:
            item = await self.api.next_item(state.user_id, state.subject)
        except ApiError as exc:
            return Reply(f"Chưa lấy được bài: {exc}")
        return self._present(state, item)

    def _present(self, state: ChatState, item: dict, prefix: str = "") -> Reply:
        state.item_id = item["item_id"]
        state.statement = item["statement_vi"]
        state.hint_level = None
        return Reply(
            f"{prefix}📝 {item['statement_vi']}\n\n"
            f"Em gõ đáp án vào đây. Cần gợi ý thì /hint."
        )

    async def answer(self, chat_id: int, user_id: str, text: str) -> Reply:
        state = self.state_for(chat_id, user_id)
        if not state.item_id or not state.session_id:
            return Reply("Chưa có bài nào đang làm. Gõ /practice để nhận bài nhé.")

        try:
            result = await self.api.submit(state.session_id, state.item_id, text.strip())
        except ApiError as exc:
            return Reply(f"Chưa chấm được: {exc}")

        if result["is_correct"]:
            state.item_id = None
            return Reply(f"✅ {result['message']}\n\nGõ /practice để làm bài tiếp theo.")

        lines = [f"❌ {result['message']}"]
        if result.get("first_wrong_step") is not None:
            lines.append(f"Bước sai đầu tiên: bước {result['first_wrong_step']}.")
        hint = result.get("hint")
        if hint:
            state.hint_level = hint["level"]
            lines.append(f"\n💡 Gợi ý (mức {hint['level']} — {hint['level_label']}):\n{hint['text']}")
        lines.append("\nEm thử lại, hoặc /hint để được gợi ý thêm.")
        return Reply("\n".join(lines))

    async def hint(self, chat_id: int, user_id: str, asked_for_solution: bool = False) -> Reply:
        state = self.state_for(chat_id, user_id)
        if not state.item_id or not state.session_id:
            return Reply("Chưa có bài nào đang làm. Gõ /practice nhé.")
        try:
            hint = await self.api.hint(state.session_id, state.item_id, asked_for_solution)
        except ApiError as exc:
            return Reply(f"Chưa lấy được gợi ý: {exc}")

        state.hint_level = hint["level"]
        tail = "" if hint["level"] >= 5 else "\n\n(Vẫn chưa rõ thì /hint tiếp nhé.)"
        return Reply(f"💡 Mức {hint['level']} — {hint['level_label']}:\n{hint['text']}{tail}")

    async def progress(self, chat_id: int, user_id: str) -> Reply:
        state = self.state_for(chat_id, user_id)
        if not state.subject:
            return Reply("Em chọn môn trước đã: /subject")
        try:
            data = await self.api.progress(state.user_id, state.subject)
        except ApiError as exc:
            return Reply(f"Chưa xem được tiến độ: {exc}")

        skills = sorted(data["skills"], key=lambda s: s["mastery"])
        weakest = skills[:5]
        accuracy = data["correct"] / data["attempts"] if data["attempts"] else 0.0
        lines = [
            f"📊 {state.subject}: {data['attempts']} lượt, đúng {data['correct']} "
            f"({accuracy:.0%})",
            "",
            "Kỹ năng cần luyện thêm:",
        ]
        lines += [f"{_bar(s['mastery'])} {s['mastery']:.0%} — {s['name_vi']}" for s in weakest]
        return Reply("\n".join(lines))

    async def explain(self, chat_id: int, user_id: str, question: str) -> Reply:
        """Hỏi lý thuyết — không cần đang làm bài, không cần chọn môn.

        Đã chọn môn thì thu hẹp về giáo trình môn đó; chưa chọn thì tìm cả bốn môn.
        """
        state = self.state_for(chat_id, user_id)
        if not question.strip():
            return Reply("Em gõ kèm câu hỏi nhé, ví dụ: /explain chu trình Euler là gì")
        try:
            result = await self.api.ask(question.strip(), state.subject)
        except ApiError as exc:
            return Reply(f"Chưa tra được: {exc}")

        lines = [result["answer"].strip()]
        if result.get("sources"):
            lines.append("\n📚 Nguồn:")
            lines += [f"• {source}" for source in result["sources"][:3]]
        return Reply("\n".join(lines))

    async def stop(self, chat_id: int) -> Reply:
        self.states.pop(chat_id, None)
        return Reply("Đã kết thúc phiên. Quay lại lúc nào cũng được — /start.")


def _bar(value: float, width: int = 10) -> str:
    """Thanh tiến độ bằng ký tự — Telegram không có biểu đồ trong tin nhắn thường."""
    filled = round(min(max(value, 0.0), 1.0) * width)
    return "▰" * filled + "▱" * (width - filled)
