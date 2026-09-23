"""Huấn luyện QLoRA phân loại mã lỗi — chạy trên Kaggle GPU (kernel script).

Đẩy lên bằng ``python scripts/kaggle_push.py``. File này chạy TRONG kernel Kaggle,
không chạy ở máy cá nhân (không có GPU, không có bitsandbytes trên Windows).

Kernel làm ba việc, theo đúng thứ tự đó:

1. **Đo model gốc trước khi học** trên cùng tập test — nếu không có số này thì
   không biết LoRA thêm được bao nhiêu, hay chỉ là model vốn đã biết.
2. Huấn luyện QLoRA 4-bit.
3. Đo lại trên CHÍNH tập test đó, bằng CHÍNH cách bóc mã và cách tính macro-F1 mà
   baseline ở máy dùng — có vậy hai con số mới so được với nhau.

Chi tiết quan trọng: **loss chỉ tính trên phần đáp án**, không tính trên prompt.
Prompt ở đây dài gần 900 token (có cả danh sách mã lỗi) còn đáp án chỉ vài token;
để loss trải đều thì model dành gần hết sức học cách chép lại đề bài.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path


def _install_dependencies() -> None:
    """Cài bitsandbytes và peft ngay trong kernel.

    Ảnh Kaggle có sẵn torch và transformers nhưng KHÔNG có bitsandbytes bản đủ
    mới (transformers đòi >= 0.46.1 cho 4-bit), và peft thì tuỳ ảnh. Cài ở đây
    để kernel tự chạy được, không phải sửa tay trên giao diện.
    """
    packages = ["bitsandbytes>=0.46.1", "peft>=0.11", "accelerate>=0.30"]
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-U", *packages], check=False)


_install_dependencies()

import torch
from torch.utils.data import Dataset as TorchDataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    Trainer,
    TrainingArguments,
    set_seed,
)

BASE_MODEL = os.environ.get("BASE_MODEL", "Qwen/Qwen2.5-1.5B-Instruct")


def _find_data_dir() -> Path:
    """Tìm thư mục dữ liệu trong /kaggle/input.

    Không viết cứng đường dẫn: lần chạy đầu tiên đã hỏng vì kernel khởi động khi
    dataset còn đang xử lý, và thư mục mount chưa tồn tại. Dò theo file thì thông
    báo lỗi cũng nói rõ có những gì trong /kaggle/input.
    """
    root = Path("/kaggle/input")
    # Tìm đệ quy: Kaggle không phải lúc nào cũng mount thẳng vào
    # /kaggle/input/<slug>; lần chạy trước nó nằm dưới /kaggle/input/datasets/...
    for found in sorted(root.rglob("train.jsonl")):
        return found.parent
    available = [str(path.relative_to(root)) for path in root.rglob("*")][:20] if root.exists() else []
    raise FileNotFoundError(
        f"Không thấy train.jsonl trong /kaggle/input (có: {available}). "
        "Dataset có thể chưa xử lý xong — đợi rồi chạy lại kernel."
    )


DATA_DIR = _find_data_dir()
OUTPUT_DIR = Path("/kaggle/working")
MAX_LENGTH = 1152          # p95 của prompt ≈ 880 token, chừa chỗ cho đáp án
EVAL_SAMPLES = 300
EPOCHS = float(os.environ.get("EPOCHS", 3))
SEED = 20260923

CODE_PATTERN = re.compile(r"\b[A-Z]{2,4}(?:\.[A-Z0-9_]+)+\b")


def load_jsonl(name: str) -> list[dict]:
    return [json.loads(line) for line in (DATA_DIR / f"{name}.jsonl").open(encoding="utf-8")]


# --------------------------------------------------------------------------
# Chỉ số — cài lại y hệt scripts/exp3_error_classification.py để so được
# --------------------------------------------------------------------------

def extract_code(text: str, valid: set[str]) -> str | None:
    for candidate in CODE_PATTERN.findall(text.upper()):
        if candidate in valid:
            return candidate
    return None


def macro_f1(pairs: list[tuple[str, str | None]]) -> tuple[float, dict[str, float]]:
    true_positive: dict[str, int] = defaultdict(int)
    predicted: dict[str, int] = defaultdict(int)
    actual: dict[str, int] = defaultdict(int)
    for truth, guess in pairs:
        actual[truth] += 1
        if guess is not None:
            predicted[guess] += 1
            if guess == truth:
                true_positive[truth] += 1

    per_class = {}
    for code in actual:
        precision = true_positive[code] / predicted[code] if predicted[code] else 0.0
        recall = true_positive[code] / actual[code]
        per_class[code] = (2 * precision * recall / (precision + recall)
                           if precision + recall else 0.0)
    return (sum(per_class.values()) / len(per_class) if per_class else 0.0), per_class


# --------------------------------------------------------------------------
# Dữ liệu
# --------------------------------------------------------------------------

class CodeDataset(TorchDataset):
    """Prompt bị che khỏi loss; chỉ phần mã lỗi mới có nhãn."""

    def __init__(self, rows: list[dict], tokenizer) -> None:
        self.samples = []
        for row in rows:
            prompt = tokenizer.apply_chat_template(
                [{"role": "user", "content": row["prompt"]}],
                tokenize=False, add_generation_prompt=True,
            )
            prompt_ids = tokenizer(prompt, add_special_tokens=False)["input_ids"]
            answer_ids = tokenizer(row["completion"] + tokenizer.eos_token,
                                   add_special_tokens=False)["input_ids"]
            # Cắt từ ĐẦU prompt nếu quá dài, để phần đáp án ở cuối luôn còn nguyên.
            budget = MAX_LENGTH - len(answer_ids)
            prompt_ids = prompt_ids[-budget:]
            self.samples.append({
                "input_ids": prompt_ids + answer_ids,
                "labels": [-100] * len(prompt_ids) + answer_ids,
            })

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int) -> dict:
        return self.samples[index]


def collate(batch: list[dict], pad_id: int) -> dict:
    width = max(len(row["input_ids"]) for row in batch)
    input_ids, labels, attention = [], [], []
    for row in batch:
        padding = width - len(row["input_ids"])
        input_ids.append(row["input_ids"] + [pad_id] * padding)
        labels.append(row["labels"] + [-100] * padding)
        attention.append([1] * len(row["input_ids"]) + [0] * padding)
    return {
        "input_ids": torch.tensor(input_ids),
        "labels": torch.tensor(labels),
        "attention_mask": torch.tensor(attention),
    }


# --------------------------------------------------------------------------
# Đo
# --------------------------------------------------------------------------

@torch.no_grad()
def evaluate(model, tokenizer, rows: list[dict], valid: set[str], tiers: dict[str, str],
             batch_size: int = 8) -> dict:
    model.eval()
    pairs: list[tuple[str, str | None]] = []
    started = time.time()

    for start in range(0, len(rows), batch_size):
        chunk = rows[start:start + batch_size]
        prompts = [
            tokenizer.apply_chat_template([{"role": "user", "content": row["prompt"]}],
                                          tokenize=False, add_generation_prompt=True)
            for row in chunk
        ]
        encoded = tokenizer(prompts, return_tensors="pt", padding=True, truncation=True,
                            max_length=MAX_LENGTH, add_special_tokens=False).to(model.device)
        generated = model.generate(**encoded, max_new_tokens=20, do_sample=False,
                                   pad_token_id=tokenizer.pad_token_id)
        for row, sequence in zip(chunk, generated):
            text = tokenizer.decode(sequence[encoded["input_ids"].shape[1]:],
                                    skip_special_tokens=True)
            pairs.append((row["completion"], extract_code(text, valid)))
        if (start // batch_size) % 5 == 0:
            print(f"    đã đo {len(pairs)}/{len(rows)} ({time.time() - started:.0f}s)", flush=True)

    score, per_class = macro_f1(pairs)
    accuracy = sum(1 for truth, guess in pairs if truth == guess) / len(pairs)
    invalid = sum(1 for _, guess in pairs if guess is None) / len(pairs)
    tier_hit = sum(1 for truth, guess in pairs
                   if guess is not None and tiers.get(guess) == tiers.get(truth)) / len(pairs)
    return {"macro_f1": score, "accuracy": accuracy, "tier_accuracy": tier_hit,
            "invalid_rate": invalid, "n": len(pairs), "per_class_f1": per_class,
            "seconds": time.time() - started}


def main() -> None:
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

    set_seed(SEED)
    print(f"GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'KHÔNG CÓ'}")

    train_rows = load_jsonl("train")
    validation_rows = load_jsonl("validation")
    test_rows = load_jsonl("test")[:EVAL_SAMPLES]
    codes = json.loads((DATA_DIR / "codes.json").read_text(encoding="utf-8"))
    valid = set(codes)
    tiers = {code: entry["tier"] for code, entry in codes.items()}
    print(f"train {len(train_rows)} | validation {len(validation_rows)} | test {len(test_rows)}")

    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "left"          # cần cho generate theo lô

    quantisation = BitsAndBytesConfig(
        load_in_4bit=True, bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16, bnb_4bit_use_double_quant=True,
    )
    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL, quantization_config=quantisation, device_map="auto", trust_remote_code=True,
    )

    print("\n=== Đo model GỐC (chưa học) ===", flush=True)
    before = evaluate(model, tokenizer, test_rows, valid, tiers)
    print(f"  macro-F1 {before['macro_f1']:.3f} | accuracy {before['accuracy']:.3f} "
          f"| bịa mã {before['invalid_rate']:.1%}")

    print("\n=== Huấn luyện QLoRA ===", flush=True)
    model = prepare_model_for_kbit_training(model)
    model = get_peft_model(model, LoraConfig(
        r=16, lora_alpha=32, lora_dropout=0.05, bias="none", task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
    ))
    model.print_trainable_parameters()
    model.config.use_cache = False

    tokenizer.padding_side = "right"         # huấn luyện thì đệm bên phải
    trainer = Trainer(
        model=model,
        args=TrainingArguments(
            output_dir=str(OUTPUT_DIR / "checkpoints"),
            num_train_epochs=EPOCHS,
            per_device_train_batch_size=2,
            gradient_accumulation_steps=8,
            learning_rate=2e-4,
            lr_scheduler_type="cosine",
            warmup_ratio=0.03,
            logging_steps=20,
            eval_strategy="epoch",
            save_strategy="epoch",
            save_total_limit=1,
            fp16=True,
            gradient_checkpointing=True,
            report_to=[],
            seed=SEED,
        ),
        train_dataset=CodeDataset(train_rows, tokenizer),
        eval_dataset=CodeDataset(validation_rows[:200], tokenizer),
        data_collator=lambda batch: collate(batch, tokenizer.pad_token_id),
    )
    history = trainer.train()

    model.config.use_cache = True
    tokenizer.padding_side = "left"
    print("\n=== Đo lại SAU khi học ===", flush=True)
    after = evaluate(model, tokenizer, test_rows, valid, tiers)
    print(f"  macro-F1 {after['macro_f1']:.3f} | accuracy {after['accuracy']:.3f} "
          f"| bịa mã {after['invalid_rate']:.1%}")

    model.save_pretrained(str(OUTPUT_DIR / "adapter"))
    tokenizer.save_pretrained(str(OUTPUT_DIR / "adapter"))
    (OUTPUT_DIR / "metrics.json").write_text(json.dumps({
        "base_model": BASE_MODEL, "epochs": EPOCHS, "seed": SEED,
        "train_size": len(train_rows), "eval_size": len(test_rows),
        "before": before, "after": after,
        "train_loss": history.metrics.get("train_loss"),
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\nKẾT QUẢ: macro-F1 {before['macro_f1']:.3f} → {after['macro_f1']:.3f} "
          f"| accuracy {before['accuracy']:.3f} → {after['accuracy']:.3f}")


if __name__ == "__main__":
    main()
