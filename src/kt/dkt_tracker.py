"""Dùng DKT ĐÃ HUẤN LUYỆN để ước lượng năng lực lúc phục vụ thật.

Cho tới đây DKT mới chỉ là một thí nghiệm offline: huấn luyện, đo AUC, viết vào
báo cáo. Lớp này đưa nó vào vòng phục vụ — cùng một giao diện với ``BKTTracker``
nên bộ chọn bài không cần biết đang dùng mô hình nào.

Khác biệt cốt lõi với BKT: BKT giữ một con số cho mỗi kỹ năng và cập nhật độc
lập; DKT nhìn TOÀN BỘ chuỗi làm bài rồi cho ra xác suất đúng cho mọi kỹ năng
cùng lúc, nên nó bắt được chuyện làm tốt kỹ năng này thì kỹ năng kia cũng khá
lên. Cái giá phải trả: mỗi lần cần ước lượng là một lần chạy mạng trên cả chuỗi,
và phải có mô hình đã huấn luyện sẵn cho đúng tập kỹ năng của môn đó.

Nếu chưa có mô hình cho môn nào thì ``load_tracker`` trả None và tầng gọi tự
quay về BKT — hệ thống không bao giờ được hỏng chỉ vì thiếu một file .pt.
"""

from __future__ import annotations

import json
from pathlib import Path

import torch

from src.core.config import ROOT
from src.kt.dkt import DKT, DKTConfig, SkillIndex

MODEL_DIR = ROOT / "models" / "dkt"


class DKTTracker:
    """Cùng giao diện với ``BKTTracker``, nhưng ước lượng bằng mạng hồi tiếp."""

    def __init__(self, model: DKT, index: SkillIndex, prior: dict[str, float] | None = None) -> None:
        self.model = model.eval()
        self.index = index
        self.history: list[tuple[str, int]] = []
        # Tiên nghiệm dùng cho kỹ năng mà mô hình chưa từng thấy, và cho lúc chuỗi
        # còn rỗng — khi đó DKT chưa có gì để suy luận.
        self.prior = dict(prior or {})
        self._cache: dict[str, float] | None = None

    # ------------------------------------------------------------------

    def observe(self, skill_ids: list[str], correct: bool) -> dict[str, float]:
        for skill in skill_ids:
            self.history.append((skill, int(correct)))
        self._cache = None
        return {skill: self.mastery(skill) for skill in skill_ids}

    def mastery(self, skill_id: str) -> float:
        """Xác suất làm đúng kỹ năng này ở lượt kế tiếp."""
        if skill_id not in self.index.index:
            return self.prior.get(skill_id, 0.25)
        if self._cache is None:
            self._cache = self._predict_all()
        return self._cache.get(skill_id, self.prior.get(skill_id, 0.25))

    def probability_for(self, skill_id: str) -> float:
        """DKT đã cho thẳng xác suất đúng, không phải đi qua slip/guess như BKT."""
        return self.mastery(skill_id)

    def set_mastery(self, skill_id: str, value: float) -> None:
        """Đặt tiên nghiệm — dùng cho cold start, không ghi đè được lịch sử."""
        self.prior[skill_id] = min(max(value, 0.0), 1.0)
        self._cache = None

    def snapshot(self) -> dict[str, float]:
        return {skill: self.mastery(skill) for skill in self.index.skills}

    def weakest(self, candidates: list[str], limit: int = 3) -> list[str]:
        return sorted(candidates, key=self.mastery)[:limit]

    # ------------------------------------------------------------------

    @torch.no_grad()
    def _predict_all(self) -> dict[str, float]:
        """Chạy mạng trên cả chuỗi, lấy dự đoán ở bước CUỐI cho mọi kỹ năng."""
        if not self.history:
            return dict(self.prior)

        skills = len(self.index)
        usable = [(skill, answer) for skill, answer in self.history if skill in self.index.index]
        if not usable:
            return dict(self.prior)

        inputs = torch.zeros(1, len(usable), 2 * skills)
        for step, (skill, answer) in enumerate(usable):
            inputs[0, step, self.index.index[skill] + (skills if answer else 0)] = 1.0

        logits = self.model(inputs)[0, -1]
        probabilities = torch.sigmoid(logits).tolist()
        return {skill: probabilities[position] for skill, position in self.index.index.items()}


# --------------------------------------------------------------------------

def save_tracker_model(model: DKT, index: SkillIndex, subject: str,
                       directory: Path | None = None,
                       config: DKTConfig | None = None) -> Path:
    """Lưu trọng số KÈM siêu tham số dựng mạng.

    Lưu mỗi ``state_dict`` là không đủ: lúc nạp phải dựng lại đúng kiến trúc, mà
    kích thước lớp ẩn nằm ở ``DKTConfig``. Bản đầu dựng bằng cấu hình mặc định nên
    mô hình nào huấn luyện với lớp ẩn khác 64 là nạp lại vỡ ngay (test bắt được).
    """
    directory = directory or MODEL_DIR
    directory.mkdir(parents=True, exist_ok=True)
    architecture = {
        "hidden_size": model.rnn.hidden_size,
        "layers": model.rnn.num_layers,
        "dropout": float(model.dropout.p),
    }
    path = directory / f"{subject.lower()}.pt"
    torch.save({"state_dict": model.state_dict(), "skills": index.skills,
                "architecture": architecture}, path)
    (directory / f"{subject.lower()}.json").write_text(
        json.dumps({"subject": subject, "skills": index.skills, "architecture": architecture},
                   ensure_ascii=False, indent=1),
        encoding="utf-8")
    return path


def load_tracker(subject: str, prior: dict[str, float] | None = None,
                 directory: Path | None = None) -> DKTTracker | None:
    """Nạp mô hình của môn; chưa huấn luyện thì trả None để tầng gọi dùng BKT."""
    path = (directory or MODEL_DIR) / f"{subject.lower()}.pt"
    if not path.exists():
        return None
    payload = torch.load(path, map_location="cpu", weights_only=False)
    index = SkillIndex(payload["skills"])
    architecture = payload.get("architecture", {})
    config = DKTConfig(
        hidden_size=architecture.get("hidden_size", DKTConfig.hidden_size),
        layers=architecture.get("layers", DKTConfig.layers),
        dropout=architecture.get("dropout", DKTConfig.dropout),
    )
    model = DKT(len(index), config)
    model.load_state_dict(payload["state_dict"])
    return DKTTracker(model, index, prior)
