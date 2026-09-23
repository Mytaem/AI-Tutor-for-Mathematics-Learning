"""SAKT — Self-Attentive Knowledge Tracing (Pandey & Karypis, 2019).

Khác DKT ở chỗ nào: DKT nhồi cả quá khứ vào một trạng thái ẩn, nên lượt làm bài
từ 30 bước trước ảnh hưởng tới dự đoán hôm nay qua một đường rất hẹp. SAKT bỏ
hồi tiếp, cho mỗi kỹ năng cần dự đoán **tự chọn** những lượt quá khứ liên quan
bằng cơ chế chú ý: truy vấn là kỹ năng sắp làm, khoá và giá trị là các lượt đã
làm. Nhờ vậy nó bắt được quan hệ xa mà không phải nhớ mọi thứ.

Hai chi tiết bắt buộc, sai là hỏng thí nghiệm:

- **Mặt nạ nhân quả**: lượt thứ t chỉ được nhìn các lượt ≤ t. Thiếu mặt nạ này
  thì mô hình nhìn thấy tương lai và AUC đẹp giả.
- **Mặt nạ phần đệm**: các ô đệm phải bị loại khỏi cả chú ý lẫn loss.

Cài bằng ``nn.MultiheadAttention`` thay vì tự viết, vì phần đáng để tự viết
(mã hoá tương tác, mặt nạ, chỉ số) mới là chỗ dễ sai.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import nn

from src.kt.dkt import Sequence, SkillIndex, TrainingHistory, accuracy, auc_score, log_loss


@dataclass
class SAKTConfig:
    dimension: int = 64
    heads: int = 4
    dropout: float = 0.2
    learning_rate: float = 0.005
    epochs: int = 30
    batch_size: int = 32
    max_length: int = 200
    seed: int = 20260923
    patience: int = 5


def encode_sakt(sequences: list[Sequence], index: SkillIndex, max_length: int = 200):
    """Mã hoá dạng chỉ số (không one-hot) — SAKT dùng lớp embedding.

    ``interactions[t] = kỹ năng + S·đúng`` là lượt ĐÃ làm; ``targets[t]`` là kỹ
    năng của lượt KẾ TIẾP, tức là câu hỏi mà mô hình phải trả lời.
    """
    usable = [s[:max_length] for s in sequences if len(s) >= 2]
    if not usable:
        raise ValueError("Cần chuỗi dài ít nhất 2 lượt mới huấn luyện được")

    batch = len(usable)
    steps = max(len(s) for s in usable) - 1
    skills = len(index)

    interactions = torch.zeros(batch, steps, dtype=torch.long)
    targets = torch.zeros(batch, steps, dtype=torch.long)
    labels = torch.zeros(batch, steps)
    mask = torch.zeros(batch, steps)

    for row, sequence in enumerate(usable):
        for step in range(len(sequence) - 1):
            skill, correct = sequence[step]
            next_skill, next_correct = sequence[step + 1]
            interactions[row, step] = index.index[skill] + (skills if correct else 0)
            targets[row, step] = index.index[next_skill]
            labels[row, step] = float(next_correct)
            mask[row, step] = 1.0

    return interactions, targets, labels, mask


class SAKT(nn.Module):
    def __init__(self, skills: int, config: SAKTConfig | None = None) -> None:
        super().__init__()
        config = config or SAKTConfig()
        self.skills = skills
        self.dimension = config.dimension

        self.interaction_embedding = nn.Embedding(2 * skills + 1, config.dimension)
        self.skill_embedding = nn.Embedding(skills, config.dimension)
        self.position_embedding = nn.Embedding(config.max_length, config.dimension)

        self.attention = nn.MultiheadAttention(config.dimension, config.heads,
                                               dropout=config.dropout, batch_first=True)
        self.norm1 = nn.LayerNorm(config.dimension)
        self.feed_forward = nn.Sequential(
            nn.Linear(config.dimension, config.dimension * 2),
            nn.ReLU(),
            nn.Dropout(config.dropout),
            nn.Linear(config.dimension * 2, config.dimension),
        )
        self.norm2 = nn.LayerNorm(config.dimension)
        self.dropout = nn.Dropout(config.dropout)
        self.output = nn.Linear(config.dimension, 1)

    def forward(self, interactions: torch.Tensor, targets: torch.Tensor,
                padding: torch.Tensor | None = None) -> torch.Tensor:
        steps = interactions.size(1)
        positions = torch.arange(steps, device=interactions.device)

        keys = self.interaction_embedding(interactions) + self.position_embedding(positions)
        queries = self.skill_embedding(targets)

        causal = torch.triu(torch.ones(steps, steps, dtype=torch.bool,
                                       device=interactions.device), diagonal=1)
        attended, _ = self.attention(queries, keys, keys, attn_mask=causal,
                                     key_padding_mask=padding, need_weights=False)
        hidden = self.norm1(queries + self.dropout(attended))
        hidden = self.norm2(hidden + self.dropout(self.feed_forward(hidden)))
        return self.output(hidden).squeeze(-1)


def train_sakt(
    train: list[Sequence],
    validation: list[Sequence],
    index: SkillIndex,
    config: SAKTConfig | None = None,
) -> tuple[SAKT, TrainingHistory]:
    config = config or SAKTConfig()
    torch.manual_seed(config.seed)

    model = SAKT(len(index), config)
    optimiser = torch.optim.Adam(model.parameters(), lr=config.learning_rate)
    criterion = nn.BCEWithLogitsLoss(reduction="none")

    interactions, targets, labels, mask = encode_sakt(train, index, config.max_length)
    padding = mask == 0
    history = TrainingHistory()
    best_state = {k: v.clone() for k, v in model.state_dict().items()}
    since_improved = 0

    for epoch in range(config.epochs):
        model.train()
        order = torch.randperm(interactions.size(0))
        total = 0.0

        for start in range(0, len(order), config.batch_size):
            rows = order[start:start + config.batch_size]
            # Chuỗi toàn đệm sẽ làm softmax của chú ý ra NaN, bỏ qua cả lô như vậy.
            if bool(padding[rows].all(dim=1).any()):
                continue
            optimiser.zero_grad()
            logits = model(interactions[rows], targets[rows], padding[rows])
            losses = criterion(logits, labels[rows]) * mask[rows]
            loss = losses.sum() / mask[rows].sum().clamp(min=1.0)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            optimiser.step()
            total += loss.detach().item() * len(rows)

        history.train_loss.append(total / interactions.size(0))
        auc = evaluate_sakt(model, validation, index, config)["auc"]
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
def predict_sakt(model: SAKT, sequences: list[Sequence], index: SkillIndex,
                 config: SAKTConfig | None = None) -> tuple[list[float], list[int]]:
    config = config or SAKTConfig()
    model.eval()
    interactions, targets, labels, mask = encode_sakt(sequences, index, config.max_length)
    logits = model(interactions, targets, mask == 0)
    probabilities = torch.sigmoid(logits)
    keep = mask.bool()
    return probabilities[keep].tolist(), labels[keep].long().tolist()


def evaluate_sakt(model: SAKT, sequences: list[Sequence], index: SkillIndex,
                  config: SAKTConfig | None = None) -> dict[str, float]:
    scores, truth = predict_sakt(model, sequences, index, config)
    return {"auc": auc_score(scores, truth), "accuracy": accuracy(scores, truth),
            "log_loss": log_loss(scores, truth), "n": len(truth)}
