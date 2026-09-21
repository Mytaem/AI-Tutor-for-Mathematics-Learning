"""Lưu trữ phiên học, bài làm, gợi ý và mức thành thạo.

Dùng sqlite3 trần, không ORM: lược đồ nhỏ, truy vấn đơn giản, và quan trọng hơn
là mọi thứ nằm trong một file duy nhất — tiện đem đi phân tích, tiện sao lưu
trước buổi bảo vệ, không phải dựng server.

Lược đồ được thiết kế cho việc PHÂN TÍCH về sau, không chỉ để chạy ứng dụng.
Bảng ``attempts`` và ``hints`` chính là dữ liệu thô cho EXP-2, EXP-5, EXP-6 và
phần thực nghiệm người dùng, nên phải ghi đủ ngay từ đầu — bổ sung cột sau khi
đã thu dữ liệu thì mẫu cũ mất trường, không dùng được nữa.
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id   TEXT PRIMARY KEY,
    user_id      TEXT NOT NULL,
    subject      TEXT NOT NULL,
    created_at   REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS attempts (
    attempt_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   TEXT NOT NULL,
    user_id      TEXT NOT NULL,
    subject      TEXT,
    item_id      TEXT NOT NULL,
    raw_input    TEXT,
    steps_json   TEXT,
    is_correct   INTEGER,
    final_answer_correct INTEGER,
    first_wrong_step INTEGER,
    error_codes  TEXT,
    verifier_json TEXT,
    created_at   REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS hints (
    hint_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   TEXT NOT NULL,
    item_id      TEXT NOT NULL,
    level        INTEGER NOT NULL,
    text         TEXT NOT NULL,
    source       TEXT,
    error_code   TEXT,
    blocked      INTEGER DEFAULT 0,
    created_at   REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS mastery (
    user_id      TEXT NOT NULL,
    skill_id     TEXT NOT NULL,
    value        REAL NOT NULL,
    updated_at   REAL NOT NULL,
    PRIMARY KEY (user_id, skill_id)
);

CREATE INDEX IF NOT EXISTS idx_attempts_session ON attempts(session_id);
CREATE INDEX IF NOT EXISTS idx_attempts_user ON attempts(user_id);
CREATE INDEX IF NOT EXISTS idx_hints_session ON hints(session_id);
"""


class Store:
    """Kho dữ liệu của ứng dụng."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        if str(path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False vì FastAPI chạy handler trên nhiều thread.
        self._connection = sqlite3.connect(
            ":memory:" if str(path) == ":memory:" else self.path,
            check_same_thread=False,
        )
        self._connection.row_factory = sqlite3.Row
        self._connection.executescript(SCHEMA)
        self._migrate()
        self._connection.commit()

    def _migrate(self) -> None:
        """Nâng cấp file DB đã tạo bằng lược đồ cũ.

        ``CREATE TABLE IF NOT EXISTS`` KHÔNG thêm cột mới vào bảng đã có, nên một
        file ``tutor.sqlite`` tạo trước khi hỗ trợ nhiều môn sẽ thiếu cột
        ``subject`` và mọi truy vấn lọc theo môn đều nổ. Bài làm cũ suy ra môn từ
        tiền tố mã bài (``MAE101-...``) — mã bài được thiết kế như vậy từ đầu.
        """
        columns = {row["name"] for row in self._connection.execute("PRAGMA table_info(attempts)")}
        if "subject" not in columns:
            self._connection.execute("ALTER TABLE attempts ADD COLUMN subject TEXT")
            self._connection.execute(
                "UPDATE attempts SET subject = substr(item_id, 1, instr(item_id, '-') - 1) "
                "WHERE subject IS NULL AND instr(item_id, '-') > 0"
            )
        self._connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_attempts_user_subject ON attempts(user_id, subject)"
        )

    def close(self) -> None:
        self._connection.close()

    # ------------------------------------------------------------------

    def create_session(self, user_id: str, subject: str) -> str:
        session_id = uuid.uuid4().hex
        self._connection.execute(
            "INSERT INTO sessions (session_id, user_id, subject, created_at) VALUES (?, ?, ?, ?)",
            (session_id, user_id, subject, time.time()),
        )
        self._connection.commit()
        return session_id

    def get_session(self, session_id: str) -> sqlite3.Row | None:
        return self._connection.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()

    # ------------------------------------------------------------------

    def record_attempt(
        self,
        session_id: str,
        user_id: str,
        item_id: str,
        raw_input: str,
        steps: list[str],
        verification: Any,
        subject: str | None = None,
    ) -> int:
        cursor = self._connection.execute(
            """
            INSERT INTO attempts
                (session_id, user_id, subject, item_id, raw_input, steps_json, is_correct,
                 final_answer_correct, first_wrong_step, error_codes, verifier_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id, user_id, subject, item_id, raw_input,
                json.dumps(steps, ensure_ascii=False),
                int(verification.is_correct),
                None if verification.final_answer_correct is None else int(verification.final_answer_correct),
                verification.first_wrong_step,
                json.dumps(verification.candidate_error_codes, ensure_ascii=False),
                verification.model_dump_json(),
                time.time(),
            ),
        )
        self._connection.commit()
        return cursor.lastrowid

    def record_hint(self, session_id: str, item_id: str, hint: Any) -> int:
        cursor = self._connection.execute(
            """
            INSERT INTO hints (session_id, item_id, level, text, source, error_code, blocked, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id, item_id, int(hint.level), hint.text, hint.source,
                hint.error_code, int(hint.was_blocked), time.time(),
            ),
        )
        self._connection.commit()
        return cursor.lastrowid

    def attempts_for_session(self, session_id: str) -> list[sqlite3.Row]:
        return self._connection.execute(
            "SELECT * FROM attempts WHERE session_id = ? ORDER BY attempt_id", (session_id,)
        ).fetchall()

    @staticmethod
    def _subject_filter(subject: str | None) -> tuple[str, tuple]:
        return (" AND subject = ?", (subject,)) if subject else ("", ())

    def attempt_count(self, user_id: str, subject: str | None = None) -> int:
        """Người này đã làm bao nhiêu bài (của một môn) — để biết còn trong giai đoạn đo đầu vào không.

        Tính RIÊNG từng môn: làm xong bài đo MAE101 không có nghĩa là đã được đo
        năng lực MAI391.
        """
        clause, params = self._subject_filter(subject)
        return self._connection.execute(
            "SELECT COUNT(*) FROM attempts WHERE user_id = ?" + clause, (user_id, *params)
        ).fetchone()[0]

    def attempted_item_ids(self, user_id: str, subject: str | None = None) -> set[str]:
        clause, params = self._subject_filter(subject)
        rows = self._connection.execute(
            "SELECT DISTINCT item_id FROM attempts WHERE user_id = ?" + clause, (user_id, *params)
        ).fetchall()
        return {row["item_id"] for row in rows}

    def recent_item_ids(self, user_id: str, limit: int = 5, subject: str | None = None) -> set[str]:
        clause, params = self._subject_filter(subject)
        rows = self._connection.execute(
            "SELECT item_id FROM attempts WHERE user_id = ?" + clause +
            " ORDER BY attempt_id DESC LIMIT ?",
            (user_id, *params, limit),
        ).fetchall()
        return {row["item_id"] for row in rows}

    # ------------------------------------------------------------------

    def load_mastery(self, user_id: str) -> dict[str, float]:
        rows = self._connection.execute(
            "SELECT skill_id, value FROM mastery WHERE user_id = ?", (user_id,)
        ).fetchall()
        return {row["skill_id"]: row["value"] for row in rows}

    def save_mastery(self, user_id: str, values: dict[str, float]) -> None:
        now = time.time()
        self._connection.executemany(
            "INSERT INTO mastery (user_id, skill_id, value, updated_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(user_id, skill_id) DO UPDATE SET value = excluded.value, "
            "updated_at = excluded.updated_at",
            [(user_id, skill_id, value, now) for skill_id, value in values.items()],
        )
        self._connection.commit()

    # ------------------------------------------------------------------

    def stats(self) -> dict[str, int]:
        def count(table: str) -> int:
            return self._connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

        return {
            "sessions": count("sessions"),
            "attempts": count("attempts"),
            "hints": count("hints"),
            "mastery_records": count("mastery"),
        }
