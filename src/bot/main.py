"""Bot Telegram — chạy: python -m src.bot.main

Cần biến môi trường ``TELEGRAM_TOKEN`` (lấy từ @BotFather) và một API đang chạy
(``API_URL``, mặc định http://localhost:8000).

Tệp này cố ý mỏng: nó chỉ nối lệnh Telegram với ``Dialog`` và đổ văn bản ra. Mọi
thứ đáng test nằm trong ``dialog.py``, nên đây không có gì để hỏng ngoài việc
thiếu token.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.bot.client import TutorApi  # noqa: E402
from src.bot.dialog import Dialog, Reply  # noqa: E402

LOG = logging.getLogger("bot")


def build_dialog() -> Dialog:
    return Dialog(TutorApi(base_url=os.environ.get("API_URL", "http://localhost:8000")))


async def run() -> None:
    from aiogram import Bot, Dispatcher, F
    from aiogram.filters import Command, CommandStart
    from aiogram.types import Message

    token = os.environ.get("TELEGRAM_TOKEN", "").strip()
    if not token:
        raise SystemExit(
            "Thiếu TELEGRAM_TOKEN. Lấy token ở @BotFather rồi đặt biến môi trường:\n"
            "  set TELEGRAM_TOKEN=123456:ABC...   (Windows)\n"
            "  export TELEGRAM_TOKEN=123456:ABC... (Linux/macOS)"
        )

    dialog = build_dialog()
    bot = Bot(token)
    dispatcher = Dispatcher()

    def who(message: Message) -> tuple[int, str]:
        """Danh tính người học: ưu tiên username, không có thì dùng id Telegram."""
        user = message.from_user
        name = (user.username if user and user.username else str(user.id if user else message.chat.id))
        return message.chat.id, f"tg:{name}"

    async def send(message: Message, reply: Reply) -> None:
        await message.answer(reply.text)

    @dispatcher.message(CommandStart())
    async def handle_start(message: Message) -> None:
        await send(message, await dialog.start(*who(message)))

    @dispatcher.message(Command("subject"))
    async def handle_subject(message: Message) -> None:
        await send(message, await dialog.choose_subject(*who(message)))

    for code in ("mae101", "mad101", "mai391", "mas291"):
        @dispatcher.message(Command(code))
        async def handle_pick(message: Message, subject: str = code.upper()) -> None:
            await send(message, await dialog.set_subject(*who(message), subject))

    @dispatcher.message(Command("practice"))
    async def handle_practice(message: Message) -> None:
        await send(message, await dialog.practice(*who(message)))

    @dispatcher.message(Command("hint"))
    async def handle_hint(message: Message) -> None:
        await send(message, await dialog.hint(*who(message)))

    @dispatcher.message(Command("solution"))
    async def handle_solution(message: Message) -> None:
        await send(message, await dialog.hint(*who(message), asked_for_solution=True))

    @dispatcher.message(Command("explain"))
    async def handle_explain(message: Message) -> None:
        question = (message.text or "").partition(" ")[2]
        await send(message, await dialog.explain(*who(message), question))

    @dispatcher.message(Command("progress"))
    async def handle_progress(message: Message) -> None:
        await send(message, await dialog.progress(*who(message)))

    @dispatcher.message(Command("stop"))
    async def handle_stop(message: Message) -> None:
        await send(message, await dialog.stop(message.chat.id))

    @dispatcher.message(F.text & ~F.text.startswith("/"))
    async def handle_answer(message: Message) -> None:
        await send(message, await dialog.answer(*who(message), message.text or ""))

    health = await dialog.api.health()
    LOG.info("API sẵn sàng: %s đề, %s kỹ năng", health.get("items"), health.get("skills"))
    await dispatcher.start_polling(bot)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    asyncio.run(run())


if __name__ == "__main__":
    main()
