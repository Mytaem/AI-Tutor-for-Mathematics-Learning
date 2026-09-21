"""Test API với nhiều môn, và hồi quy cho các lỗi tìm ra khi mở rộng sang MAI391."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.api.app import build_service, create_app  # noqa: E402
from src.api.db import Store  # noqa: E402
from src.core.config import AppConfig  # noqa: E402
from src.kt.coldstart import PLACEMENT_LENGTH  # noqa: E402


@pytest.fixture
def service():
    return build_service(AppConfig(), store=Store(":memory:"))


@pytest.fixture
def client(service) -> TestClient:
    return TestClient(create_app(service))


def start(client: TestClient, user: str, subject: str) -> dict:
    response = client.post("/session/start", json={"user_id": user, "subject": subject})
    assert response.status_code == 200, response.text
    return response.json()


def attempt(client: TestClient, session: dict, item_id: str, answer: str) -> dict:
    return client.post("/attempt", json={
        "session_id": session["session_id"], "item_id": item_id, "final_answer": answer,
    }).json()


class TestSubjects:
    def test_liet_ke_cac_mon_da_ho_tro(self, client: TestClient) -> None:
        assert {"MAE101", "MAI391"} <= set(client.get("/subjects").json())

    def test_health_bao_theo_tung_mon(self, client: TestClient) -> None:
        body = client.get("/health").json()
        assert body["subjects"]["MAI391"]["items"] >= 20
        assert body["items"] == sum(s["items"] for s in body["subjects"].values())

    def test_mon_chua_ho_tro_thi_404(self, client: TestClient) -> None:
        response = client.post("/session/start", json={"user_id": "u", "subject": "MAS291"})
        assert response.status_code == 404
        assert "MAS291" in response.json()["detail"]


class TestMAI391Session:
    def test_phien_mai391_nhan_bai_mai391(self, client: TestClient) -> None:
        session = start(client, "u", "MAI391")
        assert session["first_item"]["item_id"].startswith("MAI391-")
        assert session["placement_mode"] is True

    def test_cham_dung_bai_mai391(self, client: TestClient, service) -> None:
        session = start(client, "u", "MAI391")
        item = service.banks["MAI391"].get("MAI391-VEC-001")
        body = attempt(client, session, item.item_id, "[3, 3]")
        assert body["is_correct"] is True
        assert all(skill.startswith("MAI.") for skill in body["mastery_changes"])

    def test_chan_doan_loi_mai391_qua_api(self, client: TestClient) -> None:
        session = start(client, "u", "MAI391")
        body = attempt(client, session, "MAI391-ODE-004", "C1*exp(x) + C2*exp(x)")
        assert body["is_correct"] is False
        assert "MAI.ODE.INCOMPLETE" in body["error_codes"]
        assert body["hint"] is not None

    def test_khong_lo_dap_an_mai391(self, client: TestClient, service) -> None:
        session = start(client, "u", "MAI391")
        item = service.banks["MAI391"].get(session["first_item"]["item_id"])
        raw = json.dumps(session, ensure_ascii=False)
        assert item.answer_text not in raw
        assert "answer" not in session["first_item"]

    def test_tien_do_loc_theo_mon(self, client: TestClient) -> None:
        body = client.get("/progress", params={"user_id": "u", "subject": "MAI391"}).json()
        assert body["skills"] and all(s["skill_id"].startswith("MAI.") for s in body["skills"])

    def test_tien_do_toan_bo_gom_ca_hai_mon(self, client: TestClient) -> None:
        skills = {s["skill_id"][:4] for s in client.get("/progress", params={"user_id": "u"}).json()["skills"]}
        assert {"MAE.", "MAI."} <= skills


class TestPlacementPerSubject:
    def test_do_dau_vao_tinh_rieng_tung_mon(self, client: TestClient) -> None:
        """Làm xong bài đo MAE101 không có nghĩa là đã được đo năng lực MAI391."""
        session = start(client, "u", "MAE101")
        for _ in range(PLACEMENT_LENGTH):
            item = client.get("/item/next", params={"user_id": "u", "subject": "MAE101"}).json()
            last = attempt(client, session, item["item_id"], "x")
        assert last["placement_mode"] is False

        other = start(client, "u", "MAI391")
        assert other["placement_mode"] is True
        assert other["placement_remaining"] == PLACEMENT_LENGTH


class TestHintStateIsolation:
    """Hồi quy: trạng thái gợi ý từng bị khoá chỉ theo mã bài.

    Mọi sinh viên làm cùng một bài dùng chung một thang gợi ý: A bấm "gợi ý
    thêm" ba lần, B mở cùng bài đó nhận ngay gợi ý mức cao.
    """

    def test_hai_nguoi_cung_bai_khong_dung_chung_thang_goi_y(self, client: TestClient) -> None:
        item_id = "MAE101-INT-010"

        a = start(client, "A", "MAE101")
        first_a = attempt(client, a, item_id, "(x**2+1)**4 + C")
        for _ in range(3):
            client.post("/hint", json={"session_id": a["session_id"], "item_id": item_id})

        b = start(client, "B", "MAE101")
        first_b = attempt(client, b, item_id, "(x**2+1)**4 + C")

        assert first_b["hint"]["level"] == first_a["hint"]["level"], (
            "Người thứ hai phải bắt đầu từ đầu thang gợi ý, không kế thừa của người khác"
        )

    def test_cung_mot_nguoi_van_leo_thang_binh_thuong(self, client: TestClient) -> None:
        item_id = "MAE101-INT-010"
        session = start(client, "A", "MAE101")
        first = attempt(client, session, item_id, "(x**2+1)**4 + C")
        second = client.post("/hint", json={"session_id": session["session_id"], "item_id": item_id}).json()
        assert second["level"] > first["hint"]["level"]


class TestMigration:
    def test_nang_cap_file_db_cu_thieu_cot_subject(self, tmp_path: Path) -> None:
        """File tutor.sqlite tạo trước khi hỗ trợ nhiều môn không được làm hỏng app."""
        path = tmp_path / "old.sqlite"
        with sqlite3.connect(path) as connection:
            connection.execute(
                "CREATE TABLE attempts (attempt_id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "session_id TEXT NOT NULL, user_id TEXT NOT NULL, item_id TEXT NOT NULL, "
                "raw_input TEXT, steps_json TEXT, is_correct INTEGER, final_answer_correct INTEGER, "
                "first_wrong_step INTEGER, error_codes TEXT, verifier_json TEXT, created_at REAL NOT NULL)"
            )
            connection.execute(
                "INSERT INTO attempts (session_id, user_id, item_id, is_correct, created_at) "
                "VALUES ('s', 'u', 'MAE101-INT-001', 1, 0)"
            )

        store = Store(path)
        assert store.attempt_count("u", "MAE101") == 1, "Bài làm cũ phải được gán môn từ tiền tố mã bài"
        assert store.attempt_count("u", "MAI391") == 0
        store.close()
