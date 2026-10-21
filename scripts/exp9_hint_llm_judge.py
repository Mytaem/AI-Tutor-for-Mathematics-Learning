"""EXP-9 — mô hình chấm phiếu gợi ý, TẠM THAY ba người chấm khi chưa có người.

    python scripts/exp9_hint_llm_judge.py
    python scripts/exp9_hint_llm_judge.py --models qwen2.5:7b-instruct qwen2.5:3b-instruct

Đây KHÔNG phải đánh giá của người. Giám khảo cùng họ Qwen với model sinh gợi ý,
nên có thiên lệch tự chấm mình. Kết quả chỉ dùng làm số tham khảo và phải ghi rõ
là "máy chấm" trong báo cáo; chấm tay (docs/viec-can-lam.md, việc 2) vẫn là bằng
chứng chính.

Ra ``data/eval/hint_ratings_llm.csv`` với cột ``<tiêu chí>_m1``, ``_m2``... nên
dùng lại được ``build_hint_rating_sheet.py --kappa`` để tính kappa giữa các máy.
Chạy lại thì bỏ qua dòng đã chấm.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.config import ROOT, LLMConfig  # noqa: E402
from src.llm.client import OpenAICompatibleBackend  # noqa: E402

AXES = ("dung_toan", "khong_lo", "su_pham", "tieng_viet")
SHEET = ROOT / "data" / "eval" / "hint_ratings_template.csv"
OUT = ROOT / "data" / "eval" / "hint_ratings_llm.csv"

SYSTEM = (
    "Bạn là giảng viên toán chấm chất lượng câu gợi ý mà một gia sư AI đưa cho sinh "
    "viên vừa làm sai. Cho điểm nguyên 1–5 theo bốn tiêu chí:\n"
    "- dung_toan: gợi ý có nói gì sai về toán không (5 = hoàn toàn đúng, 1 = sai kiến thức).\n"
    "- khong_lo: có giữ được đáp án không. Mức gợi ý 1, 2, 3 mà nói ra đáp án cuối thì "
    "cho 1; mức 4 trở lên được phép nói đáp án.\n"
    "- su_pham: có dẫn dắt người học tự nghĩ không (5 = gợi mở đúng chỗ sai, "
    "1 = làm hộ hoặc chung chung không liên quan).\n"
    "- tieng_viet: câu tiếng Việt có tự nhiên, đúng giọng thầy–trò không.\n"
    "Chấm khắt khe, không cho 5 nếu có điểm yếu rõ ràng. Chỉ trả về một dòng JSON: "
    '{"dung_toan": n, "khong_lo": n, "su_pham": n, "tieng_viet": n, "ghi_chu": "lý do ngắn"}'
)


def prompt(row: dict) -> list[dict]:
    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": (
            f"ĐỀ BÀI: {row['de_bai']}\n"
            f"BÀI LÀM SAI CỦA SINH VIÊN: {row['bai_lam_sai']}\n"
            f"MỨC GỢI Ý: {row['muc']} (trên 5)\n"
            f"CÂU GỢI Ý: {row['goi_y']}"
        )},
    ]


def parse(text: str) -> dict | None:
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
        scores = {axis: int(data[axis]) for axis in AXES}
    except (ValueError, KeyError, TypeError):
        return None
    if not all(1 <= v <= 5 for v in scores.values()):
        return None
    scores["ghi_chu"] = str(data.get("ghi_chu", ""))[:200]
    return scores


def judge(backend: OpenAICompatibleBackend, row: dict) -> dict | None:
    # Model nhỏ thỉnh thoảng trả JSON hỏng; thử lại một lần ở nhiệt độ khác.
    for temperature in (0.0, 0.3):
        reply = backend.chat(prompt(row), temperature=temperature, max_tokens=160)
        scores = parse(reply.text)
        if scores:
            return scores
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+",
                        default=["qwen2.5:7b-instruct", "qwen2.5:3b-instruct"])
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    rows = list(csv.DictReader(SHEET.open(encoding="utf-8-sig")))[: args.limit]
    done: dict[str, dict] = {}
    if OUT.exists():
        done = {r["stt"]: r for r in csv.DictReader(OUT.open(encoding="utf-8-sig"))}

    config = LLMConfig()
    backends = [OpenAICompatibleBackend(f"m{i}", config.ollama_url, model, 180.0)
                for i, model in enumerate(args.models, start=1)]
    base = [k for k in rows[0] if k not in AXES and k != "ghi_chu"]
    fields = base + [f"{a}_m{i}" for i in range(1, len(backends) + 1) for a in AXES] + \
        [f"ghi_chu_m{i}" for i in range(1, len(backends) + 1)]

    failed = 0
    for position, row in enumerate(rows, start=1):
        out = done.get(row["stt"]) or {k: row[k] for k in base}
        for i, backend in enumerate(backends, start=1):
            if out.get(f"dung_toan_m{i}"):
                continue
            scores = judge(backend, row)
            if scores is None:
                failed += 1
                continue
            for axis in AXES:
                out[f"{axis}_m{i}"] = scores[axis]
            out[f"ghi_chu_m{i}"] = scores["ghi_chu"]
        done[row["stt"]] = out
        with OUT.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(done.values())
        print(f"\r{position}/{len(rows)}", end="", flush=True)

    print(f"\nGhi {OUT.relative_to(ROOT)} — {failed} lượt chấm hỏng JSON (để trống).")
    for i, model in enumerate(args.models, start=1):
        print(f"  m{i} = {model}")
    print(f"Tính đồng thuận: python scripts/build_hint_rating_sheet.py --kappa {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
