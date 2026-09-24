"""Lớp gọi API cho bot Telegram.

Bot là **client mỏng**: không chấm bài, không giữ đáp án, không tự quyết mức gợi
ý. Mọi quyết định nằm ở FastAPI, y như web. Nhờ vậy hai kênh cho cùng một kết
quả trên cùng một bài làm, và log của chúng nằm chung một bảng — phân tích ở
Phần L mới gộp được.

Tách riêng khỏi ``handlers.py`` để test được toàn bộ luồng hội thoại mà không
cần token Telegram lẫn server đang chạy: test chỉ việc thay lớp này bằng một
bản giả.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


class ApiError(RuntimeError):
    """API trả lỗi — bot phải nói cho người dùng biết, không được im lặng."""


@dataclass
class TutorApi:
    base_url: str = "http://localhost:8000"
    timeout: float = 120.0        # model chạy CPU có thể mất hàng chục giây

    async def _call(self, method: str, path: str, **kwargs) -> Any:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout) as client:
            try:
                response = await client.request(method, path, **kwargs)
            except httpx.HTTPError as exc:
                raise ApiError(f"Không gọi được API: {exc}") from exc

        if response.status_code >= 400:
            detail = ""
            try:
                detail = response.json().get("detail", "")
            except Exception:
                detail = response.text[:200]
            raise ApiError(detail or f"API trả lỗi {response.status_code}")
        return response.json()

    # ------------------------------------------------------------------

    async def health(self) -> dict:
        return await self._call("GET", "/health")

    async def subjects(self) -> list[str]:
        return await self._call("GET", "/subjects")

    async def start_session(self, user_id: str, subject: str) -> dict:
        return await self._call("POST", "/session/start",
                                json={"user_id": user_id, "subject": subject})

    async def next_item(self, user_id: str, subject: str) -> dict:
        return await self._call("GET", "/item/next",
                                params={"user_id": user_id, "subject": subject})

    async def submit(self, session_id: str, item_id: str, answer: str) -> dict:
        return await self._call("POST", "/attempt", json={
            "session_id": session_id, "item_id": item_id, "final_answer": answer,
        })

    async def hint(self, session_id: str, item_id: str, asked_for_solution: bool = False) -> dict:
        return await self._call("POST", "/hint", json={
            "session_id": session_id, "item_id": item_id,
            "asked_for_solution": asked_for_solution,
        })

    async def ask(self, question: str, subject: str | None = None) -> dict:
        return await self._call("POST", "/ask", json={"question": question, "subject": subject})

    async def progress(self, user_id: str, subject: str) -> dict:
        return await self._call("GET", "/progress",
                                params={"user_id": user_id, "subject": subject})
