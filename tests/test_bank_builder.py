"""Test ba bộ sinh đề mới (MAD101, MAS291, MAI391).

Test quan trọng nhất là ``test_moi_template_sinh_duoc_bai``: mỗi template phải
thực sự đẻ ra được bài, và mọi bài đẻ ra phải tự chấm đúng. Một template hỏng
(gieo tham số vô lý, tính sai đáp án) thì không sinh nổi bài nào — nhưng nếu chỉ
đếm tổng số bài thì lỗi đó bị che mất, vì các template khác sinh bù vào.

Sinh ít bài thôi: bài MAS291 nào cũng bị verifier đối chứng Monte Carlo nên
chậm; số lượng thật do ``scripts/build_bank.py`` lo.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.itembank import ITEMS_DIR, load_items  # noqa: E402
from src.core.schema import Submission  # noqa: E402
from src.data_gen import discrete_items, mml_items, probstat_items  # noqa: E402
from src.verify.registry import verifier_for  # noqa: E402

MODULES = {"MAD101": discrete_items, "MAI391": mml_items, "MAS291": probstat_items}


@pytest.fixture(scope="module")
def generated() -> dict:
    """Mỗi môn sinh vài chục bài — đủ để mọi template được gọi ít nhất một lần."""
    return {code: module.generate(len(module.template_ids()) * 2, validate=True)
            for code, module in MODULES.items()}


@pytest.mark.parametrize("subject", list(MODULES))
def test_moi_template_sinh_duoc_bai(subject: str, generated) -> None:
    module = MODULES[subject]
    produced = {item.meta.get("template") for item in generated[subject]}
    missing = [name for name in module.template_ids() if name not in produced]
    assert missing == [], f"{subject}: template không sinh được bài nào: {missing}"


@pytest.mark.parametrize("subject", list(MODULES))
def test_bai_sinh_ra_tu_cham_dung(subject: str, generated) -> None:
    """Hàng rào của khung sinh đề: chỉ nhận bài mà verifier xác nhận."""
    verifier = verifier_for(subject)
    for item in generated[subject]:
        result = verifier.verify(item, Submission(item_id=item.item_id, final_answer=item.answer_text))
        assert result.final_answer_correct is True, f"{item.item_id}: {item.statement_vi} → {item.answer_text}"


@pytest.mark.parametrize("subject", list(MODULES))
def test_khong_trung_ma_de_va_khong_trung_tham_so(subject: str, generated) -> None:
    items = generated[subject]
    assert len({item.item_id for item in items}) == len(items)
    fingerprints = [str(sorted((k, str(v)) for k, v in item.meta.items() if k != "template"))
                    for item in items]
    assert len(set(fingerprints)) == len(fingerprints), "có hai đề trùng hệt tham số"


@pytest.mark.parametrize("subject", list(MODULES))
def test_de_co_du_phat_bieu_ky_nang_va_dap_an(subject: str, generated) -> None:
    for item in generated[subject]:
        assert item.statement_vi.strip() and item.skills and item.answer_text.strip(), item.item_id
        assert item.source == "generated"


@pytest.mark.parametrize("subject", list(MODULES))
def test_sinh_lai_cung_seed_ra_ket_qua_y_het(subject: str) -> None:
    """Ngân hàng đề trong git phải tái lập được — nếu không thì số liệu báo cáo cũng không."""
    module = MODULES[subject]
    first = module.generate(6, seed=123, validate=False)
    second = module.generate(6, seed=123, validate=False)
    assert [i.statement_vi for i in first] == [i.statement_vi for i in second]
    assert [i.answer_text for i in first] == [i.answer_text for i in second]


@pytest.mark.parametrize("subject", list(MODULES))
def test_ngan_hang_da_commit_van_cham_dung(subject: str) -> None:
    """Toàn bộ file đã sinh sẵn trong data/items phải còn chấm đúng.

    Đây là lưới an toàn cho việc SỬA VERIFIER: đổi bộ chấm mà làm sai một dạng
    bài cũ thì test này đỏ ngay, không phải chờ tới lúc chạy thí nghiệm.
    """
    path = ITEMS_DIR / f"{subject.lower()}_generated.jsonl"
    if not path.exists():
        pytest.skip(f"chưa sinh {path.name}")
    verifier = verifier_for(subject)
    items = load_items(path)
    assert len(items) >= 100
    wrong = [
        item.item_id for item in items[::7]          # lấy mẫu thưa cho test chạy nhanh
        if verifier.verify(item, Submission(item_id=item.item_id,
                                            final_answer=item.answer_text)).final_answer_correct is not True
    ]
    assert wrong == [], f"{subject}: {len(wrong)} bài trong ngân hàng không còn chấm đúng: {wrong[:5]}"
