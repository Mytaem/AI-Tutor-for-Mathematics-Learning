"""Test bộ sinh lỗi — đồng thời là bộ test phủ có hệ thống cho verifier.

Mỗi bài làm sai sinh ra ở đây đều có nhãn chính xác, nên ta kiểm tra được hai
điều mà không bộ test viết tay nào làm nổi:

- **Tỉ lệ phát hiện**: verifier có nhận ra bài làm sai không?
- **Tỉ lệ gán nhãn đúng**: verifier có gọi tên đúng loại lỗi không?

Hai con số này chính là số liệu cho EXP-2 và EXP-3 trong PLAN.md.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import pytest
import sympy as sp

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.itembank import ERRORS_DIR, ItemBank, load_error_codes  # noqa: E402
from src.core.schema import AnswerType, Submission  # noqa: E402
from src.data_gen.error_injector import InjectedError, build_dataset  # noqa: E402
from src.verify.registry import verifier_for  # noqa: E402
from src.verify.equivalence import expr_equal, parse_math  # noqa: E402

# Mã lỗi mà tầng ký hiệu tự gán được. Các mã còn lại verifier chỉ phát hiện
# "sai" chứ chưa gọi tên được — đó là phần dành cho bộ phân loại neural.
SYMBOLIC_LABELS = {
    "MAE.INT.NOCONST": "MAE.INT.NOCONST",
    "MAE.SIGN": "MAE.SIGN",
    "MAE.INT.CONSTFACTOR": "MAE.INT.CONSTFACTOR",
    "MAE.INT.SUBST.NOFACTOR": "MAE.INT.CONSTFACTOR",
    "MAE.INT.POWER.NODIV": "MAE.INT.CONSTFACTOR",
    "MAE.INT.DEF.NOEVAL": "MAE.INT.DEF.NOEVAL",
    "MAE.INT.DEF.SWAPBOUNDS": "MAE.INT.DEF.SWAPBOUNDS",
}


@pytest.fixture(scope="module")
def bank() -> ItemBank:
    return ItemBank.load("MAE101")


@pytest.fixture(scope="module")
def dataset(bank: ItemBank) -> list[InjectedError]:
    return build_dataset(bank, ERRORS_DIR / "mae101.json")


class TestDatasetShape:
    def test_sinh_du_so_luong(self, dataset: list[InjectedError]) -> None:
        assert len(dataset) >= 60, f"Chỉ sinh được {len(dataset)} mẫu"

    def test_phu_du_loai_loi(self, dataset: list[InjectedError]) -> None:
        codes = {record.error_code for record in dataset}
        assert len(codes) >= 8, f"Mới phủ được {len(codes)} mã lỗi: {sorted(codes)}"

    def test_moi_ma_loi_deu_co_trong_taxonomy(self, dataset: list[InjectedError]) -> None:
        """Không được sinh ra mã lỗi lạ, không có trong bảng phân loại."""
        taxonomy = load_error_codes(ERRORS_DIR / "mae101.json")
        unknown = {r.error_code for r in dataset} - set(taxonomy)
        assert unknown == set(), f"Mã lỗi không có trong taxonomy: {unknown}"

    def test_moi_ban_ghi_deu_co_nhan_day_du(self, dataset: list[InjectedError]) -> None:
        for record in dataset:
            assert record.error_code and record.tier and record.item_id
            assert record.wrong_final_answer or record.wrong_steps


class TestInjectedErrorsAreActuallyWrong:
    def test_dap_an_sai_that_su_khac_dap_an_dung(self, dataset: list[InjectedError]) -> None:
        """Lỗi sinh ra phải thực sự sai. Nếu trùng đáp án đúng thì nhãn là rác.

        Ngoại lệ: quên '+ C' vẫn là một nguyên hàm đúng, sai ở chỗ thiếu tính
        tổng quát chứ không sai về giá trị.
        """
        false_labels: list[str] = []
        for record in dataset:
            if record.error_code in {"MAE.INT.NOCONST", "MAE.ALG.STEP"}:
                continue
            if record.wrong_final_answer is None:
                continue
            if expr_equal(record.wrong_final_answer, record.correct_answer).equal:
                false_labels.append(f"{record.item_id}/{record.error_code}")

        assert false_labels == [], f"Các mẫu 'sai' nhưng thực ra đúng: {false_labels}"


class TestEigenfunctionTrap:
    """Hồi quy cho một lớp lỗi nhãn đã từng lọt lưới.

    ∫e^(-x)dx = -e^(-x) + C. Nhưng đạo hàm của e^(-x) cũng đúng bằng -e^(-x).
    Hàm e^(λx) là hàm riêng của cả đạo hàm lẫn tích phân, và tại λ = -1 hai phép
    trùng nhau. Bộ sinh từng gán nhãn "lấy đạo hàm thay vì tích phân" cho chính
    đáp án đúng — nhãn sai kiểu này còn hại hơn thiếu dữ liệu.
    """

    def test_khong_sinh_nhan_sai_cho_ham_rieng(self) -> None:
        from src.core.schema import Item, Subject
        from src.data_gen.error_injector import is_genuinely_wrong

        item = Item(
            item_id="TRAP-001",
            subject=Subject.MAE101,
            statement_vi="Tính nguyên hàm của e^(-x)",
            answer_type=AnswerType.ANTIDERIVATIVE,
            answer="-exp(-x) + C",
            integrand="exp(-x)",
            variable="x",
        )
        assert not is_genuinely_wrong(item, "-exp(-x) + C"), "Đây là đáp án ĐÚNG, không được gán nhãn lỗi"
        assert is_genuinely_wrong(item, "exp(-x) + C"), "Đáp án này sai dấu, phải nhận ra"

    def test_ham_mu_lambda_bang_1_cung_duoc_chan(self) -> None:
        from src.core.schema import Item, Subject
        from src.data_gen.error_injector import is_genuinely_wrong

        item = Item(
            item_id="TRAP-002",
            subject=Subject.MAE101,
            statement_vi="Tính nguyên hàm của e^x",
            answer_type=AnswerType.ANTIDERIVATIVE,
            answer="exp(x) + C",
            integrand="exp(x)",
            variable="x",
        )
        assert not is_genuinely_wrong(item, "exp(x) + C")


class TestVerifierCatchesInjectedErrors:
    def test_phat_hien_duoc_moi_loi(self, bank: ItemBank, dataset: list[InjectedError]) -> None:
        """Mọi lỗi sinh ra phải bị verifier phát hiện. Đây là test chặt nhất cho tầng kiểm chứng."""
        verifier = verifier_for("MAE101")
        missed: list[str] = []

        for record in dataset:
            item = bank.get(record.item_id)
            submission = Submission(
                item_id=item.item_id,
                final_answer=record.wrong_final_answer,
                steps=record.wrong_steps,
            )
            result = verifier.verify(item, submission)

            if record.error_code == "MAE.INT.NOCONST":
                # Vẫn đúng về giá trị, chỉ thiếu hằng số — phải gắn mã lỗi.
                caught = "MAE.INT.NOCONST" in result.candidate_error_codes
            elif record.error_code == "MAE.ALG.STEP":
                caught = result.first_wrong_step == record.wrong_step_index
            else:
                caught = result.final_answer_correct is False

            if not caught:
                missed.append(f"{record.item_id}/{record.error_code}")

        assert missed == [], f"Verifier bỏ sót {len(missed)} lỗi: {missed}"

    def test_gan_nhan_dung_cho_cac_loi_tang_ky_hieu(
        self, bank: ItemBank, dataset: list[InjectedError]
    ) -> None:
        """Với các lỗi tầng ký hiệu phân biệt được, nhãn gán ra phải đúng."""
        verifier = verifier_for("MAE101")
        mislabeled: list[str] = []

        for record in dataset:
            expected = SYMBOLIC_LABELS.get(record.error_code)
            if expected is None:
                continue

            item = bank.get(record.item_id)
            result = verifier.verify(
                item, Submission(item_id=item.item_id, final_answer=record.wrong_final_answer)
            )
            if expected not in result.candidate_error_codes:
                mislabeled.append(
                    f"{record.item_id}/{record.error_code}: mong {expected}, nhận {result.candidate_error_codes}"
                )

        assert mislabeled == [], "Gán nhãn sai:\n" + "\n".join(mislabeled)

    def test_nhan_he_so_chi_duoc_gan_khi_dung_su_that(
        self, bank: ItemBank, dataset: list[InjectedError]
    ) -> None:
        """Độ chính xác của nhãn: hễ verifier nói 'lệch một hệ số' thì phải đúng là vậy.

        Kiểm chứng độc lập bằng ``simplify`` — nếu tỉ số đạo hàm trên biểu thức
        gốc còn chứa biến thì nhãn đó là bịa.
        """
        verifier = verifier_for("MAE101")
        fabricated: list[str] = []

        for record in dataset:
            item = bank.get(record.item_id)
            if item.answer_type is not AnswerType.ANTIDERIVATIVE or not record.wrong_final_answer:
                continue

            result = verifier.verify(
                item, Submission(item_id=item.item_id, final_answer=record.wrong_final_answer)
            )
            if "MAE.INT.CONSTFACTOR" not in result.candidate_error_codes:
                continue

            derivative = sp.diff(parse_math(record.wrong_final_answer), sp.Symbol(item.variable))
            ratio = sp.simplify(derivative / parse_math(item.integrand or "1"))
            if ratio.free_symbols:
                fabricated.append(f"{record.item_id}/{record.error_code}: tỉ số = {ratio}")

        assert fabricated == [], "Gán nhãn lệch-hệ-số cho trường hợp không phải vậy:\n" + "\n".join(fabricated)

    def test_gioi_han_da_biet_ham_mu_lam_nhoe_ranh_gioi_loai_loi(self, bank: ItemBank) -> None:
        """Ghi nhận một giới hạn THẬT của tầng ký hiệu, không phải lỗi cài đặt.

        Với ∫e^(2x)dx, sinh viên lấy đạo hàm thay vì tích phân sẽ ra 2e^(2x), mà
        đạo hàm của nó lại đúng bằng 4 lần biểu thức gốc. Hàm mũ là hàm riêng của
        phép đạo hàm, nên lỗi KHÁI NIỆM này nhìn từ ngoài giống hệt lỗi HỆ SỐ.

        Tầng ký hiệu không thể tự gỡ được chuyện này — đây chính là lý do cần bộ
        phân loại neural đọc cả lời giải để suy ra nguyên nhân. Ghi vào phần
        Limitations của báo cáo.
        """
        verifier = verifier_for("MAE101")
        item = bank.get("MAE101-INT-006")  # ∫ e^(2x) dx
        result = verifier.verify(
            item, Submission(item_id=item.item_id, final_answer="2*exp(2*x) + C")
        )
        assert result.final_answer_correct is False
        assert "MAE.INT.CONSTFACTOR" in result.candidate_error_codes


def _print_console(line: str) -> None:
    """In ra console thật, chịu được cả terminal không đọc nổi tiếng Việt.

    Console Windows mặc định cp1252; `print` thẳng dấu tiếng Việt ra đó ném
    UnicodeEncodeError và **cả bộ test đổ chỉ vì cái terminal đang chạy nó**.
    Thà mất dấu còn hơn mất bộ test.
    """
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    sys.stdout.write(line.encode(encoding, "replace").decode(encoding) + "\n")


def test_bao_cao_do_phu(dataset: list[InjectedError], capsys: pytest.CaptureFixture[str]) -> None:
    """In thống kê để đưa vào báo cáo — không phải assertion, chạy với -s để xem."""
    counter = Counter(record.error_code for record in dataset)
    with capsys.disabled():
        _print_console(f"\n  Tổng số mẫu lỗi sinh ra: {len(dataset)}")
        for code, count in counter.most_common():
            _print_console(f"    {code:<30} {count:>3}")
