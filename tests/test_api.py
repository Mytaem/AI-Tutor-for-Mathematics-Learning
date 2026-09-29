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

import src.api.app as app_module  # noqa: E402
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

class TestCORS:
    """Thiếu CORS thì web hiện ra đầy đủ nhưng KHÔNG nút nào chạy.

    Lỗi này từng lọt qua cả bộ test: ``TestClient`` và ``curl`` không thi hành
    same-origin policy, chỉ trình duyệt thật mới chặn. Test ở đây giả đúng cú
    preflight mà trình duyệt gửi trước mỗi lời gọi POST.
    """

    def test_cho_phep_web_o_cong_3000_goi_sang(self, client: TestClient) -> None:
        response = client.options("/session/start", headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        })
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"

    def test_origin_la_thuoc_tinh_cua_phan_hoi_that(self, client: TestClient) -> None:
        """Không chỉ preflight: phản hồi thật cũng phải mang header đó."""
        response = client.get("/health", headers={"Origin": "http://localhost:3000"})
        assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


class TestAdmin:
    """Phần quản trị phải chặn ở TẦNG SERVER, không phải ở giao diện."""

    def test_chua_dat_khoa_thi_tat_han(self, client: TestClient, monkeypatch) -> None:
        """Mặc định phải là TẮT, không phải mở.

        Dữ liệu ở đây là bài làm của người thật. "Chưa cấu hình" mà mở sẵn là
        kiểu lỗ hổng tệ nhất vì không ai nhận ra cho tới lúc muộn.
        """
        monkeypatch.setattr(app_module, "ADMIN_TOKEN", "")
        fresh = TestClient(create_app(build_service(AppConfig(), store=Store(":memory:"))))
        assert fresh.get("/admin/enabled").json() == {"enabled": False}
        assert fresh.get("/admin/overview").status_code == 403

    def test_khoa_sai_hoac_thieu_thi_tu_choi(self, monkeypatch) -> None:
        monkeypatch.setattr(app_module, "ADMIN_TOKEN", "khoa-that")
        guarded = TestClient(create_app(build_service(AppConfig(), store=Store(":memory:"))))
        assert guarded.get("/admin/overview").status_code == 401
        # Khoá sai phải là ASCII: giá trị header không mang được dấu tiếng Việt,
        # httpx chặn ngay ở tầng HTTP nên sẽ không tới được chỗ mình muốn kiểm.
        assert guarded.get("/admin/overview", headers={"X-Admin-Token": "doan-bua"}).status_code == 401
        assert guarded.get("/admin/overview", headers={"X-Admin-Token": "khoa-that"}).status_code == 200

    def test_tong_hop_khong_tron_loi_dinh_dang_vao_ti_le_dung(self, monkeypatch) -> None:
        """Bài KHÔNG ĐỌC ĐƯỢC phải đếm riêng, không kéo tỉ lệ đúng xuống."""
        monkeypatch.setattr(app_module, "ADMIN_TOKEN", "khoa-that")
        store = Store(":memory:")
        service = build_service(AppConfig(), store=store)
        guarded = TestClient(create_app(service))
        head = {"X-Admin-Token": "khoa-that"}

        session = guarded.post("/session/start", json={"user_id": "sv9", "subject": "MAE101"}).json()
        item_id = session["first_item"]["item_id"]
        correct = service.bank_for("MAE101").items[item_id].answer_text
        for answer in (correct, "x = ?"):
            guarded.post("/attempt", json={
                "session_id": session["session_id"], "item_id": item_id, "final_answer": answer,
            })

        stats = guarded.get("/admin/overview", headers=head).json()["subjects"][0]
        assert stats["attempts"] == 2
        assert stats["unreadable"] == 1
        assert stats["accuracy"] == 1.0, "1 đúng / 1 chấm được = 100%, bài không đọc được để riêng"

    def test_xuat_csv_co_bom_cho_excel(self, monkeypatch) -> None:
        """Thiếu BOM thì Excel trên Windows mở ra tiếng Việt thành ký tự lạ."""
        monkeypatch.setattr(app_module, "ADMIN_TOKEN", "khoa-that")
        guarded = TestClient(create_app(build_service(AppConfig(), store=Store(":memory:"))))
        response = guarded.get("/admin/export.csv", headers={"X-Admin-Token": "khoa-that"})
        assert response.status_code == 200
        assert response.content.startswith(b"\xef\xbb\xbf")
        assert "attachment" in response.headers["content-disposition"]


class TestSyllabus:
    """Cây chọn phạm vi: môn → chương → bài → dạng bài."""

    def test_tra_ca_cay_trong_mot_loi_goi(self, client: TestClient) -> None:
        body = client.get("/syllabus", params={"subject": "MAD101"}).json()
        assert body["subject"] == "MAD101"
        assert len(body["chapters"]) >= 5
        chapter = next(c for c in body["chapters"] if c["lessons"])
        lesson = next(l for l in chapter["lessons"] if l["topics"])
        assert lesson["topics"][0]["name_vi"]

    def test_khong_co_user_thi_van_tra_duoc_cay(self, client: TestClient) -> None:
        """Trang chọn môn cần cây TRƯỚC khi có phiên, nên user_id phải là tuỳ chọn."""
        body = client.get("/syllabus", params={"subject": "MAE101"}).json()
        assert all(c["mastery"] is None for c in body["chapters"])

    def test_co_user_thi_kem_muc_thanh_thao(self, client: TestClient, session: dict) -> None:
        body = client.get(
            "/syllabus", params={"subject": "MAE101", "user_id": "sv001"}
        ).json()
        assert any(c["mastery"] is not None for c in body["chapters"])

    def test_so_de_tren_nut_dung_bang_so_de_bam_vao_nhan_duoc(
        self, client: TestClient, session: dict
    ) -> None:
        """Nút ghi "12 đề" mà bấm vào báo hết đề là kiểu hỏng mất lòng tin nhất."""
        body = client.get("/syllabus", params={"subject": "MAE101"}).json()
        for chapter in body["chapters"]:
            response = client.get("/item/next", params={
                "user_id": "sv001", "subject": "MAE101", "chapter": chapter["chapter"],
            })
            if chapter["items"] == 0:
                assert response.status_code == 404
            else:
                assert response.status_code == 200, chapter["name_vi"]

    def test_loc_den_tan_dang_bai(self, client: TestClient, session: dict) -> None:
        body = client.get("/syllabus", params={"subject": "MAD101"}).json()
        chapter = next(c for c in body["chapters"] if any(l["topics"] for l in c["lessons"]))
        lesson = next(l for l in chapter["lessons"] if l["topics"])
        topic = lesson["topics"][0]

        response = client.get("/item/next", params={
            "user_id": "sv001", "subject": "MAD101",
            "chapter": chapter["chapter"], "skill": lesson["skill_id"],
            "topic": topic["topic_id"],
        })
        assert response.status_code == 200
        assert lesson["skill_id"] in response.json()["skills"]

    def test_pham_vi_rong_thi_noi_ro_la_chon_hep_qua(
        self, client: TestClient, session: dict
    ) -> None:
        """Không được trả "hết đề": người học vừa tự chọn phạm vi, họ cần biết vì sao."""
        response = client.get("/item/next", params={
            "user_id": "sv001", "subject": "MAD101",
            "chapter": "Ch7 Trees", "topic": "gcd",
        })
        assert response.status_code == 404
        assert "rộng hơn" in response.json()["detail"]


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

    def test_lam_sai_van_co_loi_nhan_xet(self, client: TestClient, session: dict) -> None:
        """Giao diện hiển thị 'Chưa đúng — {message}'; message rỗng thì hiện ra câu cụt."""
        body = client.post("/attempt", json={
            "session_id": session["session_id"],
            "item_id": session["first_item"]["item_id"],
            "final_answer": "x",
        }).json()
        assert body["message"].strip()

    def test_khong_doc_duoc_bai_lam_thi_khong_dung_toi_mastery(
        self, client: TestClient, session: dict
    ) -> None:
        """Bộ chấm TỪ CHỐI kết luận thì mô hình năng lực phải đứng yên.

        Trước đây bài không đọc được bị cập nhật y hệt bài sai thật: mức thành
        thạo tụt 0,45 → 0,23 chỉ vì sinh viên gõ sai định dạng. Đó là ghi lỗi
        gõ phím thành lỗ hổng kiến thức, và nó bẩn đúng cái mô hình mà cả phần
        chọn bài thích ứng dựa vào.
        """
        item_id = session["first_item"]["item_id"]
        skills = session["first_item"]["skills"]

        def mastery() -> dict[str, float]:
            body = client.get("/progress", params={"user_id": "sv001", "subject": "MAE101"}).json()
            return {s["skill_id"]: s["mastery"] for s in body["skills"] if s["skill_id"] in skills}

        before = mastery()
        body = client.post("/attempt", json={
            "session_id": session["session_id"], "item_id": item_id, "final_answer": "x = ?",
        }).json()

        assert body["final_answer_correct"] is None, "đề này đọc được, chọn đề khác để test"
        assert mastery() == before

    @pytest.mark.parametrize("subject", ["MAE101", "MAI391", "MAS291", "MAD101"])
    def test_khong_de_nao_lo_dap_an_qua_api(self, client: TestClient, subject: str) -> None:
        """Quét NHIỀU đề của mọi môn, không chỉ đề đầu tiên của một phiên.

        Bản test cũ chỉ kiểm bài đầu tiên; một dạng bài hiếm làm lộ đáp án sẽ
        không bao giờ bị bắt.
        """
        service = build_service(AppConfig(), store=Store(":memory:"))
        bank = service.banks[subject]
        started = client.post("/session/start", json={"user_id": f"sv-{subject}", "subject": subject}).json()

        leaks = []
        for item in list(bank.items.values())[::37]:
            answer = item.answer_text
            body = client.post("/attempt", json={
                "session_id": started["session_id"], "item_id": item.item_id, "final_answer": "0",
            }).json()
            if len(answer) >= 4 and answer.lower() in json.dumps(body, ensure_ascii=False).lower():
                leaks.append(f"{item.item_id}: «{answer}»")
        assert leaks == [], "\n".join(leaks[:5])

    def test_cap_nhat_muc_thanh_thao(self, client: TestClient, session: dict) -> None:
        """Bài sai THẬT thì phải cập nhật mô hình năng lực.

        Bản cũ nộp ``"x"`` — chuỗi mà bộ chấm không đọc nổi — nên nó vẫn xanh
        cả khi hệ thống cập nhật năng lực dựa trên một kết luận chưa hề có.
        Đáp án ở đây cố tình SAI nhưng ĐỌC ĐƯỢC, để phân biệt hai ca đó.
        """
        body = client.post("/attempt", json={
            "session_id": session["session_id"],
            "item_id": session["first_item"]["item_id"],
            "final_answer": "[9, 9]",
        }).json()
        assert body["final_answer_correct"] is False, "đáp án test phải đọc được và sai"
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
