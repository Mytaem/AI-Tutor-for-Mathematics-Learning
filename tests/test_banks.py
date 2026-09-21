"""Test toàn vẹn cho ngân hàng đề của MỌI môn đã có verifier.

Chạy qua registry, nên khi thêm một môn mới (MAD101, MAS291), bộ test này tự áp
dụng mà không phải viết lại. Test quan trọng nhất là đáp án chuẩn phải tự verify
được: nếu đỏ thì hoặc đáp án trong ngân hàng bị gõ sai, hoặc verifier có lỗ hổng
— và khi đó mọi số liệu thực nghiệm đều vô nghĩa.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.itembank import ItemBank, load_course_error_codes  # noqa: E402
from src.core.schema import Submission  # noqa: E402
from src.verify.registry import supported_subjects, verifier_for  # noqa: E402

SUBJECTS = [s.value for s in supported_subjects()]


@pytest.fixture(scope="module", params=SUBJECTS)
def subject(request) -> str:
    return request.param


@pytest.fixture(scope="module")
def bank(subject: str) -> ItemBank:
    return ItemBank.load(subject)


def test_du_so_bai_toi_thieu(bank: ItemBank) -> None:
    assert len(bank.items) >= 20
    assert len(bank.skills) >= 10


def test_khong_tham_chieu_ky_nang_la(bank: ItemBank) -> None:
    assert bank.unknown_skill_references() == []


def test_do_thi_tien_quyet_la_dag(bank: ItemBank) -> None:
    assert bank.prerequisite_cycles() == []
    assert bank.orphan_prerequisites() == []


def test_ma_bai_dung_tien_to_mon(bank: ItemBank, subject: str) -> None:
    """Tiền tố mã bài là cách API biết một bài thuộc môn nào."""
    assert all(item_id.startswith(subject) for item_id in bank.items)
    assert all(item.subject.value == subject for item in bank.items.values())


def test_taxonomy_loi_hop_le(bank: ItemBank, subject: str) -> None:
    codes = load_course_error_codes(subject)
    assert len(codes) >= 12, "Mục tiêu trong PLAN.md: ≥ 12 mã lỗi mỗi môn"
    for code in codes.values():
        assert code.hint_vi, f"{code.code} thiếu câu gợi ý cho hint mức 2"
        assert code.skill_id is None or code.skill_id in bank.skills, f"{code.code} trỏ tới kỹ năng lạ"


def test_moi_dap_an_chuan_tu_verify_duoc(bank: ItemBank, subject: str) -> None:
    verifier = verifier_for(subject)
    failures = []
    for item in bank.items.values():
        result = verifier.verify(item, Submission(item_id=item.item_id, final_answer=item.answer_text))
        if result.final_answer_correct is not True:
            failures.append(f"{item.item_id}: {result.notes}")
    assert failures == [], "\n".join(failures)


def test_loi_giai_mau_khong_bi_bao_sai(bank: ItemBank, subject: str) -> None:
    verifier = verifier_for(subject)
    failures = []
    for item in bank.items.values():
        if item.reference_solution_steps:
            for c in verifier.check_steps(item, [s.expr for s in item.reference_solution_steps]):
                if c.ok is False:
                    failures.append(f"{item.item_id} bước {c.step}: {c.reason}")
    assert failures == [], "\n".join(failures)
