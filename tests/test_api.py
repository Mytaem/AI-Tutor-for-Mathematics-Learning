"""Test API.

Nhóm test quan trọng nhất là ``TestAnswerNeverLeaks``: nếu endpoint trả đáp án
kèm bài tập thì toàn bộ thiết kế sư phạm phía trên sụp đổ, vì sinh viên chỉ cần
mở tab Network của trình duyệt.
"""

from __future__ import annotations

import json
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
def client() -> TestClient:
    service = build_service(AppConfig(), store=Store(":memory:"))
    return TestClient(create_app(service))


@pytest.fixture
def session(client: TestClient) -> dict:
    response = client.post("/session/start", json={"user_id": "sv001", "subject": "MAE101"})
    assert response.status_code == 200
    return response.json()


# ==========================================================================

class TestHealth:
    def test_bao_cao_trang_thai(self, client: TestClient) -> None:
        body = client.get("/health").json()
        assert body["status"] == "ok"
        assert body["items"] >= 20
        assert body["skills"] >= 10


class TestSession:
    def test_tao_phien_va_nhan_bai_dau_tien(self, session: dict) -> None:
        assert session["session_id"]
        assert session["first_item"] is not None
        assert session["first_item"]["statement_vi"]

    def test_moi_phien_co_ma_rieng(self, client: TestClient) -> None:
        first = client.post("/session/start", json={"user_id": "a"}).json()
        second = client.post("/session/start", json={"user_id": "b"}).json()
        assert first["session_id"] != second["session_id"]

    def test_tu_choi_user_id_rong(self, client: TestClient) -> None:
        assert client.post("/session/start", json={"user_id": ""}).status_code == 422


class TestAnswerNeverLeaks:
    """Đáp án không được rời khỏi server trước khi sinh viên đủ điều kiện thấy nó."""

    FORBIDDEN = ("answer", "integrand", "reference_solution_steps")

    def test_bai_tap_tra_ve_khong_chua_dap_an(self, session: dict) -> None:
        item = session["first_item"]
        for field in self.FORBIDDEN:
            assert field not in item, f"Endpoint làm lộ trường {field!r}"

    def test_endpoint_item_next_cung_khong_lo(self, client: TestClient) -> None:
        item = client.get("/item/next", params={"user_id": "sv001"}).json()
        for field in self.FORBIDDEN:
            assert field not in item

    def test_khong_co_dap_an_trong_toan_bo_phan_hoi(
        self, client: TestClient, session: dict
    ) -> None:
        """Quét cả chuỗi JSON thô, phòng trường hợp đáp án lọt qua đường khác."""
        from src.api.app import build_service  # noqa: F401  (giữ import cục bộ cho rõ)

        service = build_service(AppConfig(), store=Store(":memory:"))
        item_id = session["first_item"]["item_id"]
        expected_answer = service.bank.get(item_id).answer_text

    # Tìm chuỗi con chỉ có nghĩa với đáp án đủ dài: một đáp án như "5" kiểu gì
    # cũng trùng một ký tự nào đó trong JSON (mã phiên dạng hex...). Với đáp án
    # ngắn, bảo đảm thật nằm ở việc các trường đáp án không có mặt — đã có test riêng.
        if len(expected_answer) >= 4:
            assert expected_answer not in json.dumps(session, ensure_ascii=False)

    def test_phan_hoi_bai_lam_sai_khong_lo_dap_an(
        self, client: TestClient, session: dict
    ) -> None:
        item_id = session["first_item"]["item_id"]
        response = client.post("/attempt", json={
            "session_id": session["session_id"],
            "item_id": item_id,
            "final_answer": "42",
        }).json()

        service = build_service(AppConfig(), store=Store(":memory:"))
        expected = service.bank.get(item_id).answer_text
        if len(expected) >= 4:
            assert expected not in json.dumps(response, ensure_ascii=False)


class TestAttempt:
    def test_lam_dung_thi_bao_dung(self, client: TestClient, session: dict) -> None:
        service = build_service(AppConfig(), store=Store(":memory:"))
        item_id = session["first_item"]["item_id"]
        correct = service.bank.get(item_id).answer_text

        body = client.post("/attempt", json={
            "session_id": session["session_id"], "item_id": item_id, "final_answer": correct,
        }).json()

        assert body["is_correct"] is True
        assert body["hint"] is None
        assert body["message"]

    def test_lam_sai_thi_co_goi_y(self, client: TestClient, session: dict) -> None:
        body = client.post("/attempt", json={
            "session_id": session["session_id"],
            "item_id": session["first_item"]["item_id"],
            "final_answer": "x",
        }).json()

        assert body["is_correct"] is False
        assert body["hint"] is not None
        assert body["hint"]["level_label"]

    def test_cap_nhat_muc_thanh_thao(self, client: TestClient, session: dict) -> None:
        body = client.post("/attempt", json={
            "session_id": session["session_id"],
            "item_id": session["first_item"]["item_id"],
            "final_answer": "x",
        }).json()
        assert body["mastery_changes"], "Làm bài xong phải cập nhật mô hình năng lực"

    def test_phien_khong_ton_tai_thi_404(self, client: TestClient) -> None:
        response = client.post("/attempt", json={
            "session_id": "khong-co", "item_id": "MAE101-INT-001", "final_answer": "x",
        })
        assert response.status_code == 404

    def test_bai_tap_khong_ton_tai_thi_404(self, client: TestClient, session: dict) -> None:
        response = client.post("/attempt", json={
            "session_id": session["session_id"], "item_id": "KHONG-CO", "final_answer": "x",
        })
        assert response.status_code == 404


class TestHint:
    def test_xin_goi_y_thi_leo_thang(self, client: TestClient, session: dict) -> None:
        session_id, item_id = session["session_id"], session["first_item"]["item_id"]
        first = client.post("/attempt", json={
            "session_id": session_id, "item_id": item_id, "final_answer": "x",
        }).json()

        levels = [first["hint"]["level"]]
        for _ in range(3):
            body = client.post("/hint", json={"session_id": session_id, "item_id": item_id}).json()
            levels.append(body["level"])

        assert levels == sorted(levels)
        assert levels[-1] > levels[0], "Xin thêm thì phải được gợi ý cụ thể hơn"

    def test_chua_lam_bai_thi_khong_xin_goi_y_duoc(
        self, client: TestClient, session: dict
    ) -> None:
        response = client.post("/hint", json={
            "session_id": session["session_id"], "item_id": session["first_item"]["item_id"],
        })
        assert response.status_code == 404


class TestProgress:
    def test_tra_ve_muc_thanh_thao_tung_ky_nang(self, client: TestClient, session: dict) -> None:
        client.post("/attempt", json={
            "session_id": session["session_id"],
            "item_id": session["first_item"]["item_id"],
            "final_answer": "x",
        })

        body = client.get("/progress", params={"user_id": "sv001"}).json()
        assert body["attempts"] == 1
        assert body["skills"]
        assert all(0.0 <= s["mastery"] <= 1.0 for s in body["skills"])
        assert all(s["name_vi"] for s in body["skills"]), "Phải có tên tiếng Việt để hiển thị"

    def test_nguoi_dung_moi_van_tra_ve_duoc(self, client: TestClient) -> None:
        body = client.get("/progress", params={"user_id": "nguoi-moi"}).json()
        assert body["attempts"] == 0


class TestPlacement:
    """Giai đoạn đo đầu vào — chạy trước khi bước vào luyện tập thật."""

    def test_nguoi_moi_vao_che_do_do_dau_vao(self, session: dict) -> None:
        assert session["placement_mode"] is True
        assert session["placement_remaining"] == PLACEMENT_LENGTH

    def test_dem_lui_sau_moi_cau(self, client: TestClient, session: dict) -> None:
        body = client.post("/attempt", json={
            "session_id": session["session_id"],
            "item_id": session["first_item"]["item_id"],
            "final_answer": "x",
        }).json()
        assert body["placement_remaining"] == PLACEMENT_LENGTH - 1

    def test_ket_thuc_sau_du_so_cau(self, client: TestClient, session: dict) -> None:
        session_id = session["session_id"]
        for _ in range(PLACEMENT_LENGTH):
            item = client.get("/item/next", params={"user_id": "sv001"}).json()
            body = client.post("/attempt", json={
                "session_id": session_id, "item_id": item["item_id"], "final_answer": "x",
            }).json()

        assert body["placement_mode"] is False
        assert body["placement_remaining"] == 0

    def test_khong_hoi_lai_bai_da_lam_trong_luc_do(
        self, client: TestClient, session: dict
    ) -> None:
        session_id = session["session_id"]
        seen: list[str] = []
        for _ in range(PLACEMENT_LENGTH):
            item = client.get("/item/next", params={"user_id": "sv001"}).json()
            seen.append(item["item_id"])
            client.post("/attempt", json={
                "session_id": session_id, "item_id": item["item_id"], "final_answer": "x",
            })

        assert len(set(seen)) == len(seen), f"Hỏi lại bài đã làm: {seen}"

    def test_phu_nhieu_ky_nang(self, client: TestClient, session: dict) -> None:
        """Mục tiêu của bài đo là phủ rộng, không phải đào sâu một kỹ năng."""
        service = build_service(AppConfig(), store=Store(":memory:"))
        session_id = session["session_id"]

        covered: set[str] = set()
        for _ in range(PLACEMENT_LENGTH):
            item = client.get("/item/next", params={"user_id": "sv001"}).json()
            covered.update(service.bank.get(item["item_id"]).skills)
            client.post("/attempt", json={
                "session_id": session_id, "item_id": item["item_id"], "final_answer": "x",
            })

        assert len(covered) >= 5, f"{PLACEMENT_LENGTH} câu mới phủ được {len(covered)} kỹ năng"


class TestColdStartMastery:
    def test_nguoi_moi_khong_co_mastery_phang(self, client: TestClient) -> None:
        """Bug đã sửa: trước đây mọi kỹ năng cùng một giá trị nên bộ chọn bài mù."""
        body = client.get("/progress", params={"user_id": "hoan-toan-moi"}).json()
        values = {round(s["mastery"], 4) for s in body["skills"]}
        assert len(values) > 1, "Tiên nghiệm phải phân biệt kỹ năng nền tảng với kỹ năng sâu"

    def test_lam_dung_thi_nang_ca_ky_nang_tien_quyet(
        self, client: TestClient, session: dict
    ) -> None:
        service = build_service(AppConfig(), store=Store(":memory:"))
        item = service.bank.get("MAE101-INT-010")  # cần MAE.INT.SUBST

        before = {
            s["skill_id"]: s["mastery"]
            for s in client.get("/progress", params={"user_id": "sv001"}).json()["skills"]
        }
        client.post("/attempt", json={
            "session_id": session["session_id"],
            "item_id": item.item_id,
            "final_answer": str(item.answer),
        })
        after = {
            s["skill_id"]: s["mastery"]
            for s in client.get("/progress", params={"user_id": "sv001"}).json()["skills"]
        }

        assert after["MAE.DER.CHAIN"] > before["MAE.DER.CHAIN"], (
            "Giải được bài đổi biến thì phải nâng cả quy tắc hàm hợp"
        )


class TestSelection:
    def test_khong_lap_lai_bai_vua_lam(self, client: TestClient, session: dict) -> None:
        session_id = session["session_id"]
        first_id = session["first_item"]["item_id"]

        client.post("/attempt", json={
            "session_id": session_id, "item_id": first_id, "final_answer": "x",
        })
        next_item = client.get("/item/next", params={"user_id": "sv001"}).json()

        assert next_item["item_id"] != first_id, "Bộ chọn bài phải tránh lặp lại bài vừa làm"
