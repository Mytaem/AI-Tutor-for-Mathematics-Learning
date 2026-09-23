"""Test học sinh mô phỏng và các tiêu chí chọn bài mới.

Học sinh ảo là nền của EXP-5 và EXP-6, nên sai ở đây thì mọi số liệu Gate 3 đều
sai theo mà không ai biết. Ba thứ được canh chặt:

1. **Tái lập được**: cùng seed phải ra cùng chuỗi tương tác.
2. **Hành vi đúng hướng**: người giỏi làm đúng nhiều hơn người kém, bài khó khó
   hơn bài dễ, luyện thì tiến bộ, và tiến bộ NHANH HƠN khi có gợi ý.
3. **Hệ thống không được nhìn trộm**: bộ chọn bài chỉ thấy đúng/sai, không thấy
   năng lực ẩn.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.itembank import ItemBank  # noqa: E402
from src.core.schema import AnswerType, Item, Subject  # noqa: E402
from src.kt.bkt import BKTTracker  # noqa: E402
from src.kt.selector import SelectorWeights, coverage_score, expected_success, score_item  # noqa: E402
from src.kt.simulator import (  # noqa: E402
    STRATEGIES,
    SimulatedStudent,
    StudentProfile,
    make_cohort,
    run_session,
    simulate_cohort,
    to_sequences,
)


def item(item_id: str, skills: list[str], difficulty: float = 0.5) -> Item:
    return Item(item_id=item_id, subject=Subject.MAE101, skills=skills,
                statement_vi="đề thử", answer_type=AnswerType.NUMBER, answer="1",
                difficulty=difficulty)


@pytest.fixture(scope="module")
def bank() -> ItemBank:
    return ItemBank.load("MAE101")


@pytest.fixture(scope="module")
def chapter(bank):
    skills = {k: v for k, v in bank.skills.items() if k.startswith("MAE.INT")}
    items = [i for i in bank.items.values() if i.skills and set(i.skills) <= set(skills)]
    return items, skills


class TestStudentBehaviour:
    def test_gioi_thi_lam_dung_nhieu_hon(self) -> None:
        task = item("i1", ["S"])
        strong = SimulatedStudent("a", {"S": 2.0})
        weak = SimulatedStudent("b", {"S": -2.0})
        assert strong.probability_correct(task) > weak.probability_correct(task)

    def test_bai_kho_thi_xac_suat_dung_thap_hon(self) -> None:
        student = SimulatedStudent("a", {"S": 0.5})
        assert student.probability_correct(item("dễ", ["S"], 0.2)) > \
               student.probability_correct(item("khó", ["S"], 0.9))

    def test_bai_nhieu_ky_nang_phu_thuoc_ky_nang_yeu_nhat(self) -> None:
        """Một mắt xích hỏng là hỏng cả bài — không lấy trung bình."""
        student = SimulatedStudent("a", {"mạnh": 3.0, "yếu": -3.0})
        both = student.probability_correct(item("i", ["mạnh", "yếu"]))
        only_weak = student.probability_correct(item("i", ["yếu"]))
        assert both == pytest.approx(only_weak)

    def test_slip_va_guess_giu_xac_suat_trong_khoang(self) -> None:
        profile = StudentProfile()
        for ability in (-10.0, 0.0, 10.0):
            probability = SimulatedStudent("a", {"S": ability}, profile).probability_correct(item("i", ["S"]))
            assert profile.guess - 1e-9 <= probability <= 1 - profile.slip + 1e-9

    def test_luyen_thi_tien_bo(self) -> None:
        student = SimulatedStudent("a", {"S": 0.0})
        before = student.ability["S"]
        student.learn(item("i", ["S"]), correct=True, with_hint=False)
        assert student.ability["S"] > before

    def test_co_goi_y_thi_hoc_tu_loi_nhanh_hon(self) -> None:
        """Giả thiết sư phạm của cả đồ án — ablation --no-hint của EXP-6 dựa vào đây."""
        with_hint = SimulatedStudent("a", {"S": 0.0})
        without = SimulatedStudent("b", {"S": 0.0})
        with_hint.learn(item("i", ["S"]), correct=False, with_hint=True)
        without.learn(item("i", ["S"]), correct=False, with_hint=False)
        assert with_hint.ability["S"] > without.ability["S"]

    def test_ky_nang_sau_trong_dag_thi_khoi_dau_yeu_hon(self, bank) -> None:
        cohort = make_cohort(40, bank.skills, seed=3)
        basic = sum(s.ability["MAE.INT.BASIC"] for s in cohort) / len(cohort)
        advanced = sum(s.ability["MAE.INT.SUBST"] for s in cohort) / len(cohort)
        assert advanced < basic, "kỹ năng có tiên quyết phải khởi đầu thấp hơn"


class TestSession:
    @pytest.mark.parametrize("strategy", STRATEGIES)
    def test_moi_chien_luoc_chay_duoc_va_sinh_du_luot(self, chapter, strategy: str) -> None:
        items, skills = chapter
        student = make_cohort(1, skills, seed=5)[0]
        result = run_session(student, items, skills, strategy=strategy, steps=15, seed=5)
        assert len({i.step for i in result.interactions}) == 15
        assert 0.0 <= result.accuracy <= 1.0

    def test_cung_seed_ra_cung_ket_qua(self, chapter) -> None:
        items, skills = chapter
        runs = [
            [(i.item_id, i.correct) for i in
             run_session(make_cohort(1, skills, seed=9)[0], items, skills, steps=20, seed=9).interactions]
            for _ in range(2)
        ]
        assert runs[0] == runs[1]

    def test_doi_seed_ra_ket_qua_khac(self, chapter) -> None:
        items, skills = chapter
        first = run_session(make_cohort(1, skills, seed=1)[0], items, skills, steps=20, seed=1)
        second = run_session(make_cohort(1, skills, seed=2)[0], items, skills, steps=20, seed=2)
        assert [i.item_id for i in first.interactions] != [i.item_id for i in second.interactions]

    def test_khong_lap_lai_bai_da_lam_khi_con_bai_moi(self, chapter) -> None:
        """Phạt lặp lại của bộ chọn: còn bài mới thì không cho làm lại bài cũ."""
        items, skills = chapter
        student = make_cohort(1, skills, seed=4)[0]
        result = run_session(student, items, skills, strategy="zpd", steps=12, seed=4)
        used = [i.item_id for i in result.interactions]
        assert len(set(used)) == len({i.step for i in result.interactions})

    def test_chuoi_cho_dkt_dung_dinh_dang(self, chapter) -> None:
        items, skills = chapter
        results = simulate_cohort(items, skills, students=3, steps=10, seed=6)
        sequences = to_sequences(results)
        assert len(sequences) == 3
        assert all(skill in skills and answer in (0, 1)
                   for sequence in sequences for skill, answer in sequence)

    def test_khong_gio_y_thi_hoc_it_hon(self, chapter) -> None:
        items, skills = chapter
        with_hint = simulate_cohort(items, skills, students=25, steps=40, seed=8, with_hint=True)
        without = simulate_cohort(items, skills, students=25, steps=40, seed=8, with_hint=False)
        assert (sum(r.mastered_skills for r in with_hint)
                > sum(r.mastered_skills for r in without))


class TestSelectorCriteria:
    def test_do_kho_anh_huong_xac_suat_uoc_luong(self) -> None:
        """Hồi quy: bản cũ bỏ qua độ khó nên mọi bài cùng kỹ năng đều như nhau."""
        tracker = BKTTracker()
        tracker.set_mastery("S", 0.6)
        easy = expected_success(item("dễ", ["S"], 0.1), tracker)
        hard = expected_success(item("khó", ["S"], 0.9), tracker)
        assert easy > hard

    def test_phu_ky_nang_uu_tien_ky_nang_it_luyen(self) -> None:
        practised = {"đã_luyện": 10, "chưa": 0}
        assert coverage_score(item("i", ["chưa"]), practised) > \
               coverage_score(item("i", ["đã_luyện"]), practised)

    def test_khong_truyen_lich_su_thi_tieu_chi_phu_vo_hieu(self) -> None:
        assert coverage_score(item("i", ["S"]), None) == 1.0

    def test_trong_so_phu_lam_doi_lua_chon(self) -> None:
        tracker = BKTTracker()
        candidates = [item("cũ", ["đã_luyện"], 0.5), item("mới", ["chưa"], 0.5)]
        practised = {"đã_luyện": 8, "chưa": 0}
        weights = SelectorWeights(coverage=6.0)
        scores = {i.item_id: score_item(i, tracker, {}, set(), weights, practised) for i in candidates}
        assert scores["mới"] > scores["cũ"]
