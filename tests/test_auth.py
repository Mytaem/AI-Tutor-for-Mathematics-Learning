"""Tài khoản: đăng ký, đăng nhập, và KHÔNG ai xem/sửa được dữ liệu người khác."""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.api.app import build_service, create_app  # noqa: E402
from src.api.auth import COOKIE_NAME, hash_password, verify_password  # noqa: E402
from src.api.db import Store  # noqa: E402
from src.core.config import AppConfig  # noqa: E402

PASSWORD = "matkhau123"


@pytest.fixture(scope="module")
def app():
    return create_app(build_service(AppConfig(), store=Store(":memory:")))


def browser(app) -> TestClient:
    """Một trình duyệt riêng: cookie riêng, không có khoá dịch vụ."""
    return TestClient(app)


def signed_up(app, email: str) -> TestClient:
    client = browser(app)
    response = client.post("/auth/register", json={"email": email, "password": PASSWORD, "display_name": "An"})
    assert response.status_code == 201, response.text
    return client


class TestMatKhau:
    def test_bam_va_kiem(self):
        stored = hash_password("abc12345")
        assert stored.startswith("scrypt$") and "abc12345" not in stored
        assert verify_password("abc12345", stored)
        assert not verify_password("abc12346", stored)

    def test_cung_mat_khau_khac_chuoi_bam(self):
        assert hash_password("abc12345") != hash_password("abc12345")


class TestDangKyDangNhap:
    def test_dang_ky_dat_cookie_httponly(self, app):
        client = browser(app)
        response = client.post("/auth/register", json={"email": "An@Gmail.com ", "password": PASSWORD})
        assert response.status_code == 201
        assert response.json()["email"] == "an@gmail.com"
        cookie = response.headers["set-cookie"]
        assert COOKIE_NAME in cookie and "HttpOnly" in cookie and "samesite=lax" in cookie.lower()
        assert client.get("/auth/me").json()["email"] == "an@gmail.com"

    def test_trung_email(self, app):
        signed_up(app, "trung@gmail.com")
        again = browser(app).post("/auth/register", json={"email": "TRUNG@gmail.com", "password": PASSWORD})
        assert again.status_code == 409

    @pytest.mark.parametrize(("email", "password"), [
        ("khong-phai-email", PASSWORD), ("a@b.co", "ngan1"), ("a@b.co", "chiconchu"), ("a@b.co", "12345678"),
    ])
    def test_tu_choi_email_sai_va_mat_khau_yeu(self, app, email, password):
        assert browser(app).post("/auth/register", json={"email": email, "password": password}).status_code == 422

    def test_dang_nhap_dung_va_sai(self, app):
        signed_up(app, "login@gmail.com")
        client = browser(app)
        assert client.post("/auth/login", json={"email": "login@gmail.com", "password": "saimatkhau9"}).status_code == 401
        assert client.get("/auth/me").status_code == 401
        assert client.post("/auth/login", json={"email": "LOGIN@gmail.com", "password": PASSWORD}).status_code == 200
        assert client.get("/auth/me").status_code == 200

    def test_email_khong_ton_tai_cung_mot_cau_bao_loi(self, app):
        signed_up(app, "co-that@gmail.com")
        wrong_pw = browser(app).post("/auth/login", json={"email": "co-that@gmail.com", "password": "sai12345"})
        no_user = browser(app).post("/auth/login", json={"email": "khong-co@gmail.com", "password": "sai12345"})
        assert wrong_pw.status_code == no_user.status_code == 401
        assert wrong_pw.json()["detail"] == no_user.json()["detail"]

    def test_sai_nhieu_lan_thi_tam_khoa(self):
        app = create_app(build_service(AppConfig(), store=Store(":memory:")))
        signed_up(app, "do@gmail.com")
        client = browser(app)
        for _ in range(5):
            assert client.post("/auth/login", json={"email": "do@gmail.com", "password": "sai12345"}).status_code == 401
        blocked = client.post("/auth/login", json={"email": "do@gmail.com", "password": PASSWORD})
        assert blocked.status_code == 429 and "Retry-After" in blocked.headers

    def test_dang_xuat_vo_hieu_phien(self, app):
        client = signed_up(app, "out@gmail.com")
        token = client.cookies.get(COOKIE_NAME)
        assert client.post("/auth/logout").status_code == 204
        # Kể cả giữ lại token cũ thì cũng hết hiệu lực ở phía server.
        stolen = browser(app)
        stolen.cookies.set(COOKIE_NAME, token)
        assert stolen.get("/auth/me").status_code == 401

    def test_doi_mat_khau_dang_xuat_thiet_bi_khac(self, app):
        laptop = signed_up(app, "doi@gmail.com")
        phone = browser(app)
        phone.post("/auth/login", json={"email": "doi@gmail.com", "password": PASSWORD})
        assert laptop.post("/auth/password", json={"current_password": "sai12345", "new_password": "moi123456"}).status_code == 403
        assert laptop.post("/auth/password", json={"current_password": PASSWORD, "new_password": "moi123456"}).status_code == 204
        assert laptop.get("/auth/me").status_code == 200
        assert phone.get("/auth/me").status_code == 401
        assert browser(app).post("/auth/login", json={"email": "doi@gmail.com", "password": "moi123456"}).status_code == 200


class TestPhanQuyen:
    def test_chua_dang_nhap_bi_chan(self, app):
        anonymous = browser(app)
        assert anonymous.post("/session/start", json={"subject": "MAE101"}).status_code == 401
        assert anonymous.get("/progress", params={"user_id": "x", "subject": "MAE101"}).status_code == 401
        assert anonymous.post("/ask", json={"question": "Đạo hàm là gì?"}).status_code == 401
        # Cây môn học vẫn công khai — trang giới thiệu cần nó.
        assert anonymous.get("/syllabus", params={"subject": "MAE101"}).status_code == 200

    def test_gui_user_id_nguoi_khac_bi_bo_qua(self, app):
        alice = signed_up(app, "alice@gmail.com")
        bob = signed_up(app, "bob@gmail.com")
        alice_id = alice.get("/auth/me").json()["user_id"]
        session = alice.post("/session/start", json={"subject": "MAE101"}).json()
        assert session["user_id"] == alice_id
        # Bob đòi tiến độ của Alice bằng cách gửi user_id: chỉ nhận về của chính mình.
        bob_view = bob.get("/progress", params={"user_id": alice_id, "subject": "MAE101"}).json()
        assert bob_view["user_id"] != alice_id

    def test_khong_nop_bai_vao_phien_nguoi_khac(self, app):
        alice = signed_up(app, "alice2@gmail.com")
        bob = signed_up(app, "bob2@gmail.com")
        session = alice.post("/session/start", json={"subject": "MAE101"}).json()
        item_id = session["first_item"]["item_id"]
        body = {"session_id": session["session_id"], "item_id": item_id, "final_answer": "1"}
        assert bob.post("/attempt", json=body).status_code == 403
        assert bob.post("/hint", json={"session_id": session["session_id"], "item_id": item_id}).status_code == 403
        assert alice.post("/attempt", json=body).status_code == 200

    def test_khoa_dich_vu_sai_khong_duoc_tin(self, app):
        fake = TestClient(app, headers={"X-Service-Token": "doan-bua"})
        assert fake.post("/session/start", json={"user_id": "tg:1", "subject": "MAE101"}).status_code == 401

    def test_khoa_dich_vu_dung_goi_thay_nguoi_dung(self, app):
        from conftest import SERVICE_HEADERS

        bot = TestClient(app, headers=SERVICE_HEADERS)
        assert bot.post("/session/start", json={"user_id": "tg:42", "subject": "MAE101"}).json()["user_id"] == "tg:42"


# ----------------------------------------------------------------------
# Email: xác thực, quên mật khẩu; quyền với dữ liệu: tải về, xoá
# ----------------------------------------------------------------------

import re  # noqa: E402

from src.api.mailer import Mailer  # noqa: E402


@pytest.fixture()
def mailed():
    mailer = Mailer(host="", sender="")
    service = build_service(AppConfig(), store=Store(":memory:"))
    app = create_app(service, mailer=mailer)
    app.state.service = service
    return app, mailer


def _token_in(message) -> str:
    return re.search(r"token=([A-Za-z0-9_\-]+)", message.get_content()).group(1)


class TestEmail:
    def test_dang_ky_gui_thu_xac_thuc_va_xac_thuc_duoc(self, mailed):
        app, mailer = mailed
        client = signed_up(app, "verify@gmail.com")
        assert client.get("/auth/me").json()["email_verified"] is False
        assert len(mailer.outbox) == 1 and mailer.outbox[0]["To"] == "verify@gmail.com"
        token = _token_in(mailer.outbox[0])
        assert browser(app).post("/auth/verify", json={"token": token}).json()["email_verified"] is True
        assert client.get("/auth/me").json()["email_verified"] is True
        # Link chỉ dùng được một lần.
        assert browser(app).post("/auth/verify", json={"token": token}).status_code == 400

    def test_quen_mat_khau_dat_lai_va_dang_xuat_moi_noi(self, mailed):
        app, mailer = mailed
        old_device = signed_up(app, "quen@gmail.com")
        mailer.outbox.clear()
        assert browser(app).post("/auth/forgot", json={"email": "Quen@gmail.com"}).status_code == 202
        token = _token_in(mailer.outbox[-1])
        assert "/reset?token=" in mailer.outbox[-1].get_content()
        # Mật khẩu yếu bị từ chối và KHÔNG đốt mất link.
        assert browser(app).post("/auth/reset", json={"token": token, "new_password": "yeu"}).status_code == 422
        assert browser(app).post("/auth/reset", json={"token": token, "new_password": "moitinh123"}).status_code == 204
        assert old_device.get("/auth/me").status_code == 401
        assert browser(app).post("/auth/login", json={"email": "quen@gmail.com", "password": "moitinh123"}).status_code == 200
        assert browser(app).post("/auth/reset", json={"token": token, "new_password": "khac12345"}).status_code == 400

    def test_quen_mat_khau_email_khong_ton_tai_tra_cung_cau(self, mailed):
        app, mailer = mailed
        mailer.outbox.clear()
        response = browser(app).post("/auth/forgot", json={"email": "khong-ai@gmail.com"})
        assert response.status_code == 202 and response.json() == {"sent": True}
        assert mailer.outbox == []


class TestDuLieuCaNhan:
    def test_tai_ve_du_lieu_cua_minh(self, mailed):
        app, _ = mailed
        client = signed_up(app, "export@gmail.com")
        session = client.post("/session/start", json={"subject": "MAS291"}).json()
        client.post("/attempt", json={"session_id": session["session_id"],
                                      "item_id": session["first_item"]["item_id"], "final_answer": "0.1"})
        response = client.get("/auth/export")
        assert "attachment" in response.headers["content-disposition"]
        data = response.json()
        assert data["account"]["email"] == "export@gmail.com"
        assert len(data["attempts"]) == 1 and "password_hash" not in data["account"]

    def test_xoa_tai_khoan_xoa_het_du_lieu(self, mailed):
        app, _ = mailed
        client = signed_up(app, "xoa@gmail.com")
        session = client.post("/session/start", json={"subject": "MAS291"}).json()
        client.post("/attempt", json={"session_id": session["session_id"],
                                      "item_id": session["first_item"]["item_id"], "final_answer": "0.1"})
        user_id = client.get("/auth/me").json()["user_id"]
        assert client.post("/auth/delete", json={"password": "sai12345"}).status_code == 403
        assert client.post("/auth/delete", json={"password": PASSWORD}).status_code == 204
        assert client.get("/auth/me").status_code == 401
        store = app.state.service.store
        for table in ("users", "sessions", "attempts", "mastery", "auth_tokens", "email_tokens"):
            left = store._connection.execute(f"SELECT COUNT(*) FROM {table} WHERE user_id = ?", (user_id,))
            assert left.fetchone()[0] == 0, f"còn dữ liệu trong {table}"
        relogin = browser(app).post("/auth/login", json={"email": "xoa@gmail.com", "password": PASSWORD})
        assert relogin.status_code == 401
        # Đăng ký lại cùng email được — tài khoản cũ đã thật sự biến mất.
        again = signed_up(app, "xoa@gmail.com")
        assert again.get("/auth/me").json()["user_id"] != user_id
        assert again.get("/auth/export").json()["attempts"] == []
