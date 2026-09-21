"""Test tầng gia sư: chính sách leo thang, guardrail, engine.

Chạy hoàn toàn không cần LLM — chính sách và guardrail là logic thuần tuý, nên
có thể kiểm tra chặt chẽ và tất định.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.itembank import ERRORS_DIR, ItemBank, load_error_codes  # noqa: E402
from src.core.schema import AnswerType, Item, Subject, Submission  # noqa: E402
from src.tutor.guardrail import (  # noqa: E402
    check_leak,
    extract_expressions,
    leak_rate,
    reveals_answer,
)
from src.tutor.hint_policy import HintLevel, HintPolicy, PolicyConfig, TutorState  # noqa: E402
from src.tutor.hints import HintGenerator, TutorEngine  # noqa: E402
from src.verify.calculus import CalculusVerifier  # noqa: E402
from src.verify.equivalence import parse_math  # noqa: E402


@pytest.fixture(scope="module")
def bank() -> ItemBank:
    return ItemBank.load("MAE101")


@pytest.fixture
def item(bank: ItemBank) -> Item:
    return bank.get("MAE101-INT-010")  # ∫ x(x²+1)³ dx = (x²+1)⁴/8 + C


@pytest.fixture
def engine(bank: ItemBank) -> TutorEngine:
    generator = HintGenerator(
        error_codes=load_error_codes(ERRORS_DIR / "mae101.json"),
        skills=bank.skills,
        seed=42,
    )
    return TutorEngine(CalculusVerifier(), generator)


# ==========================================================================
# Chính sách leo thang
# ==========================================================================

class TestEscalationRules:
    def test_chua_lam_gi_thi_chi_khoi_goi(self) -> None:
        policy = HintPolicy()
        assert policy.decide(TutorState("X")) is HintLevel.PROBE

    def test_chi_leo_mot_muc_moi_luot(self) -> None:
        """Luật sống còn: không được nhảy cóc, nếu không ladder thành vô nghĩa."""
        policy = HintPolicy()
        state = TutorState("X", attempts=1)

        levels = []
        for _ in range(6):
            level = policy.decide(state, requested=True)
            state.record_hint(level)
            levels.append(int(level))

        assert levels == [1, 2, 3, 4, 4, 4], levels
        assert all(b - a <= 1 for a, b in zip(levels, levels[1:]))

    def test_leo_thang_tu_dong_khong_bao_gio_cham_loi_giai_day_du(self) -> None:
        policy = HintPolicy()
        state = TutorState("X", attempts=1)
        for _ in range(10):
            level = policy.decide(state, requested=True)
            state.record_hint(level)
        assert max(state.hints_given) < HintLevel.FULL

    def test_phai_doi_hai_lan_moi_duoc_loi_giai_day_du(self) -> None:
        policy = HintPolicy()
        state = TutorState("X", attempts=1)

        first = policy.decide(state, asked_for_solution=True)
        assert first < HintLevel.FULL, "Lần đòi đầu tiên chưa được cho"

        state.record_hint(first)
        second = policy.decide(state, asked_for_solution=True)
        assert second is HintLevel.FULL

    def test_khong_xin_them_thi_giu_nguyen_muc(self) -> None:
        policy = HintPolicy()
        state = TutorState("X", attempts=1)
        state.record_hint(HintLevel.CONCEPT)
        assert policy.decide(state) is HintLevel.CONCEPT

    def test_sai_lap_lai_cung_loi_thi_tu_dong_leo(self) -> None:
        policy = HintPolicy()
        state = TutorState("X", attempts=1)
        state.record_hint(HintLevel.CONCEPT)

        state.record_attempt(False, ("MAE.INT.CONSTFACTOR",))
        state.record_attempt(False, ("MAE.INT.CONSTFACTOR",))

        assert policy.decide(state) is HintLevel.PITFALL

    def test_sai_loi_khac_nhau_thi_khong_leo(self) -> None:
        """Sửa được lỗi cũ rồi mắc lỗi mới là đang tiến bộ, không phải bế tắc."""
        policy = HintPolicy()
        state = TutorState("X", attempts=1)
        state.record_hint(HintLevel.CONCEPT)

        state.record_attempt(False, ("MAE.INT.CONSTFACTOR",))
        state.record_attempt(False, ("MAE.SIGN",))

        assert policy.decide(state) is HintLevel.CONCEPT

    def test_lam_dung_thi_dat_lai_chuoi_sai(self) -> None:
        state = TutorState("X")
        state.record_attempt(False, ("MAE.SIGN",))
        state.record_attempt(False, ("MAE.SIGN",))
        assert state.consecutive_wrong == 2
        state.record_attempt(True)
        assert state.consecutive_wrong == 0


class TestMasteryAdaptation:
    def test_nam_vung_thi_chi_can_hich_nhe(self) -> None:
        policy = HintPolicy()
        state = TutorState("X", attempts=1)
        assert policy.decide(state, mastery=0.9) is HintLevel.PROBE

    def test_con_yeu_thi_canh_bao_bay_luon(self) -> None:
        policy = HintPolicy()
        state = TutorState("X", attempts=1)
        assert policy.decide(state, mastery=0.2) is HintLevel.PITFALL

    def test_chua_biet_nang_luc_thi_dung_mac_dinh(self) -> None:
        policy = HintPolicy()
        state = TutorState("X", attempts=1)
        assert policy.decide(state, mastery=None) is HintLevel.CONCEPT


class TestAblation:
    def test_tat_ladder_thi_tra_thang_loi_giai(self) -> None:
        """Nhóm đối chứng của EXP-7: chỉ đổi một cờ, không sửa code."""
        policy = HintPolicy(PolicyConfig(enabled=False))
        assert policy.decide(TutorState("X")) is HintLevel.FULL


# ==========================================================================
# Guardrail
# ==========================================================================

class TestExpressionExtraction:
    @pytest.mark.parametrize(
        "text, expected",
        [
            ("Đáp án là (x**2+1)**4/8 nhé", "(x**2+1)**4/8"),
            ("Kết quả: $x^3/3$", "x**3/3"),
            ("Em thử `2*x + 1` xem", "2*x + 1"),
        ],
    )
    def test_trich_duoc_bieu_thuc_trong_cau_van(self, text: str, expected: str) -> None:
        extracted = extract_expressions(text)
        target = parse_math(expected)
        assert any(e == target for e in extracted), f"Không trích được {expected} từ {text!r}"

    def test_cau_van_thuan_tuy_khong_sinh_bieu_thuc_rac(self) -> None:
        text = "Em đọc lại đề một lượt nhé, bài này cho gì và hỏi gì?"
        assert extract_expressions(text) == []


class TestLeakDetection:
    def test_chan_duoc_cau_lo_dap_an(self, item: Item) -> None:
        report = check_leak("Đáp án là (x**2+1)**4/8 + C", item, HintLevel.CONCEPT)
        assert report.leaked
        assert report.offending_expression is not None

    def test_chan_ca_dang_viet_khac_cua_dap_an(self, item: Item) -> None:
        """Lộ đáp án dưới dạng tương đương vẫn là lộ."""
        report = check_leak("Kết quả bằng (x**2+1)**4 / 8", item, HintLevel.PITFALL)
        assert report.leaked

    def test_khong_chan_goi_y_hop_le(self, item: Item) -> None:
        report = check_leak("Em thử đặt u = x**2 + 1 xem sao?", item, HintLevel.PITFALL)
        assert not report.leaked

    def test_nhac_lai_de_bai_khong_bi_coi_la_lo(self, item: Item) -> None:
        """Nhắc lại biểu thức dưới dấu tích phân là nhắc đề, không phải lộ đáp án."""
        report = check_leak("Ta cần tính nguyên hàm của x*(x**2+1)**3", item, HintLevel.CONCEPT)
        assert not report.leaked

    def test_muc_cao_duoc_phep_noi_dap_an(self, item: Item) -> None:
        report = check_leak("Đáp án là (x**2+1)**4/8 + C", item, HintLevel.FULL)
        assert not report.leaked

    def test_bat_duoc_dap_an_viet_o_dang_khai_trien(self, item: Item) -> None:
        """Dạng khai triển của đáp án cũng phải bị chặn, vì nó vẫn là đáp án."""
        expanded = str(parse_math("(x**2+1)**4/8").expand())
        assert reveals_answer(parse_math(expanded), item)

    def test_tinh_duoc_ti_le_ro(self, item: Item) -> None:
        reports = [
            check_leak("Đáp án là (x**2+1)**4/8", item, HintLevel.CONCEPT),
            check_leak("Em thử đặt u = x**2+1 nhé", item, HintLevel.CONCEPT),
        ]
        assert leak_rate(reports) == 0.5


# ==========================================================================
# Engine
# ==========================================================================

class TestEngine:
    def test_lam_dung_thi_khen_va_khong_goi_y(self, engine: TutorEngine, item: Item) -> None:
        response = engine.submit(
            item, Submission(item_id=item.item_id, final_answer="(x**2+1)**4/8 + C")
        )
        assert response.is_correct
        assert response.hint is None
        assert response.congratulation

    def test_dung_nhung_thieu_hang_so_thi_van_khen_kem_nhac(
        self, engine: TutorEngine, item: Item
    ) -> None:
        response = engine.submit(
            item, Submission(item_id=item.item_id, final_answer="(x**2+1)**4/8")
        )
        assert response.is_correct
        assert "lưu ý" in response.congratulation.lower()

    def test_sai_thi_goi_y_dung_loai_bay(self, engine: TutorEngine, item: Item) -> None:
        """Gợi ý mức 2 phải lấy đúng câu nhắc ứng với mã lỗi đã chẩn đoán."""
        submission = Submission(item_id=item.item_id, final_answer="(x**2+1)**4 + C")

        engine.submit(item, submission)                      # lượt 1
        response = engine.submit(item, submission)           # lượt 2, sai lặp lại
        while response.hint.level < HintLevel.PITFALL:
            response = engine.request_hint(item, response.verification)

        assert response.hint.level is HintLevel.PITFALL
        assert response.hint.source == "taxonomy"
        assert response.hint.error_code == "MAE.INT.CONSTFACTOR"

    def test_khong_goi_y_nao_bi_ro_dap_an(self, engine: TutorEngine, item: Item) -> None:
        """Chạy hết cả thang gợi ý, không mức nào dưới 4 được lộ đáp án."""
        submission = Submission(item_id=item.item_id, final_answer="(x**2+1)**4 + C")
        response = engine.submit(item, submission)

        for _ in range(6):
            assert not response.hint.was_blocked, (
                f"Mức {int(response.hint.level)} bị chặn: {response.hint.blocked_original}"
            )
            response = engine.request_hint(item, response.verification)

    def test_thang_goi_y_leo_dung_thu_tu(self, engine: TutorEngine, item: Item) -> None:
        submission = Submission(item_id=item.item_id, final_answer="(x**2+1)**4 + C")
        response = engine.submit(item, submission)

        levels = [int(response.hint.level)]
        for _ in range(4):
            response = engine.request_hint(item, response.verification)
            levels.append(int(response.hint.level))

        assert levels == sorted(levels), levels
        assert levels[0] < levels[-1], "Phải có leo thang"

    def test_loi_giai_day_du_co_du_cac_buoc(self, engine: TutorEngine, item: Item) -> None:
        response = engine.submit(
            item, Submission(item_id=item.item_id, final_answer="(x**2+1)**4 + C")
        )
        response = engine.request_hint(item, response.verification, asked_for_solution=True)
        response = engine.request_hint(item, response.verification, asked_for_solution=True)

        assert response.hint.level is HintLevel.FULL
        assert str(item.answer) in response.hint.text
        assert "Bước 1" in response.hint.text

    def test_moi_bai_co_trang_thai_rieng(self, engine: TutorEngine, bank: ItemBank) -> None:
        first, second = bank.get("MAE101-INT-001"), bank.get("MAE101-INT-010")
        engine.submit(first, Submission(item_id=first.item_id, final_answer="x**3 + C"))
        engine.submit(first, Submission(item_id=first.item_id, final_answer="x**3 + C"))

        assert engine.state_for(first.item_id).attempts == 2
        assert engine.state_for(second.item_id).attempts == 0
