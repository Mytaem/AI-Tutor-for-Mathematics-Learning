"""Test khởi tạo năng lực cho người học mới và bài kiểm tra đầu vào.

Lý do phải có phần này: nếu mọi kỹ năng cùng một tiên nghiệm thì bộ chọn bài gần
như chọn tuỳ ý trong vài lượt đầu, và dữ liệu thu được từ người dùng thật ở
những lượt đó là nhiễu — không dùng cho EXP-5, EXP-6 được.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.itembank import ItemBank  # noqa: E402
from src.kt.bkt import BKTTracker  # noqa: E402
from src.kt.coldstart import (  # noqa: E402
    FLOOR_PRIOR,
    PLACEMENT_LENGTH,
    initial_mastery,
    is_placement_done,
    make_tracker,
    placement_score,
    propagate_prerequisites,
    select_placement_item,
    skill_depths,
    uncertainty,
)


@pytest.fixture(scope="module")
def bank() -> ItemBank:
    return ItemBank.load("MAE101")


class TestSkillDepth:
    def test_ky_nang_nen_tang_co_do_sau_0(self, bank: ItemBank) -> None:
        depths = skill_depths(bank.skills)
        assert depths["MAE.LIM.BASIC"] == 0, "Giới hạn cơ bản không cần kỹ năng nào trước"

    def test_do_sau_tang_theo_chuoi_tien_quyet(self, bank: ItemBank) -> None:
        depths = skill_depths(bank.skills)
        # MAE.LIM.BASIC -> MAE.DER.BASIC -> MAE.INT.BASIC -> MAE.INT.SUBST
        assert depths["MAE.DER.BASIC"] > depths["MAE.LIM.BASIC"]
        assert depths["MAE.INT.BASIC"] > depths["MAE.DER.BASIC"]
        assert depths["MAE.INT.SUBST"] > depths["MAE.INT.BASIC"]

    def test_moi_ky_nang_deu_co_do_sau(self, bank: ItemBank) -> None:
        assert set(skill_depths(bank.skills)) == set(bank.skills)


class TestInitialMastery:
    def test_khong_con_phang_nua(self, bank: ItemBank) -> None:
        """Đây chính là bug cần sửa: trước đây mọi kỹ năng cùng một giá trị."""
        values = set(initial_mastery(bank.skills).values())
        assert len(values) > 1, "Tiên nghiệm phải phân biệt được kỹ năng nền tảng với kỹ năng sâu"

    def test_ky_nang_nen_tang_cao_hon_ky_nang_sau(self, bank: ItemBank) -> None:
        priors = initial_mastery(bank.skills)
        assert priors["MAE.LIM.BASIC"] > priors["MAE.INT.SUBST"]
        assert priors["MAE.DER.BASIC"] > priors["MAE.INT.DEF.SUBST"]

    def test_khong_tut_xuong_duoi_san(self, bank: ItemBank) -> None:
        assert all(v >= FLOOR_PRIOR for v in initial_mastery(bank.skills).values())

    def test_nam_trong_khoang_hop_le(self, bank: ItemBank) -> None:
        assert all(0.0 <= v <= 1.0 for v in initial_mastery(bank.skills).values())


class TestMakeTracker:
    def test_du_lieu_da_luu_de_len_tien_nghiem(self, bank: ItemBank) -> None:
        tracker = make_tracker(bank.skills, {"MAE.INT.SUBST": 0.88})
        assert tracker.mastery("MAE.INT.SUBST") == 0.88

    def test_ky_nang_chua_co_du_lieu_dung_tien_nghiem(self, bank: ItemBank) -> None:
        tracker = make_tracker(bank.skills, {"MAE.INT.SUBST": 0.88})
        priors = initial_mastery(bank.skills)
        assert tracker.mastery("MAE.LIM.BASIC") == priors["MAE.LIM.BASIC"]


class TestPrerequisitePropagation:
    def test_lam_dung_bai_sau_thi_nang_ca_tien_quyet(self, bank: ItemBank) -> None:
        """Giải được tích phân đổi biến thì đương nhiên biết quy tắc hàm hợp."""
        tracker = make_tracker(bank.skills)
        before = tracker.mastery("MAE.DER.CHAIN")

        propagate_prerequisites(tracker, bank.skills, ["MAE.INT.SUBST"])

        assert tracker.mastery("MAE.DER.CHAIN") > before

    def test_lan_truyen_qua_nhieu_tang(self, bank: ItemBank) -> None:
        tracker = make_tracker(bank.skills)
        propagate_prerequisites(tracker, bank.skills, ["MAE.INT.DEF.SUBST"])

        # MAE.INT.DEF.SUBST -> MAE.INT.SUBST -> MAE.INT.BASIC -> MAE.DER.BASIC
        assert tracker.mastery("MAE.DER.BASIC") >= 0.6, "Phải lan tới tận gốc"

    def test_chi_nang_khong_bao_gio_ha(self, bank: ItemBank) -> None:
        """Người đã thạo tiên quyết không được bị hạ xuống chỉ vì lan truyền."""
        tracker = make_tracker(bank.skills)
        tracker.set_mastery("MAE.DER.CHAIN", 0.95)

        propagate_prerequisites(tracker, bank.skills, ["MAE.INT.SUBST"])

        assert tracker.mastery("MAE.DER.CHAIN") == 0.95

    def test_ky_nang_khong_ton_tai_khong_gay_loi(self, bank: ItemBank) -> None:
        tracker = make_tracker(bank.skills)
        assert propagate_prerequisites(tracker, bank.skills, ["KHONG.CO.THAT"]) == {}


class TestUncertainty:
    def test_cao_nhat_o_giua(self) -> None:
        assert uncertainty(0.5) == 1.0

    def test_thap_o_hai_dau(self) -> None:
        """Biết chắc là giỏi hoặc chắc là chưa biết thì hỏi thêm cũng vô ích."""
        assert uncertainty(0.0) == pytest.approx(0.0)
        assert uncertainty(1.0) == pytest.approx(0.0)

    def test_doi_xung(self) -> None:
        assert uncertainty(0.3) == pytest.approx(uncertainty(0.7))


class TestPlacementSelection:
    def test_uu_tien_ky_nang_chua_duoc_hoi(self, bank: ItemBank) -> None:
        tracker = make_tracker(bank.skills)
        items = list(bank.items.values())

        first = select_placement_item(items, tracker, covered_skills=set())
        assert first is not None

        second = select_placement_item(
            items, tracker,
            covered_skills=set(first.skills),
            exclude={first.item_id},
        )
        assert second is not None
        assert not set(second.skills) <= set(first.skills), "Phải chuyển sang kỹ năng mới"

    def test_khong_hoi_lai_bai_da_lam(self, bank: ItemBank) -> None:
        tracker = make_tracker(bank.skills)
        items = list(bank.items.values())
        done = {item.item_id for item in items[:-1]}

        chosen = select_placement_item(items, tracker, set(), exclude=done)
        assert chosen is not None and chosen.item_id not in done

    def test_het_bai_thi_tra_none(self, bank: ItemBank) -> None:
        items = list(bank.items.values())
        chosen = select_placement_item(
            items, make_tracker(bank.skills), set(),
            exclude={item.item_id for item in items},
        )
        assert chosen is None

    def test_bai_da_biet_chac_ket_qua_thi_diem_thap(self, bank: ItemBank) -> None:
        """Bài chắc chắn làm được không cho thêm thông tin nào."""
        item = bank.get("MAE101-INT-001")

        certain = BKTTracker()
        for skill in item.skills:
            certain.set_mastery(skill, 0.99)

        unsure = BKTTracker()
        for skill in item.skills:
            unsure.set_mastery(skill, 0.5)

        assert placement_score(item, certain, set()) < placement_score(item, unsure, set())

    def test_do_dai_bai_kiem_tra(self) -> None:
        assert not is_placement_done(PLACEMENT_LENGTH - 1)
        assert is_placement_done(PLACEMENT_LENGTH)
