"""Đẩy job huấn luyện lên Kaggle và theo dõi — chạy: python scripts/kaggle_push.py

    python scripts/kaggle_push.py                  # đẩy và chạy
    python scripts/kaggle_push.py --status         # xem kernel đang chạy tới đâu
    python scripts/kaggle_push.py --fetch          # tải log và adapter về

Cần ``~/.kaggle/access_token`` (hoặc biến môi trường ``KAGGLE_API_TOKEN``).

Hai chỗ phải xử lý riêng cho máy này, đều đã gặp thật:

- **IPv6**: DNS trả địa chỉ NAT64 cho kaggle.com và kết nối treo; phải ép IPv4.
- **Thư mục tạm của CLI**: nó dựng tên file tạm từ đường dẫn truyền vào, nên chạy
  với đường dẫn tuyệt đối kiểu Windows là hỏng. Luôn chạy với ``-p .`` từ trong
  chính thư mục cần đẩy.
"""

from __future__ import annotations

import argparse
import json
import shutil
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

USERNAME = "dngthmtm"
DATASET_ID = f"{USERNAME}/ai-tutor-error-codes"
KERNEL_ID = f"{USERNAME}/ai-tutor-lora-error-classifier"
WORK_DIR = ROOT / ".kaggle_tmp"

KERNEL_METADATA = {
    "id": KERNEL_ID,
    "title": "AI Tutor LoRA error classifier",
    "code_file": "kaggle_train_lora.py",
    "language": "python",
    "kernel_type": "script",
    "is_private": True,
    "enable_gpu": True,
    "enable_internet": True,          # cần để tải model gốc từ HuggingFace
    "dataset_sources": [DATASET_ID],
    "competition_sources": [],
    "kernel_sources": [],
}


def _force_ipv4() -> None:
    original = socket.getaddrinfo

    def ipv4_only(host, port, family=0, type=0, proto=0, flags=0):
        return original(host, port, socket.AF_INET, type, proto, flags)

    socket.getaddrinfo = ipv4_only


def kaggle(*args: str, cwd: Path | None = None) -> int:
    """Gọi CLI Kaggle trong một tiến trình con đã vá IPv4."""
    helper = WORK_DIR / "_cli.py"
    helper.parent.mkdir(parents=True, exist_ok=True)
    helper.write_text(
        "import socket, sys\n"
        "_original = socket.getaddrinfo\n"
        "socket.getaddrinfo = lambda h, p, f=0, t=0, pr=0, fl=0: _original(h, p, socket.AF_INET, t, pr, fl)\n"
        "from kaggle.cli import main\n"
        "sys.exit(main())\n",
        encoding="utf-8",
    )
    command = [sys.executable, str(helper), *args]
    return subprocess.call(command, cwd=str(cwd or ROOT))


def push() -> None:
    folder = WORK_DIR / "kernel"
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)

    shutil.copy(ROOT / "scripts" / "kaggle_train_lora.py", folder / "kaggle_train_lora.py")
    (folder / "kernel-metadata.json").write_text(
        json.dumps(KERNEL_METADATA, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"Đẩy kernel {KERNEL_ID} (GPU, internet bật, dữ liệu {DATASET_ID})...")
    kaggle("kernels", "push", "-p", ".", cwd=folder)
    print("\nXem tiến trình: python scripts/kaggle_push.py --status")


def status() -> None:
    kaggle("kernels", "status", KERNEL_ID)


def fetch() -> None:
    output = WORK_DIR / "output"
    output.mkdir(parents=True, exist_ok=True)
    kaggle("kernels", "output", KERNEL_ID, "-p", ".", cwd=output)
    metrics = output / "metrics.json"
    if metrics.exists():
        data = json.loads(metrics.read_text(encoding="utf-8"))
        before, after = data["before"], data["after"]
        print(f"\nmacro-F1 {before['macro_f1']:.3f} → {after['macro_f1']:.3f}")
        print(f"accuracy {before['accuracy']:.3f} → {after['accuracy']:.3f}")
        print(f"bịa mã   {before['invalid_rate']:.1%} → {after['invalid_rate']:.1%}")
    else:
        print(f"Chưa có metrics.json trong {output} — kernel có thể còn đang chạy.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--fetch", action="store_true")
    args = parser.parse_args()

    _force_ipv4()
    if args.status:
        status()
    elif args.fetch:
        fetch()
    else:
        push()


if __name__ == "__main__":
    main()
