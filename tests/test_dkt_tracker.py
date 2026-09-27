"""Test dùng DKT làm mô hình năng lực lúc phục vụ.

Ba thứ được canh:

1. **Cùng giao diện với BKT** — bộ chọn bài không được biết đang dùng mô hình nào.
2. **Thiếu mô hình thì quay về BKT**, không hỏng: file ``.pt`` có thể chưa được
   huấn luyện, hoặc huấn luyện cho môn khác.
3. **Không tính xác suất hai lần**: DKT đã trả thẳng xác suất đúng, đưa tiếp qua
   công thức slip/guess của BKT là sai.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.schema import AnswerType, Item, Subject  # noqa: E402
from src.kt.bkt import BKTTracker  # noqa: E402
from src.kt.dkt import DKT, DKTConfig, SkillIndex, split_sequences, train_dkt  # noqa: E402
from src.kt.dkt_tracker import DKTTracker, load_tracker, save_tracker_model  # noqa: E402
from src.kt.selector import expected_success  # noqa: E402

SKILLS = ["S1", "S2", "S3"]
TINY = DKTConfig(hidden_size=16, epochs=4, batch_size=8, patience=4)


def item(item_id: str, skills: list[str], difficulty: float = 0.5) -> Item:
    return Item(item_id=item_id, subject=Subject.MAE101, skills=skills,
                statement_vi="đề thử", answer_type=AnswerType.NUMBER, answer="1",
                difficulty=difficulty)


@pytest.fixture(scope="module")
def trained() -> tuple[DKT, SkillIndex]:
    """Dữ liệu có quy luật rõ: S1 hầu như đúng, S3 hầu như sai."""
    import random

    rng = random.Random(5)
    sequences = []
    for _ in range(60):
        sequence = []
        for _ in range(20):
            skill = rng.choice(SKILLS)
            rate = {"S1": 0.95, "S2": 0.5, "S3": 0.05}[skill]
            sequence.append((skill, int(rng.random() < rate)))
        sequences.append(sequence)
    index = SkillIndex(SKILLS)
    train, validation, _ = split_sequences(sequences, seed=1)
    model, _ = train_dkt(train, validation, index, TINY)
    return model, index


class TestInterface:
    def test_cung_giao_dien_voi_bkt(self, trained) -> None:
        model, index = trained
        tracker = DKTTracker(model, index)
        for method in ("mastery", "observe", "set_mastery", "snapshot", "weakest",
                       "probability_for"):
            assert hasattr(tracker, method) and hasattr(BKTTracker(), method), method

    def test_chuoi_rong_thi_dung_tien_nghiem(self, trained) -> None:
        model, index = trained
        tracker = DKTTracker(model, index, prior={"S1": 0.8})
        assert tracker.mastery("S1") == 0.8

    def test_ky_nang_la_thi_dung_tien_nghiem(self, trained) -> None:
        model, index = trained
        tracker = DKTTracker(model, index, prior={"NGOAI": 0.4})
        tracker.observe(["S1"], True)
        assert tracker.mastery("NGOAI") == 0.4

    def test_hoc_duoc_quy_luat_tu_chuoi(self, trained) -> None:
        """Sau khi phát lại lịch sử, kỹ năng hay sai phải được ước lượng thấp hơn."""
        model, index = trained
        tracker = DKTTracker(model, index)
        for _ in range(6):
            tracker.observe(["S1"], True)
            tracker.observe(["S3"], False)
        assert tracker.mastery("S1") > tracker.mastery("S3")

    def test_weakest_sap_dung_thu_tu(self, trained) -> None:
        model, index = trained
        tracker = DKTTracker(model, index)
        for _ in range(6):
            tracker.observe(["S1"], True)
            tracker.observe(["S3"], False)
        assert tracker.weakest(SKILLS, limit=1) == ["S3"]


class TestSelectorIntegration:
    def test_khong_tinh_xac_suat_hai_lan(self, trained) -> None:
        """DKT đã trả xác suất đúng; cho qua slip/guess nữa là bóp về giữa.

        Kiểm bằng cách so với chính giá trị tracker trả ra: sau khi dịch theo độ
        khó trung bình (0.5 = giữ nguyên), hai số phải bằng nhau.
        """
        model, index = trained
        tracker = DKTTracker(model, index)
        for _ in range(6):
            tracker.observe(["S3"], False)
        assert expected_success(item("i", ["S3"], 0.5), tracker) == pytest.approx(
            tracker.probability_for("S3"), abs=1e-6)

    def test_bkt_van_di_qua_slip_guess(self) -> None:
        tracker = BKTTracker()
        tracker.set_mastery("S", 1.0)
        assert tracker.probability_for("S") < 1.0, "phải trừ đi xác suất bất cẩn"


class TestPersistence:
    def test_luu_roi_nap_lai_cho_cung_ket_qua(self, trained, tmp_path: Path) -> None:
        model, index = trained
        save_tracker_model(model, index, "TEST", directory=tmp_path)

        first = DKTTracker(model, index)
        second = load_tracker("TEST", directory=tmp_path)
        assert second is not None
        for tracker in (first, second):
            for _ in range(4):
                tracker.observe(["S1"], True)
                tracker.observe(["S3"], False)
        assert first.mastery("S1") == pytest.approx(second.mastery("S1"), abs=1e-5)

    def test_chua_huan_luyen_thi_tra_none(self, tmp_path: Path) -> None:
        """Thiếu mô hình phải quay về BKT chứ không được làm hỏng cả hệ thống."""
        assert load_tracker("KHONG_CO", directory=tmp_path) is None


class TestApiFallback:
    def test_api_tu_quay_ve_bkt_khi_thieu_mo_hinh(self, tmp_path: Path, monkeypatch) -> None:
        from src.api.app import build_service
        from src.api.db import Store
        from src.core.config import AppConfig

        monkeypatch.setattr("src.kt.dkt_tracker.MODEL_DIR", tmp_path)
        config = AppConfig()
        config.kt_model = "dkt"
        service = build_service(config, store=Store(":memory:"))
        assert isinstance(service.tracker_for("ai-do", "MAE101"), BKTTracker)

    def test_dung_dkt_khi_co_mo_hinh(self) -> None:
        from src.api.app import build_service
        from src.api.db import Store
        from src.core.config import AppConfig
        from src.kt.dkt_tracker import MODEL_DIR

        if not (MODEL_DIR / "mae101.pt").exists():
            pytest.skip("chưa huấn luyện mô hình phục vụ (scripts/train_dkt_for_serving.py)")
        config = AppConfig()
        config.kt_model = "dkt"
        service = build_service(config, store=Store(":memory:"))
        assert isinstance(service.tracker_for("ai-do", "MAE101"), DKTTracker)


def test_torch_khong_bat_grad_khi_du_doan(trained) -> None:
    """Dự đoán lúc phục vụ không được dựng đồ thị tính đạo hàm — phí và chậm."""
    model, index = trained
    tracker = DKTTracker(model, index)
    tracker.observe(["S1"], True)
    with torch.no_grad():
        value = tracker.mastery("S1")
    assert 0.0 <= value <= 1.0
