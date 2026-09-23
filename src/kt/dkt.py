"""Deep Knowledge Tracing — mạng hồi tiếp dự đoán lần làm bài kế tiếp.

BKT theo dõi mỗi kỹ năng bằng một con số độc lập, nên không thấy được hai điều
mà người dạy nào cũng biết: kỹ năng này giúp cho kỹ năng kia, và người học có
thể quên. DKT (Piech et al., 2015) thay bằng một trạng thái ẩn chung cho cả
chuỗi: mỗi lượt làm bài cập nhật trạng thái, rồi từ trạng thái đó dự đoán xác
suất làm đúng cho MỌI kỹ năng ở bước sau.

Cách mã hoá (đúng như bài báo gốc): mỗi lượt ``(kỹ năng s, đúng/sai a)`` thành
một vector one-hot dài 2S — vị trí ``s`` nếu sai, ``S + s`` nếu đúng. Nhờ vậy
mạng phân biệt được "làm bài kỹ năng 3 và sai" với "làm bài kỹ năng 3 và đúng",
thứ mà chỉ mã hoá kỹ năng không thôi sẽ đánh mất.

Huấn luyện: ở mỗi bước, loss chỉ tính trên ĐÚNG kỹ năng của lượt kế tiếp (các
kỹ năng khác không có nhãn), nên phải che (mask) phần còn lại — chỗ này làm sai
là AUC đẹp giả mà không ai phát hiện.

Chạy trên CPU cũng được: dữ liệu mô phỏng chỉ cỡ vài chục nghìn lượt và mạng
chỉ có một lớp GRU 64 chiều.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

import torch
from torch import nn

Sequence = list[tuple[str, int]]


@dataclass
class DKTConfig:
    hidden_size: int = 64
    layers: int = 1
    dropout: float = 0.2
    learning_rate: float = 0.01
    epochs: int = 30
    batch_size: int = 32
    max_length: int = 200
    seed: int = 20260923
    patience: int = 5          # dừng sớm khi AUC trên tập validation không tăng nữa


class SkillIndex:
    """Ánh xạ mã kỹ năng ↔ chỉ số, cố định thứ tự để nạp lại mô hình không lệch."""

    def __init__(self, skill_ids: list[str]) -> None:
        self.skills = sorted(set(skill_ids))
        self.index = {skill: position for position, skill in enumerate(self.skills)}

    def __len__(self) -> int:
        return len(self.skills)

    @classmethod
    def from_sequences(cls, sequences: list[Sequence]) -> SkillIndex:
        return cls([skill for sequence in sequences for skill, _ in sequence])


def encode(sequences: list[Sequence], index: SkillIndex, max_length: int = 200):
    """Đóng gói thành tensor có đệm.

    Trả về ``(đầu vào, kỹ năng đích, nhãn, mặt nạ)``: đầu vào là lượt thứ t, còn
    đích và nhãn là lượt t+1 — mô hình luôn dự đoán TƯƠNG LAI, không bao giờ
    được nhìn thấy kết quả mình đang phải đoán.
    """
    usable = [s[:max_length] for s in sequences if len(s) >= 2]
    if not usable:
        raise ValueError("Cần chuỗi dài ít nhất 2 lượt mới huấn luyện được")

    batch = len(usable)
    steps = max(len(s) for s in usable) - 1
    skills = len(index)

    inputs = torch.zeros(batch, steps, 2 * skills)
    targets = torch.zeros(batch, steps, dtype=torch.long)
    labels = torch.zeros(batch, steps)
    mask = torch.zeros(batch, steps)

    for row, sequence in enumerate(usable):
        for step in range(len(sequence) - 1):
            skill, correct = sequence[step]
            next_skill, next_correct = sequence[step + 1]
            inputs[row, step, index.index[skill] + (skills if correct else 0)] = 1.0
            targets[row, step] = index.index[next_skill]
            labels[row, step] = float(next_correct)
            mask[row, step] = 1.0

    return inputs, targets, labels, mask


class DKT(nn.Module):
    """Một lớp GRU, đầu ra là xác suất làm đúng cho từng kỹ năng."""

    def __init__(self, skills: int, config: DKTConfig | None = None) -> None:
        super().__init__()
        config = config or DKTConfig()
        self.skills = skills
        self.rnn = nn.GRU(
            input_size=2 * skills,
            hidden_size=config.hidden_size,
            num_layers=config.layers,
            batch_first=True,
            dropout=config.dropout if config.layers > 1 else 0.0,
        )
        self.dropout = nn.Dropout(config.dropout)
        self.output = nn.Linear(config.hidden_size, skills)

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        hidden, _ = self.rnn(inputs)
        return self.output(self.dropout(hidden))      # logit, chưa qua sigmoid


def gather_predictions(logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
    """Lấy đúng cột của kỹ năng sẽ làm ở bước kế — phần còn lại không có nhãn."""
    return logits.gather(2, targets.unsqueeze(2)).squeeze(2)


@dataclass
class TrainingHistory:
    train_loss: list[float] = field(default_factory=list)
    val_auc: list[float] = field(default_factory=list)
    best_epoch: int = 0
    best_auc: float = 0.0


def train_dkt(
    train: list[Sequence],
    validation: list[Sequence],
    index: SkillIndex,
    config: DKTConfig | None = None,
) -> tuple[DKT, TrainingHistory]:
    """Huấn luyện, chọn mô hình theo AUC trên tập validation (không theo loss)."""
    config = config or DKTConfig()
    torch.manual_seed(config.seed)

    model = DKT(len(index), config)
    optimiser = torch.optim.Adam(model.parameters(), lr=config.learning_rate)
    criterion = nn.BCEWithLogitsLoss(reduction="none")

    inputs, targets, labels, mask = encode(train, index, config.max_length)
    history = TrainingHistory()
    best_state = {k: v.clone() for k, v in model.state_dict().items()}
    since_improved = 0

    for epoch in range(config.epochs):
        model.train()
        order = torch.randperm(inputs.size(0))
        total = 0.0

        for start in range(0, len(order), config.batch_size):
            rows = order[start:start + config.batch_size]
            optimiser.zero_grad()
            logits = gather_predictions(model(inputs[rows]), targets[rows])
            losses = criterion(logits, labels[rows]) * mask[rows]
            loss = losses.sum() / mask[rows].sum().clamp(min=1.0)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 5.0)   # chuỗi dài dễ nổ gradient
            optimiser.step()
            total += loss.detach().item() * len(rows)

        history.train_loss.append(total / inputs.size(0))
        auc = evaluate(model, validation, index, config)["auc"]
        history.val_auc.append(auc)

        if auc > history.best_auc:
            history.best_auc, history.best_epoch = auc, epoch
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
            since_improved = 0
        else:
            since_improved += 1
            if since_improved >= config.patience:
                break

    model.load_state_dict(best_state)
    return model, history


@torch.no_grad()
def predict(model: DKT, sequences: list[Sequence], index: SkillIndex,
            config: DKTConfig | None = None) -> tuple[list[float], list[int]]:
    """Xác suất dự đoán và nhãn thật, đã bỏ phần đệm."""
    config = config or DKTConfig()
    model.eval()
    inputs, targets, labels, mask = encode(sequences, index, config.max_length)
    probabilities = torch.sigmoid(gather_predictions(model(inputs), targets))
    keep = mask.bool()
    return probabilities[keep].tolist(), labels[keep].long().tolist()


def evaluate(model: DKT, sequences: list[Sequence], index: SkillIndex,
             config: DKTConfig | None = None) -> dict[str, float]:
    scores, truth = predict(model, sequences, index, config)
    return {"auc": auc_score(scores, truth), "accuracy": accuracy(scores, truth),
            "log_loss": log_loss(scores, truth), "n": len(truth)}


# --------------------------------------------------------------------------
# Chỉ số
# --------------------------------------------------------------------------

def auc_score(scores: list[float], truth: list[int]) -> float:
    """AUC tính bằng thống kê Mann–Whitney, có xử lý điểm bằng nhau.

    Tự cài thay vì gọi sklearn để chỉ số này dùng được cả trong test nhanh và
    trong notebook không có sklearn; công thức hạng cũng dễ kiểm bằng tay hơn.
    """
    positives = sum(truth)
    negatives = len(truth) - positives
    if positives == 0 or negatives == 0:
        return 0.5                                   # chỉ có một lớp thì AUC vô nghĩa

    order = sorted(range(len(scores)), key=lambda i: scores[i])
    ranks = [0.0] * len(scores)
    position = 0
    while position < len(order):
        end = position
        while end + 1 < len(order) and scores[order[end + 1]] == scores[order[position]]:
            end += 1
        average_rank = (position + end) / 2 + 1       # hạng trung bình cho nhóm bằng điểm
        for i in range(position, end + 1):
            ranks[order[i]] = average_rank
        position = end + 1

    rank_sum = sum(rank for rank, label in zip(ranks, truth) if label == 1)
    return (rank_sum - positives * (positives + 1) / 2) / (positives * negatives)


def accuracy(scores: list[float], truth: list[int], threshold: float = 0.5) -> float:
    if not truth:
        return 0.0
    return sum(int(s >= threshold) == t for s, t in zip(scores, truth)) / len(truth)


def log_loss(scores: list[float], truth: list[int]) -> float:
    if not truth:
        return 0.0
    total = 0.0
    for score, label in zip(scores, truth):
        p = min(max(score, 1e-7), 1 - 1e-7)
        total -= math.log(p) if label else math.log(1 - p)
    return total / len(truth)


# --------------------------------------------------------------------------
# Chia dữ liệu
# --------------------------------------------------------------------------

def split_sequences(sequences: list[Sequence], ratios=(0.7, 0.15, 0.15), seed: int = 20260923):
    """Chia THEO NGƯỜI HỌC, không theo lượt.

    Chia theo lượt sẽ để các lượt của cùng một người nằm cả ở train lẫn test —
    mô hình học thuộc người đó và AUC đẹp lên một cách giả tạo.
    """
    shuffled = list(sequences)
    random.Random(seed).shuffle(shuffled)
    total = len(shuffled)
    first = int(total * ratios[0])
    second = first + int(total * ratios[1])
    return shuffled[:first], shuffled[first:second], shuffled[second:]
