"""Test DKT, SAKT và các baseline.

Lỗi nguy hiểm nhất ở loại mô hình này là **rò rỉ tương lai**: nếu đầu vào ở bước
t vô tình chứa kết quả của bước t+1 thì AUC đẹp rực rỡ mà hoàn toàn vô giá trị,
và không có gì báo động cả. Vì vậy phần lớn test ở đây kiểm đúng một điều: mô
hình chỉ được nhìn quá khứ.

Mọi mô hình chạy với cấu hình tí hon (vài epoch, mạng nhỏ) — test phải xong
trong vài giây, số liệu thật thì để ``scripts/exp5_kt.py`` lo.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

import pytest
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.kt.baselines import bkt_predict, fit_bkt, majority_predict  # noqa: E402
from src.kt.bkt import BKTParams  # noqa: E402
from src.kt.dkt import (  # noqa: E402
    DKTConfig,
    SkillIndex,
    accuracy,
    auc_score,
    encode,
    evaluate,
    log_loss,
    split_sequences,
    train_dkt,
)
from src.kt.sakt import SAKT, SAKTConfig, encode_sakt, evaluate_sakt, train_sakt  # noqa: E402

TINY_DKT = DKTConfig(hidden_size=16, epochs=6, batch_size=8, patience=6)
TINY_SAKT = SAKTConfig(dimension=16, heads=2, epochs=6, batch_size=8, patience=6, max_length=40)


def learnable_data(students: int = 60, steps: int = 20, seed: int = 3):
    """Dữ liệu có quy luật rõ: người 'giỏi' đúng 90%, người 'kém' đúng 20%.

    Mô hình nào không vượt được AUC 0.5 trên tập này thì chắc chắn có lỗi cài đặt.
    """
    rng = random.Random(seed)
    skills = ["S1", "S2", "S3"]
    sequences = []
    for student in range(students):
        rate = 0.9 if student % 2 == 0 else 0.2
        sequences.append([(rng.choice(skills), int(rng.random() < rate)) for _ in range(steps)])
    return sequences


@pytest.fixture(scope="module")
def data():
    sequences = learnable_data()
    index = SkillIndex.from_sequences(sequences)
    train, validation, test = split_sequences(sequences, seed=1)
    return sequences, index, train, validation, test


class TestMetrics:
    def test_auc_phan_loai_hoan_hao_bang_1(self) -> None:
        assert auc_score([0.1, 0.2, 0.8, 0.9], [0, 0, 1, 1]) == 1.0

    def test_auc_phan_loai_nguoc_bang_0(self) -> None:
        assert auc_score([0.9, 0.8, 0.2, 0.1], [0, 0, 1, 1]) == 0.0

    def test_auc_doan_bua_bang_nua(self) -> None:
        """Mọi điểm bằng nhau thì AUC phải là 0.5 — chỗ này hay sai khi xử lý điểm trùng."""
        assert auc_score([0.5] * 6, [0, 1, 0, 1, 1, 0]) == 0.5

    def test_auc_chi_mot_lop_tra_ve_nua(self) -> None:
        assert auc_score([0.2, 0.9], [1, 1]) == 0.5

    def test_accuracy_va_log_loss(self) -> None:
        assert accuracy([0.9, 0.1], [1, 0]) == 1.0
        assert log_loss([0.9, 0.9], [1, 1]) < log_loss([0.6, 0.6], [1, 1])


class TestEncoding:
    def test_dau_vao_la_luot_hien_tai_nhan_la_luot_ke_tiep(self) -> None:
        """Bất biến chống rò rỉ: nhãn ở bước t phải là kết quả của bước t+1."""
        index = SkillIndex(["A", "B"])
        sequence = [("A", 1), ("B", 0), ("A", 1)]
        inputs, targets, labels, mask = encode([sequence], index)

        assert inputs[0, 0].tolist() == [0, 0, 1, 0]      # A đúng → vị trí S + index(A)
        assert targets[0, 0].item() == index.index["B"]
        assert labels[0, 0].item() == 0.0                  # kết quả của lượt B
        assert mask[0].tolist() == [1.0, 1.0]

    def test_ket_qua_luot_ke_tiep_khong_co_trong_dau_vao(self) -> None:
        """Đổi kết quả lượt CUỐI không được làm đổi bất kỳ đầu vào nào."""
        index = SkillIndex(["A", "B"])
        first = encode([[("A", 1), ("B", 0)]], index)[0]
        second = encode([[("A", 1), ("B", 1)]], index)[0]
        assert torch.equal(first, second)

    def test_chuoi_ngan_bi_loai(self) -> None:
        index = SkillIndex(["A"])
        with pytest.raises(ValueError):
            encode([[("A", 1)]], index)

    def test_sakt_ma_hoa_khop_voi_dkt(self) -> None:
        index = SkillIndex(["A", "B"])
        sequence = [("A", 1), ("B", 0), ("A", 0)]
        _, dkt_targets, dkt_labels, _ = encode([sequence], index)
        _, sakt_targets, sakt_labels, _ = encode_sakt([sequence], index)
        assert torch.equal(dkt_targets, sakt_targets) and torch.equal(dkt_labels, sakt_labels)


class TestCausality:
    def test_dkt_khong_nhin_thay_tuong_lai(self, data) -> None:
        """Đổi một lượt ở CUỐI chuỗi không được làm đổi dự đoán ở ĐẦU chuỗi."""
        _, index, train, validation, _ = data
        model, _ = train_dkt(train[:20], validation[:5], index, TINY_DKT)
        model.eval()

        original = train[0][:12]
        changed = original[:-1] + [(original[-1][0], 1 - original[-1][1])]
        with torch.no_grad():
            first = model(encode([original], index)[0])[0, :5]
            second = model(encode([changed], index)[0])[0, :5]
        assert torch.allclose(first, second, atol=1e-6)

    def test_sakt_co_mat_na_nhan_qua(self) -> None:
        """Không có mặt nạ thì chú ý nhìn được cả lượt sau — kiểm trực tiếp."""
        index = SkillIndex(["A", "B"])
        model = SAKT(len(index), TINY_SAKT).eval()
        base = [("A", 1), ("B", 1), ("A", 0), ("B", 1)]
        changed = base[:3] + [("B", 0)]
        with torch.no_grad():
            first = model(*encode_sakt([base], index)[:2])[0, 0]
            second = model(*encode_sakt([changed], index)[:2])[0, 0]
        assert torch.allclose(first, second, atol=1e-6)


class TestTraining:
    def test_dkt_hoc_duoc_quy_luat(self, data) -> None:
        _, index, train, validation, test = data
        model, history = train_dkt(train, validation, index, TINY_DKT)
        result = evaluate(model, test, index, TINY_DKT)
        assert result["auc"] > 0.6, f"DKT không học được gì: {result}"
        assert history.train_loss[-1] < history.train_loss[0]

    def test_sakt_hoc_duoc_quy_luat(self, data) -> None:
        _, index, train, validation, test = data
        model, _ = train_sakt(train, validation, index, TINY_SAKT)
        assert evaluate_sakt(model, test, index, TINY_SAKT)["auc"] > 0.6

    def test_cung_seed_ra_cung_ket_qua(self, data) -> None:
        _, index, train, validation, test = data
        results = [evaluate(train_dkt(train, validation, index, TINY_DKT)[0], test, index, TINY_DKT)["auc"]
                   for _ in range(2)]
        assert results[0] == pytest.approx(results[1])


class TestSplit:
    def test_chia_theo_nguoi_hoc_khong_lan_lot(self) -> None:
        """Cùng một người không được xuất hiện ở hai tập — nếu lẫn thì AUC ảo."""
        sequences = [[("A", i % 2)] * 5 for i in range(20)]
        train, validation, test = split_sequences(sequences, seed=2)
        assert len(train) + len(validation) + len(test) == 20
        pieces = [id(s) for s in train], [id(s) for s in validation], [id(s) for s in test]
        assert not (set(pieces[0]) & set(pieces[1])) and not (set(pieces[1]) & set(pieces[2]))

    def test_cung_seed_chia_giong_nhau(self) -> None:
        sequences = [[("A", 1), ("B", 0)] for _ in range(10)]
        assert split_sequences(sequences, seed=7)[0] == split_sequences(sequences, seed=7)[0]


class TestBaselines:
    def test_majority_luon_cho_auc_nua(self, data) -> None:
        _, _, train, _, test = data
        scores, truth = majority_predict(train, test)
        assert auc_score(scores, truth) == 0.5

    def test_bkt_du_doan_truoc_khi_cap_nhat(self) -> None:
        """Lượt đầu không có gì để dự đoán; n dự đoán phải bằng số lượt trừ một."""
        sequence = [("A", 1), ("A", 1), ("A", 0)]
        scores, truth = bkt_predict([sequence], BKTParams())
        assert len(scores) == len(truth) == 2

    def test_bkt_tang_ky_vong_sau_khi_lam_dung(self) -> None:
        scores, _ = bkt_predict([[("A", 1), ("A", 1), ("A", 1)]], BKTParams())
        assert scores[1] > scores[0]

    def test_khop_tham_so_tot_hon_mac_dinh(self, data) -> None:
        """Tham số khớp từ dữ liệu phải cho likelihood cao hơn tham số mặc định."""
        from src.kt.baselines import log_likelihood

        _, _, train, _, _ = data
        fit = fit_bkt(train)
        assert fit.log_likelihood >= log_likelihood(train, BKTParams())
        assert fit.candidates > 100
