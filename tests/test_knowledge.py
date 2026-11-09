"""Thẻ kiến thức: đủ 70 kỹ năng, nội dung từ lời giải đã kiểm, tìm đúng thẻ cho câu hỏi."""

import pytest
from fastapi.testclient import TestClient

from src.api.app import build_service, create_app
from src.api.db import Store
from src.core.config import AppConfig
from src.knowledge.cards import all_cards, match_cards


def test_moi_ky_nang_mot_the_day_du():
    cards = all_cards()
    assert len(cards) == 70
    for card in cards:
        assert card.formulas and card.theory, card.skill_id
        assert card.example and card.example.steps, card.skill_id


def test_ly_thuyet_khong_lap_cau():
    for card in all_cards():
        assert len(card.theory) == len(set(card.theory)), card.skill_id


@pytest.mark.parametrize(("question", "skill"), [
    ("Tích phân từng phần tính thế nào?", "MAE.INT.PARTS"),
    ("định lý bayes", "MAS.PROB.BAYES"),
    ("p-value là gì", "MAS.HYP.PVALUE"),
    ("chu trinh euler", "MAD.GRAPH.EULER"),        # gõ không dấu
    ("Cây khung nhỏ nhất kruskal", "MAD.TREE.MST"),
    ("đạo hàm hàm hợp", "MAE.DER.CHAIN"),
    ("luật de morgan", "MAD.LOGIC.EQUIV"),
])
def test_tim_dung_the(question, skill):
    assert match_cards(question)[0].skill_id == skill


@pytest.mark.parametrize("question", ["Messi ghi bao nhiêu bàn", "cách nấu phở bò"])
def test_ngoai_pham_vi_khong_tra_the(question):
    assert match_cards(question) == []


def test_api_cong_khai():
    client = TestClient(create_app(build_service(AppConfig(), store=Store(":memory:"))))
    assert len(client.get("/knowledge", params={"subject": "MAD101"}).json()) == 18
    assert client.get("/knowledge/match", params={"q": "định lý bayes"}).json()[0]["skill_id"] == "MAS.PROB.BAYES"
    assert client.get("/knowledge/MAE.INT.PARTS").json()["example"]["steps"]
    assert client.get("/knowledge/KHONG.CO").status_code == 404
    assert client.get("/knowledge", params={"subject": "XYZ"}).status_code == 404
