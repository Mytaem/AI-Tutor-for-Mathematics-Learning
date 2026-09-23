"""Test luồng hội thoại của bot Telegram — chạy offline, không cần token.

Luồng hội thoại là chỗ dễ hỏng âm thầm: người dùng gõ đáp án khi chưa có bài,
xin gợi ý khi chưa chọn môn, API chết giữa chừng... Nếu bot im lặng hoặc văng
lỗi thì người thật bỏ đi, mà log không ghi gì cả.

API được thay bằng bản giả ghi lại lời gọi, nên test kiểm được cả điều quan
trọng nhất: **bot không tự chấm bài** — mọi kết luận đúng/sai đều phải đi qua
endpoint ``/attempt``.
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.bot.client import ApiError  # noqa: E402
from src.bot.dialog import Dialog  # noqa: E402

CHAT = 100
USER = "tg:sv001"


def run(coroutine):
    """Chạy một coroutine trong test đồng bộ.

    Cố ý không dùng pytest-asyncio: cả bộ test hiện chạy được mà không cần cài
    thêm gì, thêm một plugin chỉ để bốn chục dòng test bot là không đáng.
    """
    return asyncio.run(coroutine)

ITEM = {"item_id": "MAE101-INT-001", "statement_vi": "Tính nguyên hàm: ∫ x² dx",
        "skills": ["MAE.INT.BASIC"], "difficulty": 0.2, "answer_type": "antiderivative"}


@dataclass
class FakeApi:
    """API giả: trả kịch bản dựng sẵn, ghi lại mọi lời gọi."""

    correct: bool = False
    calls: list[tuple[str, tuple]] = field(default_factory=list)
    fail_with: str | None = None

    def _record(self, name: str, *args):
        self.calls.append((name, args))
        if self.fail_with:
            raise ApiError(self.fail_with)

    async def subjects(self):
        self._record("subjects")
        return ["MAE101", "MAD101"]

    async def start_session(self, user_id, subject):
        self._record("start_session", user_id, subject)
        return {"session_id": "s1", "user_id": user_id, "subject": subject,
                "first_item": ITEM, "placement_mode": True, "placement_remaining": 6}

    async def next_item(self, user_id, subject):
        self._record("next_item", user_id, subject)
        return ITEM

    async def submit(self, session_id, item_id, answer):
        self._record("submit", session_id, item_id, answer)
        if self.correct:
            return {"is_correct": True, "message": "Chính xác!", "hint": None,
                    "first_wrong_step": None}
        return {"is_correct": False, "message": "Đáp án cuối chưa đúng.", "first_wrong_step": 2,
                "hint": {"level": 2, "level_label": "Cảnh báo bẫy", "text": "Nhớ cộng hằng số C.",
                         "source": "taxonomy"}}

    async def hint(self, session_id, item_id, asked_for_solution=False):
        self._record("hint", session_id, item_id, asked_for_solution)
        return {"level": 3, "level_label": "Chỉ bước sai", "text": "Em xem lại bước 2.",
                "source": "template"}

    async def progress(self, user_id, subject):
        self._record("progress", user_id, subject)
        return {"user_id": user_id, "attempts": 4, "correct": 3, "skills": [
            {"skill_id": "MAE.INT.BASIC", "name_vi": "Nguyên hàm cơ bản", "mastery": 0.8},
            {"skill_id": "MAE.INT.SUBST", "name_vi": "Đổi biến", "mastery": 0.2},
        ]}

    async def health(self):
        self._record("health")
        return {"items": 10, "skills": 3}


@pytest.fixture
def api() -> FakeApi:
    return FakeApi()


@pytest.fixture
def dialog(api: FakeApi) -> Dialog:
    return Dialog(api)  # type: ignore[arg-type]


def pick_subject(dialog: Dialog) -> None:
    run(dialog.set_subject(CHAT, USER, "MAE101"))


class TestHappyPath:
    def test_start_huong_dan_chon_mon(self, dialog: Dialog) -> None:
        reply = run(dialog.start(CHAT, USER))
        assert "/subject" in reply.text

    def test_chon_mon_thi_nhan_luon_bai_dau(self, dialog: Dialog, api: FakeApi) -> None:
        reply = run(dialog.set_subject(CHAT, USER, "MAE101"))
        assert ITEM["statement_vi"] in reply.text
        assert "ĐO ĐẦU VÀO" in reply.text, "phải nói rõ đây là bài đo, không phải bài luyện"
        assert api.calls[0][0] == "start_session"

    def test_lam_dung_thi_khen_va_moi_bai_moi(self, dialog: Dialog, api: FakeApi) -> None:
        pick_subject(dialog)
        api.correct = True
        reply = run(dialog.answer(CHAT, USER, "x**3/3 + C"))
        assert "✅" in reply.text and "/practice" in reply.text

    def test_lam_sai_thi_kem_goi_y(self, dialog: Dialog) -> None:
        pick_subject(dialog)
        reply = run(dialog.answer(CHAT, USER, "x**3/3"))
        assert "❌" in reply.text
        assert "Nhớ cộng hằng số C." in reply.text
        assert "bước 2" in reply.text

    def test_xin_goi_y_them(self, dialog: Dialog, api: FakeApi) -> None:
        pick_subject(dialog)
        reply = run(dialog.hint(CHAT, USER))
        assert "Mức 3" in reply.text
        assert api.calls[-1] == ("hint", ("s1", ITEM["item_id"], False))

    def test_xem_tien_do_hien_ky_nang_yeu_truoc(self, dialog: Dialog) -> None:
        pick_subject(dialog)
        reply = run(dialog.progress(CHAT, USER))
        assert reply.text.index("Đổi biến") < reply.text.index("Nguyên hàm cơ bản")
        assert "75%" in reply.text  # 3/4 lượt đúng


class TestGuards:
    def test_go_dap_an_khi_chua_co_bai(self, dialog: Dialog, api: FakeApi) -> None:
        reply = run(dialog.answer(CHAT, USER, "42"))
        assert "/practice" in reply.text
        assert api.calls == [], "không được gọi API khi chưa có bài nào đang làm"

    def test_xin_bai_khi_chua_chon_mon(self, dialog: Dialog) -> None:
        assert "/subject" in run(dialog.practice(CHAT, USER)).text

    def test_api_chet_thi_bao_ro_chu_khong_im_lang(self, dialog: Dialog, api: FakeApi) -> None:
        pick_subject(dialog)
        api.fail_with = "Không gọi được API: timeout"
        reply = run(dialog.answer(CHAT, USER, "x**3/3 + C"))
        assert "timeout" in reply.text

    def test_stop_xoa_trang_thai(self, dialog: Dialog) -> None:
        pick_subject(dialog)
        run(dialog.stop(CHAT))
        assert CHAT not in dialog.states

    def test_hai_nguoi_khong_dung_chung_trang_thai(self, dialog: Dialog) -> None:
        """Hai chat khác nhau là hai người khác nhau — lẫn trạng thái là lộ bài của nhau."""
        run(dialog.set_subject(CHAT, USER, "MAE101"))
        run(dialog.set_subject(CHAT + 1, "tg:sv002", "MAD101"))
        assert dialog.states[CHAT].subject == "MAE101"
        assert dialog.states[CHAT + 1].subject == "MAD101"


class TestBotDoesNotGrade:
    def test_moi_ket_luan_deu_di_qua_api(self, dialog: Dialog, api: FakeApi) -> None:
        """Bot không được tự chấm: câu trả lời đúng hay sai phải do /attempt quyết."""
        pick_subject(dialog)
        run(dialog.answer(CHAT, USER, "x**3/3 + C"))
        assert any(name == "submit" for name, _ in api.calls)

    def test_bot_khong_giu_dap_an(self, dialog: Dialog) -> None:
        pick_subject(dialog)
        state = dialog.states[CHAT]
        assert not hasattr(state, "answer")
        assert "answer" not in vars(state)
