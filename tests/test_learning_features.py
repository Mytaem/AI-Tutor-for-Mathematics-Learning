"""Lịch sử, ôn lỗi sai, chuỗi ngày học, lời giải mẫu sau khi làm đúng."""

import pytest
from fastapi.testclient import TestClient

from src.api.app import build_service, create_app
from src.api.db import Store
from src.core.config import AppConfig


@pytest.fixture()
def learner():
    service = build_service(AppConfig(), store=Store(":memory:"))
    client = TestClient(create_app(service))
    client.post("/auth/register", json={"email": "hoc@gmail.com", "password": "matkhau123"})
    session = client.post("/session/start", json={"subject": "MAS291"}).json()
    return client, service, session


def submit(client, session, item_id, answer):
    return client.post("/attempt", json={"session_id": session["session_id"], "item_id": item_id,
                                         "final_answer": answer}).json()


def test_lich_su_va_on_loi_sai(learner):
    client, service, session = learner
    item = session["first_item"]
    correct = service.find_item(item["item_id"]).answer_text
    assert client.get("/item/review", params={"subject": "MAS291"}).status_code == 404

    submit(client, session, item["item_id"], "0.987654")              # sai
    history = client.get("/me/history").json()
    assert history[0]["verdict"] == "wrong" and history[0]["statement"]
    assert client.get("/me/history", params={"only_wrong": True}).json()[0]["item_id"] == item["item_id"]
    assert client.get("/item/review", params={"subject": "MAS291"}).json()["item_id"] == item["item_id"]

    submit(client, session, item["item_id"], correct)                  # làm lại đúng
    assert client.get("/item/review", params={"subject": "MAS291"}).status_code == 404
    assert client.get("/me/history", params={"only_wrong": True}).json() == [] or \
        all(row["item_id"] != item["item_id"] or row["verdict"] == "wrong"
            for row in client.get("/me/history", params={"only_wrong": True}).json())


def test_loi_giai_mau_chi_mo_sau_khi_lam_dung(learner):
    client, service, session = learner
    item_id = session["first_item"]["item_id"]
    assert client.get(f"/item/{item_id}/solution").status_code == 403
    submit(client, session, item_id, "0.987654")
    assert client.get(f"/item/{item_id}/solution").status_code == 403   # sai vẫn chưa được xem
    submit(client, session, item_id, service.find_item(item_id).answer_text)
    solution = client.get(f"/item/{item_id}/solution").json()
    assert solution["steps"] and solution["answer"]


def test_thong_ke_chuoi_ngay(learner):
    client, service, session = learner
    stats = client.get("/me/stats").json()
    assert stats["streak_days"] == 0 and stats["today_attempts"] == 0 and len(stats["last14"]) == 14
    item = session["first_item"]
    submit(client, session, item["item_id"], service.find_item(item["item_id"]).answer_text)
    stats = client.get("/me/stats").json()
    assert stats["streak_days"] == 1 and stats["today_attempts"] == 1 and stats["today_correct"] == 1
    assert stats["last14"][-1]["attempts"] == 1


def test_chua_dang_nhap_bi_chan():
    client = TestClient(create_app(build_service(AppConfig(), store=Store(":memory:"))))
    for path in ("/me/history", "/me/stats", "/item/review", "/item/MAS291-PROB-001/solution"):
        assert client.get(path).status_code == 401, path
