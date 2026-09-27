"""Nạp ASSISTments 2009–2010 skill builder — dữ liệu người học THẬT.

Vì sao cần: EXP-5 chạy trên học sinh mô phỏng cho DKT thắng BKT rất đậm, nhưng
chính dữ liệu đó được sinh ra với một năng lực NỀN dùng chung cho mọi kỹ năng —
thứ mà DKT bắt được còn BKT về cấu trúc thì không. Muốn biết khoảng cách thật là
bao nhiêu thì phải chạy trên log người học thật, và ASSISTments là bộ mà gần như
mọi bài báo knowledge tracing đều báo cáo, nên đối chiếu được với literature.

Bốn bước làm sạch, đều là quy ước chuẩn của các bài báo DKT; làm khác đi thì con
số không so được với ai:

1. Bỏ lượt không có ``skill_id`` (bài không gắn kỹ năng nào).
2. Chỉ giữ ``original == 1`` — bỏ các bài "scaffolding" sinh ra khi học sinh làm
   sai, vì chúng phụ thuộc vào chính kết quả đang cần dự đoán.
3. Sắp theo ``order_id`` để đúng thứ tự thời gian.
4. Bỏ học sinh có quá ít lượt (mặc định dưới 10): chuỗi quá ngắn thì cả BKT lẫn
   DKT đều chưa kịp học được gì, chỉ làm nhiễu số liệu.
"""

from __future__ import annotations

from pathlib import Path

from src.core.config import ROOT

DEFAULT_PATH = ROOT / "data" / "kt" / "ASSISTments_skill_builder_data.csv"
MIN_INTERACTIONS = 10

Sequence = list[tuple[str, int]]


def load_sequences(
    path: str | Path | None = None,
    min_interactions: int = MIN_INTERACTIONS,
    max_students: int | None = None,
    max_length: int = 200,
) -> list[Sequence]:
    """Chuỗi ``(kỹ năng, đúng/sai)`` cho mỗi học sinh, đúng thứ tự thời gian."""
    import pandas as pd

    path = Path(path) if path else DEFAULT_PATH
    if not path.exists():
        raise FileNotFoundError(
            f"Chưa có {path}. Tải bằng:\n"
            "  kaggle datasets download -d kanishkjain03/assistments-skill -p data/kt --unzip"
        )

    frame = pd.read_csv(path, encoding="latin-1", low_memory=False)
    # File gốc có BOM ở tên cột đầu tiên; đổi tên cho mọi thứ phía sau khỏi phải biết.
    frame = frame.rename(columns={column: column.lstrip("﻿ï»¿") for column in frame.columns})

    frame = frame.dropna(subset=["skill_id", "user_id", "correct", "order_id"])
    if "original" in frame.columns:
        frame = frame[frame["original"] == 1]
    frame = frame.sort_values(["user_id", "order_id"])

    sequences: list[Sequence] = []
    for _, group in frame.groupby("user_id", sort=True):
        steps = [
            (str(int(skill)), int(correct))
            for skill, correct in zip(group["skill_id"], group["correct"])
            if correct in (0, 1)
        ]
        if len(steps) >= min_interactions:
            sequences.append(steps[:max_length])
        if max_students and len(sequences) >= max_students:
            break
    return sequences


def describe(sequences: list[Sequence]) -> dict:
    interactions = sum(len(sequence) for sequence in sequences)
    skills = {skill for sequence in sequences for skill, _ in sequence}
    correct = sum(answer for sequence in sequences for _, answer in sequence)
    return {
        "students": len(sequences),
        "interactions": interactions,
        "skills": len(skills),
        "accuracy": correct / interactions if interactions else 0.0,
        "mean_length": interactions / len(sequences) if sequences else 0.0,
    }
