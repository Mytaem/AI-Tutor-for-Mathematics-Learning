"""EXP-5 — so bốn mô hình theo dõi năng lực trên cùng một tập dữ liệu.

    python scripts/exp5_kt.py                          # MAE101, 360 học sinh mô phỏng
    python scripts/exp5_kt.py --subject MAD101 --students 150 --seeds 3

    majority  đoán theo tỉ lệ đúng chung — mốc sàn, AUC phải bằng 0.5
    BKT       mô hình kinh điển, tham số KHỚP TỪ DỮ LIỆU bằng tìm kiếm trên lưới
    DKT       GRU, trạng thái ẩn chung cho cả chuỗi
    SAKT      self-attention, mỗi dự đoán tự chọn lượt quá khứ liên quan

Dữ liệu sinh từ học sinh mô phỏng, trộn ba chiến lược chọn bài (zpd, tuần tự,
ngẫu nhiên) để mô hình không học thuộc thói quen của một chiến lược.

Chia dữ liệu THEO NGƯỜI HỌC (70/15/15), không theo lượt: chia theo lượt thì các
lượt của cùng một người nằm cả ở train lẫn test, mô hình học thuộc người đó và
AUC đẹp lên một cách giả tạo.

**Đọc kết quả cho đúng:** học sinh mô phỏng có một năng lực NỀN dùng chung cho
mọi kỹ năng. Mô hình chia sẻ được thông tin giữa các kỹ năng (DKT, SAKT) đoán
được ngay từ vài lượt đầu rằng người này khá hay yếu, còn BKT về cấu trúc không
làm được. Nên khoảng cách đo ở đây là chặn TRÊN cho lợi thế của DKT, không phải
bằng chứng cho hiệu quả ngoài đời. Muốn kết luận thật thì phải chạy lại trên
ASSISTments hoặc log người dùng thật.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.config import ROOT  # noqa: E402
from src.core.itembank import ITEMS_DIR, ItemBank, load_items  # noqa: E402
from src.kt.baselines import bkt_predict, fit_bkt, majority_predict  # noqa: E402
from src.kt.dkt import (  # noqa: E402
    DKTConfig,
    SkillIndex,
    accuracy,
    auc_score,
    evaluate,
    log_loss,
    split_sequences,
    train_dkt,
)
from src.kt.sakt import SAKTConfig, evaluate_sakt, train_sakt  # noqa: E402
from src.kt.simulator import simulate_cohort, to_sequences  # noqa: E402

MIXED_STRATEGIES = ("zpd", "sequential", "random")


def build_sequences(subject: str, students: int, steps: int, seed: int):
    bank = ItemBank.load(subject)
    items = list(bank.items.values())
    generated = ITEMS_DIR / f"{subject.lower()}_generated.jsonl"
    if generated.exists():
        items += load_items(generated)
    usable = [i for i in items if i.skills and set(i.skills) <= set(bank.skills)]

    sequences = []
    for offset, strategy in enumerate(MIXED_STRATEGIES):
        results = simulate_cohort(usable, bank.skills, students=students // len(MIXED_STRATEGIES),
                                  strategy=strategy, steps=steps, seed=seed + 101 * offset)
        sequences += to_sequences(results)
    return sequences, bank


def build_assistments(max_students: int, max_length: int):
    """Log người học THẬT — để đối chiếu AUC với literature.

    Giới hạn số học sinh và độ dài chuỗi vì ``encode`` của DKT dựng một tensor
    đặc kích thước (số chuỗi × độ dài × 2·số kỹ năng): với 118 kỹ năng và 3.087
    học sinh × 200 lượt thì riêng nó đã hơn nửa GB, mà máy này chạy CPU.
    """
    from src.kt.assistments import describe, load_sequences

    sequences = load_sequences(max_students=max_students, max_length=max_length)
    stats = describe(sequences)
    print(f"  ASSISTments: {stats['students']} học sinh / {stats['interactions']} lượt / "
          f"{stats['skills']} kỹ năng / đúng {stats['accuracy']:.1%}")
    return sequences


def run_once(subject: str, students: int, steps: int, seed: int, epochs: int,
             dataset: str = "simulated", max_length: int = 100) -> dict:
    if dataset == "assistments":
        sequences = build_assistments(students, max_length)
    else:
        sequences, _ = build_sequences(subject, students, steps, seed)
    train, validation, test = split_sequences(sequences, seed=seed)
    index = SkillIndex.from_sequences(sequences)
    interactions = sum(len(s) for s in sequences)
    print(f"  {len(sequences)} chuỗi / {interactions} lượt / {len(index)} kỹ năng "
          f"→ train {len(train)}, val {len(validation)}, test {len(test)}")

    row: dict[str, dict] = {}

    scores, truth = majority_predict(train, test)
    row["majority"] = _metrics(scores, truth, 0.0)

    started = time.perf_counter()
    fit = fit_bkt(train)
    scores, truth = bkt_predict(test, fit.params)
    row["bkt"] = _metrics(scores, truth, time.perf_counter() - started)
    row["bkt"]["params"] = fit.params.__dict__

    started = time.perf_counter()
    config = DKTConfig(epochs=epochs, seed=seed)
    model, history = train_dkt(train, validation, index, config)
    result = evaluate(model, test, index, config)
    row["dkt"] = {**result, "seconds": time.perf_counter() - started,
                  "best_epoch": history.best_epoch, "val_auc": history.best_auc}

    started = time.perf_counter()
    sakt_config = SAKTConfig(epochs=epochs, seed=seed)
    sakt, sakt_history = train_sakt(train, validation, index, sakt_config)
    result = evaluate_sakt(sakt, test, index, sakt_config)
    row["sakt"] = {**result, "seconds": time.perf_counter() - started,
                   "best_epoch": sakt_history.best_epoch, "val_auc": sakt_history.best_auc}

    return row


def _metrics(scores: list[float], truth: list[int], seconds: float) -> dict:
    return {"auc": auc_score(scores, truth), "accuracy": accuracy(scores, truth),
            "log_loss": log_loss(scores, truth), "n": len(truth), "seconds": seconds}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--subject", default="MAE101")
    parser.add_argument("--students", type=int, default=360)
    parser.add_argument("--steps", type=int, default=50)
    parser.add_argument("--seeds", type=int, default=3)
    parser.add_argument("--epochs", type=int, default=25)
    parser.add_argument("--data", choices=("simulated", "assistments"), default="simulated",
                        help="assistments = log người học thật, để đối chiếu literature")
    parser.add_argument("--max-length", type=int, default=100, help="chỉ dùng với --data assistments")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    label = "ASSISTments (người học thật)" if args.data == "assistments" else args.subject
    print(f"\nEXP-5 — {label}: tối đa {args.students} học sinh × {args.seeds} seed\n")
    runs = []
    for index in range(args.seeds):
        print(f"seed {index + 1}/{args.seeds}")
        runs.append(run_once(args.subject, args.students, args.steps, 1000 + 53 * index,
                             args.epochs, args.data, args.max_length))

    models = list(runs[0])
    summary = {
        model: {
            metric: statistics.mean(run[model][metric] for run in runs)
            for metric in ("auc", "accuracy", "log_loss", "seconds")
            if metric in runs[0][model]
        } | {
            "auc_sd": statistics.pstdev([run[model]["auc"] for run in runs]) if len(runs) > 1 else 0.0,
        }
        for model in models
    }

    print(f"\n{'mô hình':<10}{'AUC':>10}{'±':>7}{'ACC':>9}{'log loss':>11}{'giây':>9}")
    for model, metrics in summary.items():
        print(f"{model:<10}{metrics['auc']:>10.3f}{metrics['auc_sd']:>7.3f}"
              f"{metrics['accuracy']:>9.3f}{metrics.get('log_loss', 0):>11.3f}{metrics['seconds']:>9.1f}")

    best = max(summary, key=lambda m: summary[m]["auc"])
    print(f"\n  AUC cao nhất: {best}")
    print(f"  tham số BKT khớp được: {runs[0]['bkt']['params']}")

    out = args.out or ROOT / "experiments" / "exp5" / (
        "assistments.json" if args.data == "assistments" else f"{args.subject.lower()}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "subject": args.subject, "dataset": args.data,
        "students": args.students, "steps": args.steps,
        "seeds": args.seeds, "epochs": args.epochs, "summary": summary, "runs": runs,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nĐã ghi {out}\n")


if __name__ == "__main__":
    main()
