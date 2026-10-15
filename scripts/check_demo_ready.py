"""Kiểm máy đã sẵn sàng demo chưa — chạy: python scripts/check_demo_ready.py

Một lệnh, trả lời đúng một câu hỏi: **bây giờ bật lên demo được chưa?**

Có script này vì `git pull` KHÔNG đủ. Kho git cố ý không chứa giáo trình (bản
quyền), kho vector đã dựng (61 MB), `node_modules`, hay model Ollama (vài GB).
Người demo mà phát hiện thiếu lúc đang trước hội đồng thì quá muộn.

Mã thoát: 0 = sẵn sàng, 1 = còn thiếu thứ CHẶN demo.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.config import ROOT  # noqa: E402

OK = "  [OK]   "
WARN = "  [LƯU Ý]"
BAD = "  [THIẾU]"

blockers: list[str] = []
warnings: list[str] = []


def ok(message: str) -> None:
    print(OK + message)


def warn(message: str, fix: str) -> None:
    print(f"{WARN} {message}")
    warnings.append(f"{message}\n       cách xử lý: {fix}")


def bad(message: str, fix: str) -> None:
    print(f"{BAD} {message}")
    blockers.append(f"{message}\n       cách xử lý: {fix}")


# ---------------------------------------------------------------- 1. Python
def check_python() -> None:
    print("\n1. Python và thư viện")
    version = sys.version_info
    if version < (3, 10):
        bad(f"Python {version.major}.{version.minor} quá cũ",
            "cài Python 3.11 rồi tạo lại môi trường ảo")
    else:
        ok(f"Python {version.major}.{version.minor}.{version.micro}")

    for module, package in (
        ("sympy", "sympy"), ("numpy", "numpy"), ("scipy", "scipy"),
        ("networkx", "networkx"), ("fastapi", "fastapi"), ("pydantic", "pydantic"),
        ("httpx", "httpx"), ("torch", "torch"), ("fitz", "pymupdf"),
    ):
        if importlib.util.find_spec(module) is None:
            bad(f"thiếu thư viện {package}", "pip install -r requirements.txt")
            return
    ok("các thư viện lõi đều có")


# ------------------------------------------------------------ 2. Ngân hàng đề
def check_bank() -> None:
    print("\n2. Ngân hàng đề và kỹ năng (có trong git, thường không thiếu)")
    try:
        from src.core.itembank import ITEMS_DIR, ItemBank, load_items
        from src.core.syllabus import chapters_of
    except Exception as exc:
        bad(f"không nạp được ngân hàng đề: {exc}", "kiểm tra lại bước pip install")
        return

    total = 0
    for subject in ("MAE101", "MAD101", "MAI391", "MAS291"):
        bank = ItemBank.load(subject)
        items = list(bank.items.values())
        generated = ITEMS_DIR / f"{subject.lower()}_generated.jsonl"
        if generated.exists():
            items += list(load_items(generated))
        total += len(items)
        empty = [c.name_vi for c in chapters_of(bank, items) if c.items == 0]
        if empty:
            warn(f"{subject}: chương không có đề — {', '.join(empty)}",
                 f"python scripts/build_bank.py {subject} 1200")
    if total >= 4000:
        ok(f"{total} đề trên 4 môn")
    else:
        warn(f"chỉ có {total} đề", "python scripts/build_bank.py all 1200")


# -------------------------------------------------------------- 3. Kho RAG
def check_index() -> None:
    print("\n3. Kho giáo trình — phần dễ thiếu nhất")
    index_dir = ROOT / "data" / "rag_index"
    chunks = index_dir / "chunks.json"
    vectors = index_dir / "embeddings.npy"

    if not chunks.exists():
        bad("CHƯA có kho giáo trình (data/rag_index/chunks.json)",
            "xin thư mục data/rag_index/ (61 MB) từ người viết code — nhanh nhất; "
            "hoặc tải giáo trình theo docs/nguon-tai-lieu.md rồi "
            "python scripts/build_rag_index.py --dense (~40 phút)")
        return

    # chunks.json có hai dạng tuỳ phiên bản: list ở cấp cao nhất, hoặc dict bọc
    # ngoài. Đọc cả hai chứ không giả định một dạng — script kiểm tra mà tự nổ
    # thì còn tệ hơn không có.
    raw = json.loads(chunks.read_text(encoding="utf-8"))
    count = len(raw["chunks"] if isinstance(raw, dict) else raw)
    ok(f"kho có {count} đoạn")

    # Đây là phần quan trọng nhất của cả script.
    #
    # Không có embedding thì KHÔNG có thang tương đồng, nên cơ chế từ chối câu
    # hỏi ngoài phạm vi TẮT HOÀN TOÀN: đo được là 3/3 câu kiểu "cách nấu phở bò"
    # đều nhận một đoạn giáo trình. Tỉ lệ trả lời sai chủ đề cũng nhảy lên 32%.
    # Hội đồng hỏi lệch một câu là vỡ demo.
    if not vectors.exists():
        bad("kho CHƯA có embedding — chỉ chạy được BM25",
            "xin data/rag_index/embeddings.npy, hoặc "
            "ollama pull bge-m3 && python scripts/build_rag_index.py --dense")
        return
    ok(f"có embedding ({vectors.stat().st_size // 1_000_000} MB) — chặn được câu ngoài phạm vi")

    try:
        from src.rag.coverage import chapter_coverage, general_material
        from src.rag.hint_retriever import load_index
        live = load_index()
        thin = []
        for subject in ("MAE101", "MAD101", "MAI391", "MAS291"):
            rows = chapter_coverage(live, subject)
            missing = [r for r in rows if not r.covered]
            if missing and general_material(live, subject) < 300:
                thin.append(f"{subject} ({len(missing)} chương)")
        if thin:
            warn("chương chưa có tài liệu: " + ", ".join(thin),
                 "python scripts/rag_coverage.py để xem chi tiết")
        else:
            ok("mọi chương của 4 môn đều có tài liệu")
    except Exception as exc:
        warn(f"không kiểm được độ phủ: {exc}", "python scripts/rag_coverage.py")


# --------------------------------------------------------------- 4. Ollama
def check_ollama() -> None:
    print("\n4. Model ngôn ngữ (tuỳ chọn — thiếu thì vẫn demo được)")
    if shutil.which("ollama") is None:
        warn("chưa cài Ollama",
             "cài từ ollama.com; thiếu thì gợi ý dùng câu mẫu và phần hỏi lý "
             "thuyết trả nguyên đoạn giáo trình — vẫn đúng, chỉ không mượt")
        return
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=5) as response:
            names = {m["name"] for m in json.load(response).get("models", [])}
    except (urllib.error.URLError, OSError, ValueError):
        warn("Ollama đã cài nhưng chưa chạy", "mở một cửa sổ và chạy: ollama serve")
        return

    ok(f"Ollama đang chạy, có {len(names)} model")

    # bge-m3 CẦN CẢ KHI CHỈ TRA CỨU, không chỉ khi dựng kho: mỗi câu hỏi phải
    # được mã hoá để so với vector trong kho. Bản đầu của script này ghi "chỉ
    # cần khi dựng lại kho" — sai, và sai theo cách làm vỡ demo: thiếu nó thì
    # phần Hỏi lý thuyết không trả lời được câu nào.
    if not any(n.startswith("bge-m3") for n in names):
        if (ROOT / "data" / "rag_index" / "embeddings.npy").exists():
            bad("thiếu bge-m3 — kho CÓ vector nhưng không mã hoá nổi câu hỏi",
                "ollama pull bge-m3 (bắt buộc, cả khi chỉ tra cứu)")
        else:
            warn("thiếu bge-m3 (cần khi dựng kho và khi tra cứu)", "ollama pull bge-m3")
    chat = [n for n in names if n.startswith("qwen2.5")]
    if not chat:
        warn("thiếu model trả lời", "ollama pull qwen2.5:7b-instruct")
    else:
        ok(f"model trả lời: {', '.join(sorted(chat))}")
        if not any("7b" in n for n in chat):
            warn("chỉ có bản 3b", "ollama pull qwen2.5:7b-instruct — tiếng Việt tốt hơn rõ rệt")


# ------------------------------------------------------------------ 5. Web
def check_web() -> None:
    print("\n5. Giao diện web")
    web = ROOT / "web"
    if not (web / "node_modules").exists():
        bad("chưa cài thư viện cho web", "cd web && npm install")
        return
    ok("node_modules đã có")
    if shutil.which("node") is None:
        bad("chưa cài Node.js", "cài Node 20+ từ nodejs.org")
    else:
        ok("Node.js đã có")


# --------------------------------------------------------------- 6. Chạy thử
def check_service() -> None:
    print("\n6. Thử dựng dịch vụ (không mở cổng)")
    try:
        from src.api.app import build_service
        from src.api.db import Store
        from src.core.config import AppConfig
        service = build_service(AppConfig(), store=Store(":memory:"))
        ok(f"dịch vụ dựng được, {len(service.subjects)} môn: {', '.join(service.subjects)}")
    except Exception as exc:
        bad(f"không dựng được dịch vụ: {exc}", "chạy python -m pytest -q để xem lỗi chi tiết")


def main() -> None:
    print("=" * 70)
    print("KIỂM TRA SẴN SÀNG DEMO")
    print("=" * 70)

    check_python()
    check_bank()
    check_index()
    check_ollama()
    check_web()
    check_service()

    print("\n" + "=" * 70)
    if blockers:
        print(f"CHƯA DEMO ĐƯỢC — {len(blockers)} việc phải làm:\n")
        for index, item in enumerate(blockers, 1):
            print(f"  {index}. {item}\n")
    else:
        print("SẴN SÀNG DEMO.\n")
        print("  Cửa sổ 1:  LLM_HINTS=1 OLLAMA_MODEL=qwen2.5:7b-instruct \\")
        print("               python -m uvicorn src.api.app:create_app --factory --port 8000")
        print("  Cửa sổ 2:  cd web && npm run dev")
        print("  Mở:        http://localhost:3000\n")

    if warnings:
        print(f"Nên xử lý nhưng không chặn demo — {len(warnings)} việc:\n")
        for index, item in enumerate(warnings, 1):
            print(f"  {index}. {item}\n")

    raise SystemExit(1 if blockers else 0)


if __name__ == "__main__":
    main()
