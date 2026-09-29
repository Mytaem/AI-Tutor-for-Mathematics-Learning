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

    def attempt_history(self, user_id: str, subject: str | None = None) -> list[tuple[str, bool]]:
        """Lịch sử làm bài theo đúng thứ tự thời gian: (mã đề, đúng/sai).

        DKT suy ra năng lực từ CẢ CHUỖI chứ không giữ trạng thái như BKT, nên mỗi
        lần dựng lại tracker phải phát lại chuỗi này.
        """
        clause, params = self._subject_filter(subject)
        rows = self._connection.execute(
            "SELECT item_id, is_correct FROM attempts WHERE user_id = ?" + clause
            + " ORDER BY attempt_id", (user_id, *params)
        ).fetchall()
        return [(row["item_id"], bool(row["is_correct"])) for row in rows]

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

    # ------------------------------------------------------------------
    # Tổng hợp cho trang quản trị
    # ------------------------------------------------------------------

    def per_subject_stats(self) -> list[dict]:
        """Số lượt, số người, tỉ lệ đúng theo từng môn.

        ``final_answer_correct`` chứ không phải ``is_correct``: bài mà bộ chấm
        KHÔNG ĐỌC ĐƯỢC cũng có ``is_correct = 0``, tính nó vào tỉ lệ đúng là
        trộn lỗi định dạng vào lỗi kiến thức. ``unreadable`` đếm riêng, và con
        số đó chính là thước đo xem ô nhập đáp án có khó dùng hay không.
        """
        rows = self._connection.execute(
            """
            SELECT subject,
                   COUNT(*)                                        AS attempts,
                   COUNT(DISTINCT user_id)                         AS learners,
                   SUM(CASE WHEN final_answer_correct = 1 THEN 1 ELSE 0 END) AS correct,
                   SUM(CASE WHEN final_answer_correct IS NULL AND first_wrong_step IS NULL
                            THEN 1 ELSE 0 END)                     AS unreadable
            FROM attempts
            GROUP BY subject
            ORDER BY attempts DESC
            """
        ).fetchall()
        out = []
        for row in rows:
            graded = (row["attempts"] or 0) - (row["unreadable"] or 0)
            out.append({
                "subject": row["subject"] or "(không rõ)",
                "attempts": row["attempts"] or 0,
                "learners": row["learners"] or 0,
                "correct": row["correct"] or 0,
                "unreadable": row["unreadable"] or 0,
                "accuracy": round((row["correct"] or 0) / graded, 4) if graded else None,
            })
        return out

    def top_error_codes(self, limit: int = 15) -> list[dict]:
        """Mã lỗi hay gặp nhất. Đây là thứ giảng viên cần để biết dạy lại chỗ nào."""
        counter: dict[str, int] = {}
        rows = self._connection.execute(
            "SELECT error_codes FROM attempts WHERE error_codes IS NOT NULL AND error_codes != '[]'"
        ).fetchall()
        for row in rows:
            try:
                for code in json.loads(row["error_codes"]):
                    counter[code] = counter.get(code, 0) + 1
            except (TypeError, ValueError):
                continue
        ordered = sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]
        return [{"error_code": code, "count": count} for code, count in ordered]

    def learners(self, limit: int = 100) -> list[dict]:
        rows = self._connection.execute(
            """
            SELECT user_id,
                   COUNT(*)                                        AS attempts,
                   SUM(CASE WHEN final_answer_correct = 1 THEN 1 ELSE 0 END) AS correct,
                   COUNT(DISTINCT subject)                         AS subjects,
                   MAX(created_at)                                 AS last_seen
            FROM attempts
            GROUP BY user_id
            ORDER BY last_seen DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [
            {
                "user_id": row["user_id"],
                "attempts": row["attempts"],
                "correct": row["correct"] or 0,
                "subjects": row["subjects"],
                "last_seen": row["last_seen"],
            }
            for row in rows
        ]

    def recent_attempts(self, limit: int = 50, subject: str | None = None) -> list[dict]:
        clause, params = self._subject_filter(subject)
        rows = self._connection.execute(
            f"""
            SELECT attempt_id, user_id, subject, item_id, raw_input,
                   is_correct, final_answer_correct, first_wrong_step, error_codes, created_at
            FROM attempts
            WHERE 1 = 1 {clause}
            ORDER BY attempt_id DESC
            LIMIT ?
            """,
            (*params, limit),
        ).fetchall()
        return [
            {
                "attempt_id": row["attempt_id"],
                "user_id": row["user_id"],
                "subject": row["subject"],
                "item_id": row["item_id"],
                "answer": row["raw_input"],
                "verdict": (
                    "đúng" if row["final_answer_correct"] == 1
                    else "không đọc được" if row["final_answer_correct"] is None
                    and row["first_wrong_step"] is None
                    else "sai"
                ),
                "error_codes": json.loads(row["error_codes"] or "[]"),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def hint_level_usage(self) -> list[dict]:
        rows = self._connection.execute(
            "SELECT level, COUNT(*) AS n FROM hints GROUP BY level ORDER BY level"
        ).fetchall()
        return [{"level": row["level"], "count": row["n"]} for row in rows]

    def stats(self) -> dict[str, int]:
        def count(table: str) -> int:
            return self._connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

        return {
            "sessions": count("sessions"),
            "attempts": count("attempts"),
            "hints": count("hints"),
            "mastery_records": count("mastery"),
        }
