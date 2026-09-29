"""Test bộ sinh đề đại số tuyến tính dùng chung cho MAE101 và MAI391.

Điều đáng canh nhất: **cùng một dạng bài phải gắn đúng mã kỹ năng của từng môn**.
Hai môn dạy chung mảng kiến thức và dùng chung bảng mã lỗi `LA.*`, nhưng mã kỹ
năng thì khác (`MAE.LA.DET` với `MAI.DEC.TRACE`) — gắn nhầm thì mô hình năng lực
cập nhật vào kỹ năng không tồn tại của môn đó, và bộ chọn bài mù luôn phần này.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.itembank import ItemBank  # noqa: E402
from src.core.schema import Submission, Subject  # noqa: E402
from src.data_gen.bank_builder import Registry  # noqa: E402
from src.data_gen.linalg_items import BUILDERS, SKILL_MAP, generate, register_all, template_ids  # noqa: E402
from src.verify.registry import verifier_for  # noqa: E402


@pytest.fixture(scope="module")
def items():
    return generate(len(template_ids()) * 2, validate=True)


class TestGeneration:
    def test_moi_dang_bai_sinh_duoc(self, items) -> None:
        produced = {item.meta.get("template") for item in items}
        missing = [name for name in template_ids() if name not in produced]
        assert missing == [], f"dạng bài không sinh được: {missing}"

    def test_bai_sinh_ra_tu_cham_dung(self, items) -> None:
        verifier = verifier_for("MAE101")
        for item in items:
            result = verifier.verify(item, Submission(
                item_id=item.item_id, final_answer=item.answer_text))
            assert result.final_answer_correct is True, f"{item.item_id}: {item.statement_vi}"

    def test_de_giai_he_co_loi_giai_theo_buoc(self, items) -> None:
        """Không có lời giải theo bước thì mã lỗi mức bước LA.ROWOP.INVALID không có mẫu."""
        systems = [i for i in items if i.meta.get("template") == "linear_system"]
        assert systems and all(len(i.reference_solution_steps) >= 3 for i in systems)

    def test_ma_tran_suy_bien_tra_dap_an_bang_loi(self, items) -> None:
        singular = [i for i in items if i.meta.get("template") == "inverse_singular"]
        assert singular and all(i.answer_text == "không khả nghịch" for i in singular)


class TestSkillMapping:
    def test_mae101_dung_ma_ky_nang_cua_mae101(self, items) -> None:
        bank = ItemBank.load("MAE101")
        for item in items:
            assert item.subject is Subject.MAE101
            for skill in item.skills:
                assert skill in bank.skills, f"{item.item_id} gắn kỹ năng lạ: {skill}"

    def test_mai391_dung_ma_ky_nang_cua_mai391(self) -> None:
        registry = Registry(Subject.MAI391, "MAI391")
        register_all(registry, "MAI391")
        generated = registry.generate(len(registry.templates), validate=True)
        bank = ItemBank.load("MAI391")
        assert generated
        for item in generated:
            for skill in item.skills:
                assert skill in bank.skills, f"{item.item_id} gắn kỹ năng lạ: {skill}"

    def test_moi_dang_bai_deu_co_ma_ky_nang_cho_ca_hai_mon(self) -> None:
        """Thiếu một môn thì dạng bài đó lặng lẽ biến mất khỏi môn ấy."""
        for subject, mapping in SKILL_MAP.items():
            missing = [name for name in BUILDERS if name not in mapping]
            assert missing == [], f"{subject} thiếu mã kỹ năng cho: {missing}"


class TestReproducible:
    def test_cung_seed_ra_cung_de(self) -> None:
        first = generate(6, seed=99, validate=False)
        second = generate(6, seed=99, validate=False)
        assert [i.statement_vi for i in first] == [i.statement_vi for i in second]
        assert [i.answer_text for i in first] == [i.answer_text for i in second]
