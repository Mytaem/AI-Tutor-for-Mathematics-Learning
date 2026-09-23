"""Hai baseline cho EXP-5: đoán theo tần suất, và BKT.

Không có baseline thì con số AUC của DKT chẳng nói lên điều gì. Hai mốc ở đây
trả lời hai câu hỏi khác nhau:

- ``majority``: chỉ đoán theo tỉ lệ đúng chung, không nhìn người học lẫn kỹ năng.
  AUC của nó luôn bằng 0.5 — nếu mô hình nào không vượt được mốc này thì nó
  không học được gì cả.
- ``BKT``: mô hình theo dõi năng lực kinh điển, có tham số, giải thích được.
  Đây mới là đối thủ thật của DKT.

Tham số BKT được KHỚP TỪ DỮ LIỆU bằng tìm kiếm trên lưới (cực đại hoá log
likelihood trên tập train), không dùng giá trị mặc định — nếu không thì so sánh
thành ra "DKT đã huấn luyện" đấu với "BKT đoán bừa tham số".
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from src.kt.bkt import BKTParams, probability_correct, update

Sequence = list[tuple[str, int]]

#: Lưới tham số cho việc khớp BKT. Thô nhưng đủ: mặt likelihood của BKT rất phẳng,
#: chia mịn hơn gần như không đổi kết quả mà tốn thời gian gấp bội.
_GRID = {
    "p_init": (0.05, 0.15, 0.25, 0.4, 0.6),
    "p_learn": (0.05, 0.1, 0.2, 0.3, 0.45),
    "p_slip": (0.05, 0.1, 0.2, 0.3),
    "p_guess": (0.05, 0.15, 0.25, 0.35),
}


def majority_predict(train: list[Sequence], test: list[Sequence]) -> tuple[list[float], list[int]]:
    """Đoán mọi lượt bằng đúng tỉ lệ làm đúng của tập train."""
    observations = [correct for sequence in train for _, correct in sequence]
    rate = sum(observations) / len(observations) if observations else 0.5
    truth = [correct for sequence in test for _, correct in sequence[1:]]
    return [rate] * len(truth), truth


def bkt_predict(sequences: list[Sequence], params: BKTParams) -> tuple[list[float], list[int]]:
    """Chạy BKT dọc từng chuỗi, dự đoán lượt kế rồi mới cập nhật.

    Thứ tự này là bắt buộc: cập nhật trước rồi mới dự đoán tức là đã nhìn thấy
    đáp án cần đoán.
    """
    scores: list[float] = []
    truth: list[int] = []
    for sequence in sequences:
        mastery: dict[str, float] = {}
        for position, (skill, correct) in enumerate(sequence):
            current = mastery.get(skill, params.p_init)
            if position > 0:                      # lượt đầu không có gì để dự đoán
                scores.append(probability_correct(current, params))
                truth.append(int(correct))
            mastery[skill] = update(current, bool(correct), params)
    return scores, truth


def log_likelihood(sequences: list[Sequence], params: BKTParams) -> float:
    scores, truth = bkt_predict(sequences, params)
    total = 0.0
    for score, label in zip(scores, truth):
        p = min(max(score, 1e-6), 1 - 1e-6)
        total += math.log(p) if label else math.log(1 - p)
    return total


@dataclass
class BKTFit:
    params: BKTParams
    log_likelihood: float
    candidates: int


def fit_bkt(train: list[Sequence], grid: dict | None = None) -> BKTFit:
    """Khớp bốn tham số BKT bằng tìm kiếm trên lưới."""
    grid = grid or _GRID
    best: BKTParams | None = None
    best_score = -math.inf
    tried = 0

    for p_init in grid["p_init"]:
        for p_learn in grid["p_learn"]:
            for p_slip in grid["p_slip"]:
                for p_guess in grid["p_guess"]:
                    if p_slip + p_guess >= 1.0:
                        continue                  # BKTParams sẽ từ chối bộ này
                    candidate = BKTParams(p_init, p_learn, p_slip, p_guess)
                    tried += 1
                    score = log_likelihood(train, candidate)
                    if score > best_score:
                        best, best_score = candidate, score

    assert best is not None
    return BKTFit(best, best_score, tried)
