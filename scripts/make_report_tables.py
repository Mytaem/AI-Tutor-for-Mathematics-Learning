"""Sinh bảng kết quả cho báo cáo từ file JSON thô — chạy: python scripts/make_report_tables.py

Ghi ra ``docs/results.md``. Mọi con số trong báo cáo lấy từ đây, KHÔNG gõ tay: gõ
tay thì sau vài lần chạy lại thí nghiệm là bảng trong báo cáo và dữ liệu trong
``experiments/`` lệch nhau, mà không ai phát hiện.

Thí nghiệm nào chưa chạy thì in thẳng "chưa chạy" thay vì bỏ trống — người đọc
(và chính mình lúc viết báo cáo) phải thấy ngay chỗ nào còn thiếu.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.config import ROOT  # noqa: E402

EXPERIMENTS = ROOT / "experiments"
OUTPUT = ROOT / "docs" / "results.md"
MISSING = "*chưa chạy*"


def load(path: Path) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def percent(value: float | None, digits: int = 1) -> str:
    """Số phần trăm theo cách viết tiếng Việt: dấu phẩy thập phân."""
    if value is None:
        return "—"
    return f"{value * 100:.{digits}f}".replace(".", ",") + "%"


def number(value: float | None, digits: int = 3) -> str:
    return f"{value:.{digits}f}".replace(".", ",") if value is not None else "—"


# --------------------------------------------------------------------------

def table_exp1() -> str:
    """Một dòng cho MỖI FILE, có cột model.

    Bản đầu gộp theo chế độ và giữ file cuối cùng, nên khi chạy thêm model 7b thì
    bảng có dòng 7b nằm cạnh dòng 3b mà không ghi model — trông như cùng một model
    mà chế độ này tốt hơn chế độ kia gấp đôi.
    """
    labels = {"direct": "hỏi thẳng", "cot": "suy luận từng bước",
              "self_consistency": "tự nhất quán k=3"}
    folder = EXPERIMENTS / "exp1"
    rows = []
    for path in sorted(folder.glob("*.json")) if folder.exists() else []:
        data = load(path)
        if data is None:
            continue
        by = data["by_subject"]
        rows.append(f"| {data['model']} | {labels.get(data['mode'], data['mode'])} | "
                    + " | ".join(percent(by.get(s), 0)
                                 for s in ("MAE101", "MAI391", "MAS291", "MAD101"))
                    + f" | **{percent(data['accuracy'], 1)}** |")
    if not rows:
        return MISSING
    header = ("| Model | Chế độ | MAE101 | MAI391 | MAS291 | MAD101 | Tổng |\n"
              "|---|---|---|---|---|---|---|")
    return header + "\n" + "\n".join(rows)


def table_exp2() -> str:
    data = load(EXPERIMENTS / "exp2" / "step_detection.json")
    if data is None:
        return MISSING
    rows = [
        "| Chỉ số | Kết quả |",
        "|---|---|",
        f"| Phát hiện có chỗ sai trong chuỗi bước | {data['found']}/{data['total']} = "
        f"{percent(data['detection_rate'])} |",
        f"| Chỉ **đúng** bước đã bị cài lỗi | {data['exact']}/{data['total']} = "
        f"{percent(data['exact_rate'])} |",
        f"| Báo oan trên lời giải mẫu (đúng) | {percent(data['false_alarm_rate'])} "
        f"trên {data['checked_correct']} lời giải |",
        "",
        f"*Chỉ phủ {len(data['by_code'])} mã lỗi mức bước: "
        f"{', '.join(sorted(data['by_code']))} — xem phần hạn chế trong "
        "`docs/evaluation-protocol.md`.*",
    ]
    return "\n".join(rows)


def table_exp3() -> str:
    folder = EXPERIMENTS / "exp3"
    if not folder.exists():
        return MISSING
    rows = []
    for path in sorted(folder.glob("*.json")):
        data = load(path)
        if data is None:
            continue
        shots = data.get("shots", 0)
        label = f"{data['model']} {'zero-shot' if not shots else f'few-shot {shots}'}"
        rows.append(f"| {label} | {number(data['macro_f1'])} | {percent(data['accuracy'])} | "
                    f"{percent(data['tier_accuracy'])} | {percent(data['invalid_rate'])} |")
    lora = load(folder / "lora_metrics.json")
    if lora:
        after = lora["after"]
        rows.append(f"| **LoRA {lora['base_model'].split('/')[-1]}** | **{number(after['macro_f1'])}** | "
                    f"{percent(after['accuracy'])} | {percent(after['tier_accuracy'])} | "
                    f"{percent(after['invalid_rate'])} |")
    header = ("| Cấu hình | macro-F1 | accuracy | đúng tầng lỗi | bịa mã |\n|---|---|---|---|---|")
    return header + "\n" + "\n".join(rows) if rows else MISSING


def table_exp4() -> str:
    rows = []
    for name, label in (("vi_k5.json", "tiếng Việt"), ("en_k5.json", "tiếng Anh")):
        data = load(EXPERIMENTS / "exp4" / name)
        if data is None:
            continue
        summary = data["summary"]
        rows.append(f"| {label} | " + " | ".join(
            number(summary[mode]["recall_at_k"]) for mode in ("bm25", "dense", "hybrid")) + " |")
    if not rows:
        return MISSING
    return ("| Ngôn ngữ câu hỏi | BM25 | dense | hybrid |\n|---|---|---|---|\n" + "\n".join(rows))


def table_exp5() -> str:
    rows = []
    subjects = [path.stem.upper() for path in sorted((EXPERIMENTS / "exp5").glob("*.json"))] \
        if (EXPERIMENTS / "exp5").exists() else []
    if not subjects:
        return MISSING
    data = {subject: load(EXPERIMENTS / "exp5" / f"{subject.lower()}.json") for subject in subjects}
    for model, label in (("majority", "majority"), ("bkt", "BKT"), ("dkt", "**DKT**"), ("sakt", "SAKT")):
        cells = [number(data[s]["summary"][model]["auc"]) for s in subjects]
        rows.append(f"| {label} | " + " | ".join(cells) + " |")
    return (f"| Mô hình | {' | '.join(f'AUC {s}' for s in subjects)} |\n"
            f"|---{'|---' * len(subjects)}|\n" + "\n".join(rows))


def table_exp6() -> str:
    folder = EXPERIMENTS / "exp6"
    data = load(folder / "mae101_mae_int.json") if folder.exists() else None
    if data is None:
        return MISSING
    rows = []
    for strategy, values in data["summary"].items():
        steps = f"{values['steps_to_target']:.0f}" if values.get("steps_to_target") else "—"
        rows.append(f"| {strategy} | {percent(values['accuracy'])} | {values['mastered']:.1f} | "
                    f"{percent(values['reached_target'], 0)} | {steps} | {values['wrong_streak']:.1f} |")
    return ("| Chiến lược | Tỉ lệ đúng | Kỹ năng thạo | Đạt mục tiêu | Số bài | Sai liên tiếp |\n"
            "|---|---|---|---|---|---|\n" + "\n".join(rows))


def table_exp7() -> str:
    folder = EXPERIMENTS / "exp7"
    paths = sorted(folder.glob("judge_*.json")) if folder.exists() else []
    if not paths:
        return MISSING
    data = load(paths[0])
    rows = [
        f"| {data['model']} làm giám khảo | {percent(data['llm']['accuracy'])} | "
        f"{percent(data['llm']['false_accept'])} | {percent(data['llm']['false_reject'])} |",
        f"| **Kiểm chứng ký hiệu** | **{percent(data['symbolic']['accuracy'])}** | "
        f"**{percent(data['symbolic']['false_accept'])}** | "
        f"**{percent(data['symbolic']['false_reject'])}** |",
    ]
    return ("| Bộ chấm | Chính xác | Báo ĐÚNG cho bài SAI | Báo SAI cho bài ĐÚNG |\n"
            "|---|---|---|---|\n" + "\n".join(rows))


def table_exp8() -> str:
    """Một dòng cho mỗi (model, cấu hình) — để thấy cả ảnh hưởng của cỡ model."""
    folder = EXPERIMENTS / "exp8"
    paths = sorted(folder.glob("*.json")) if folder.exists() else []
    if not paths:
        return MISSING
    labels = {"raw": "không guardrail, prompt không có đáp án",
              "raw+answer": "không guardrail, prompt CÓ đáp án",
              "full": "hệ thống thật (guardrail + viết lại)",
              "full+answer": "guardrail, prompt CÓ đáp án"}
    rows = []
    for path in paths:
        data = load(path)
        if data is None:
            continue
        for name, values in data["summary"].items():
            rows.append(f"| {data['model']} | {labels.get(name, name)} | "
                        f"{percent(values['leak_rate'])} | {percent(values['fallback_rate'])} | "
                        f"{values['mean_attempts']:.2f} |")
    return ("| Model | Cấu hình | Lộ đáp án | Về template | Lượt TB |\n"
            "|---|---|---|---|---|\n" + "\n".join(rows))


def main() -> None:
    sections = [
        ("EXP-1 — mô hình tự giải toán (chấm bằng verifier)", table_exp1()),
        ("EXP-2b — chỉ đúng bước sai đầu tiên", table_exp2()),
        ("EXP-3 — phân loại mã lỗi", table_exp3()),
        ("EXP-4 — truy xuất giáo trình (Recall@5)", table_exp4()),
        ("EXP-5 — mô hình theo dõi năng lực", table_exp5()),
        ("EXP-6 — chiến lược chọn bài (MAE101, chương tích phân)", table_exp6()),
        ("EXP-7a — bỏ tầng kiểm chứng ký hiệu", table_exp7()),
        ("EXP-8 — chống lộ đáp án", table_exp8()),
    ]

    lines = [
        "# Bảng kết quả",
        "",
        f"*Sinh tự động bằng `python scripts/make_report_tables.py`, ngày {date.today().isoformat()}.*",
        "*Đừng sửa tay file này — sửa ở `experiments/` rồi chạy lại script.*",
        "",
    ]
    for title, table in sections:
        lines += [f"## {title}", "", table, ""]

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(lines), encoding="utf-8")
    missing = [title for title, table in sections if table == MISSING]
    print(f"Đã ghi {OUTPUT}")
    if missing:
        print("Chưa có dữ liệu: " + "; ".join(missing))


if __name__ == "__main__":
    main()
