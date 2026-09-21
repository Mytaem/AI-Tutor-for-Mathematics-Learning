"""Test bộ sinh bài tập theo template.

Test quan trọng nhất là ``test_moi_bai_sinh_ra_deu_tu_verify_duoc`` chạy với
``validate=False``. Lý do: ở chế độ mặc định, bài nào verifier không xác nhận sẽ
bị lặng lẽ loại bỏ — rất tiện khi dùng, nhưng lại che mất template hỏng. Tắt bộ
lọc đi thì mới đo được tỉ lệ đúng THẬT của từng template.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.itembank import ItemBank  # noqa: E402
from src.core.schema import AnswerType, Item, Submission  # noqa: E402
from src.data_gen.item_generator import generate, template_ids  # noqa: E402
from src.verify.calculus import CalculusVerifier  # noqa: E402
from src.verify.equivalence import parse_math  # noqa: E402


#: Cỡ mẫu nhỏ để vòng lặp phát triển còn nhanh. ``sp.integrate`` tốn ~0.5 giây
#: mỗi bài, nên sinh vài trăm bài trong test là không chấp nhận được. Kiểm định ở
#: quy mô thật (300 bài) chạy bằng scripts/build_bank.py.
SAMPLE = 40


@pytest.fixture(scope="module")
def items() -> list[Item]:
    return generate(SAMPLE, seed=2026)


@pytest.fixture(scope="module")
def raw_items() -> list[Item]:
    """Sinh KHÔNG lọc — để đo chất lượng thật của template."""
    return generate(SAMPLE, seed=2026, validate=False)


class TestGeneration:
    def test_sinh_du_so_luong(self, items: list[Item]) -> None:
        assert len(items) == SAMPLE

    def test_ma_bai_khong_trung(self, items: list[Item]) -> None:
        ids = [item.item_id for item in items]
        assert len(ids) == len(set(ids))

    def test_khong_sinh_bai_trung_lap(self, items: list[Item]) -> None:
        fingerprints = [(item.integrand, item.bounds) for item in items]
        assert len(fingerprints) == len(set(fingerprints))

    def test_phu_het_template(self, items: list[Item]) -> None:
        used = {item.meta["template"] for item in items}
        missing = set(template_ids()) - used
        assert missing == set(), f"Template chưa sinh được bài nào: {missing}"

    def test_tai_lap_duoc_voi_cung_seed(self) -> None:
        """Kết quả trong báo cáo phải tái lập được — cùng seed phải cho cùng bộ đề."""
        first = generate(8, seed=123, validate=False)
        second = generate(8, seed=123, validate=False)
        assert [i.integrand for i in first] == [i.integrand for i in second]

    def test_seed_khac_cho_de_khac(self) -> None:
        first = generate(8, seed=1, validate=False)
        second = generate(8, seed=2, validate=False)
        assert [i.integrand for i in first] != [i.integrand for i in second]


class TestSoundness:
    def test_moi_bai_sinh_ra_deu_tu_verify_duoc(self, raw_items: list[Item]) -> None:
        """Không có bộ lọc che chắn, mọi template vẫn phải sinh ra bài đúng."""
        verifier = CalculusVerifier()
        failures: list[str] = []

        for item in raw_items:
            result = verifier.verify(
                item, Submission(item_id=item.item_id, final_answer=str(item.answer))
            )
            if result.final_answer_correct is not True:
                failures.append(f"{item.meta['template']}: ∫{item.integrand} -> {item.answer}")

        rate = 1 - len(failures) / len(raw_items)
        assert failures == [], (
            f"Tỉ lệ đúng {rate:.1%}. Các bài verifier không xác nhận:\n" + "\n".join(failures[:10])
        )

    def test_tich_phan_xac_dinh_ra_so_khong_con_bien(self, items: list[Item]) -> None:
        """Kiểm tra bằng free_symbols, không so khớp chuỗi.

        Chuỗi "exp(3)" có chứa ký tự 'x' nhưng hoàn toàn không có biến nào —
        đây đúng là kiểu bẫy mà việc so khớp chuỗi trên biểu thức toán hay mắc.
        """
        for item in items:
            if item.answer_type is AnswerType.NUMBER:
                symbols = parse_math(str(item.answer)).free_symbols
                assert symbols == set(), f"{item.item_id}: đáp án còn chứa biến {symbols}"

    def test_nguyen_ham_deu_co_hang_so_C(self, items: list[Item]) -> None:
        for item in items:
            if item.answer_type is AnswerType.ANTIDERIVATIVE:
                assert str(item.answer).rstrip().endswith("+ C"), item.item_id

    def test_loi_giai_mau_khong_co_buoc_bi_bao_sai(self, items: list[Item]) -> None:
        verifier = CalculusVerifier()
        failures: list[str] = []
        for item in items:
            if not item.reference_solution_steps:
                continue
            for check in verifier.check_steps(item, [s.expr for s in item.reference_solution_steps]):
                if check.ok is False:
                    failures.append(f"{item.item_id} bước {check.step}: {check.reason[:60]}")
        assert failures == [], "\n".join(failures[:10])


class TestConsistencyWithSkillTree:
    def test_ky_nang_gan_cho_bai_deu_ton_tai(self, items: list[Item]) -> None:
        """Template không được gắn mã kỹ năng lạ, nếu không mô hình năng lực sẽ hỏng."""
        bank = ItemBank.load("MAE101")
        unknown: set[str] = set()
        for item in items:
            unknown |= {s for s in item.skills if s not in bank.skills}
        assert unknown == set(), f"Mã kỹ năng không có trong skills.json: {unknown}"

    def test_do_kho_nam_trong_khoang_hop_le(self, items: list[Item]) -> None:
        assert all(0.0 <= item.difficulty <= 1.0 for item in items)

    def test_phan_bo_do_kho_du_rong(self, items: list[Item]) -> None:
        """Ngân hàng chỉ toàn bài dễ hoặc toàn bài khó thì bộ chọn bài vô dụng."""
        buckets = Counter(
            "dễ" if i.difficulty < 0.4 else "trung bình" if i.difficulty < 0.65 else "khó"
            for i in items
        )
        assert len(buckets) == 3, f"Phân bố độ khó quá hẹp: {dict(buckets)}"
