"""Huấn luyện DKT cho từng môn để DÙNG THẬT — chạy: python scripts/train_dkt_for_serving.py

    python scripts/train_dkt_for_serving.py                 # cả 4 môn
    python scripts/train_dkt_for_serving.py MAE101 --students 600

Khác ``scripts/exp5_kt.py``: ở đó DKT được huấn luyện để ĐO (chia train/test, báo
AUC), còn ở đây để PHỤC VỤ — huấn luyện trên toàn bộ dữ liệu mô phỏng của môn rồi
lưu ra ``models/dkt/<môn>.pt`` cho API nạp.

Vì sao huấn luyện trên học sinh mô phỏng chứ không trên ASSISTments: mô hình phải
nói về ĐÚNG tập kỹ năng của môn (``MAE.INT.SUBST``...), mà ASSISTments là kỹ năng
của chương trình khác hẳn. Khi có log người dùng thật thì huấn luyện lại trên đó —
đường dẫn và giao diện không đổi.

Vẫn giữ một phần validation để dừng sớm: huấn luyện tới lúc quá khớp rồi đem ra
phục vụ thì ước lượng năng lực còn tệ hơn BKT.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.itembank import ITEMS_DIR, ItemBank, load_items  # noqa: E402
from src.kt.dkt import DKTConfig, SkillIndex, evaluate, split_sequences, train_dkt  # noqa: E402
from src.kt.dkt_tracker import MODEL_DIR, save_tracker_model  # noqa: E402
from src.kt.simulator import simulate_cohort, to_sequences  # noqa: E402

SUBJECTS = ("MAE101", "MAI391", "MAS291", "MAD101")
STRATEGIES = ("zpd", "sequential", "random")


def build(subject: str, students: int, steps: int, seed: int):
    bank = ItemBank.load(subject)
    items = list(bank.items.values())
    generated = ITEMS_DIR / f"{subject.lower()}_generated.jsonl"
    if generated.exists():
        items += load_items(generated)
    usable = [item for item in items if item.skills and set(item.skills) <= set(bank.skills)]

    sequences = []
    for offset, strategy in enumerate(STRATEGIES):
        results = simulate_cohort(usable, bank.skills, students=students // len(STRATEGIES),
                                  strategy=strategy, steps=steps, seed=seed + 101 * offset)
        sequences += to_sequences(results)
    return sequences


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("subject", nargs="?", default=None)
    parser.add_argument("--students", type=int, default=600)
    parser.add_argument("--steps", type=int, default=60)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--seed", type=int, default=20260927)
    args = parser.parse_args()

    subjects = [args.subject.upper()] if args.subject else list(SUBJECTS)
    for subject in subjects:
        sequences = build(subject, args.students, args.steps, args.seed)
        index = SkillIndex.from_sequences(sequences)
        train, validation, _ = split_sequences(sequences, ratios=(0.85, 0.15, 0.0), seed=args.seed)
        config = DKTConfig(epochs=args.epochs, seed=args.seed)

        model, history = train_dkt(train, validation, index, config)
        result = evaluate(model, validation, index, config)
        path = save_tracker_model(model, index, subject)

        print(f"{subject}: {len(sequences)} chuỗi / {sum(len(s) for s in sequences)} lượt / "
              f"{len(index)} kỹ năng → AUC {result['auc']:.3f} "
              f"(epoch tốt nhất {history.best_epoch}) → {path.name}")

    print(f"\nĐã lưu vào {MODEL_DIR}. Bật khi chạy API: KT_MODEL=dkt\n")


if __name__ == "__main__":
    main()
