"""Fine-tune QLoRA cho bộ phân loại mã lỗi — chạy trên Colab/Kaggle (cần GPU).

    python scripts/train_lora_error_classifier.py --base Qwen/Qwen2.5-1.5B-Instruct
    python scripts/train_lora_error_classifier.py --base Qwen/Qwen2.5-3B-Instruct --epochs 2

Máy cá nhân không có GPU nên script này KHÔNG chạy trong bộ test; nó được viết để
copy lên Colab/Kaggle cùng thư mục ``data/sft/``. Phần đo kết quả dùng chung code
với baseline prompting (``scripts/exp3_error_classification.py``) để hai con số so
được với nhau.

Kỷ luật huấn luyện trên máy miễn phí (Colab hay ngắt phiên giữa chừng):

- ``save_steps`` ngắn và ``--resume`` tự tìm checkpoint mới nhất;
- ``--max-samples`` để chạy thử 5 phút trước khi chạy thật;
- seed cố định, ghi lại toàn bộ cấu hình vào thư mục đầu ra.

Vì sao QLoRA chứ không fine-tune đầy đủ: T4 16GB không chứa nổi model 3B ở fp16
cho huấn luyện. Nạp 4-bit rồi chỉ học các ma trận LoRA hạng 16 thì vừa, và đây
cũng chính là cấu hình mà một trường đại học Việt Nam có thể chạy lại được.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

DEFAULT_BASE = "Qwen/Qwen2.5-1.5B-Instruct"
SFT_DIR = Path("data/sft")


def build_text(example: dict, tokenizer) -> str:
    """Một mẫu huấn luyện = prompt + mã lỗi, theo đúng khuôn chat của model."""
    messages = [
        {"role": "user", "content": example["prompt"]},
        {"role": "assistant", "content": example["completion"]},
    ]
    return tokenizer.apply_chat_template(messages, tokenize=False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", default=DEFAULT_BASE)
    parser.add_argument("--out", default="models/lora-error-classifier")
    parser.add_argument("--epochs", type=float, default=3.0)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--accumulate", type=int, default=8, help="gradient accumulation")
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--rank", type=int, default=16)
    parser.add_argument("--max-length", type=int, default=1024)
    parser.add_argument("--max-samples", type=int, default=0, help="0 = dùng hết")
    parser.add_argument("--seed", type=int, default=20260923)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    # Nhập muộn: máy phát triển không cài transformers/peft, mà script này chỉ
    # chạy trên Colab. Nhập ở đầu file sẽ làm cả repo không import được.
    import torch
    from datasets import Dataset
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        BitsAndBytesConfig,
        DataCollatorForLanguageModeling,
        Trainer,
        TrainingArguments,
        set_seed,
    )

    set_seed(args.seed)
    output = Path(args.out)
    output.mkdir(parents=True, exist_ok=True)

    tokenizer = AutoTokenizer.from_pretrained(args.base, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    def load(split: str) -> Dataset:
        rows = [json.loads(line) for line in (SFT_DIR / f"{split}.jsonl").open(encoding="utf-8")]
        if args.max_samples and split == "train":
            rows = rows[: args.max_samples]
        data = Dataset.from_list([{"text": build_text(row, tokenizer)} for row in rows])
        return data.map(
            lambda batch: tokenizer(batch["text"], truncation=True, max_length=args.max_length),
            batched=True, remove_columns=["text"],
        )

    train, validation = load("train"), load("validation")
    print(f"train {len(train)} mẫu | validation {len(validation)} mẫu")

    quantisation = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
    )
    model = AutoModelForCausalLM.from_pretrained(
        args.base, quantization_config=quantisation, device_map="auto", trust_remote_code=True,
    )
    model = prepare_model_for_kbit_training(model)
    model = get_peft_model(model, LoraConfig(
        r=args.rank,
        lora_alpha=args.rank * 2,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        # Bám vào cả attention lẫn MLP: chỉ gắn vào q/v cho kết quả kém hơn rõ
        # với model nhỏ, mà chi phí thêm không đáng kể.
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
    ))
    model.print_trainable_parameters()

    trainer = Trainer(
        model=model,
        args=TrainingArguments(
            output_dir=str(output),
            num_train_epochs=args.epochs,
            per_device_train_batch_size=args.batch_size,
            gradient_accumulation_steps=args.accumulate,
            learning_rate=args.learning_rate,
            lr_scheduler_type="cosine",
            warmup_ratio=0.03,
            logging_steps=10,
            eval_strategy="steps",
            eval_steps=100,
            save_steps=100,              # ngắn: Colab ngắt phiên bất ngờ
            save_total_limit=2,
            fp16=True,
            gradient_checkpointing=True,
            report_to=[],
            seed=args.seed,
        ),
        train_dataset=train,
        eval_dataset=validation,
        data_collator=DataCollatorForLanguageModeling(tokenizer, mlm=False),
    )

    trainer.train(resume_from_checkpoint=args.resume or None)
    trainer.save_model(str(output))
    tokenizer.save_pretrained(str(output))
    (output / "run.json").write_text(json.dumps(vars(args), ensure_ascii=False, indent=1),
                                     encoding="utf-8")
    print(f"\nĐã lưu adapter vào {output}")
    print("Đo kết quả: python scripts/exp3_error_classification.py --limit 300 "
          "(sau khi phục vụ adapter qua vLLM hoặc Ollama)")


if __name__ == "__main__":
    main()
