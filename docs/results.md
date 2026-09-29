# Bảng kết quả

*Sinh tự động bằng `python scripts/make_report_tables.py`, ngày 2026-09-29.*
*Đừng sửa tay file này — sửa ở `experiments/` rồi chạy lại script.*

## EXP-1 — mô hình tự giải toán (chấm bằng verifier)

| Model | Chế độ | MAE101 | MAI391 | MAS291 | MAD101 | Tổng |
|---|---|---|---|---|---|---|
| qwen2.5:3b-instruct | suy luận từng bước | 50% | 33% | 50% | 33% | **41,7%** |
| qwen2.5:3b-instruct | hỏi thẳng | 25% | 0% | 25% | 42% | **22,9%** |
| qwen2.5:7b-instruct | hỏi thẳng | 58% | 25% | 33% | 58% | **43,8%** |

## EXP-2b — chỉ đúng bước sai đầu tiên

| Chỉ số | Kết quả |
|---|---|
| Phát hiện có chỗ sai trong chuỗi bước | 301/301 = 100,0% |
| Chỉ **đúng** bước đã bị cài lỗi | 301/301 = 100,0% |
| Báo oan trên lời giải mẫu (đúng) | 0,0% trên 301 lời giải |

*Chỉ phủ 2 mã lỗi mức bước: LA.ROWOP.INVALID, MAE.ALG.STEP — xem phần hạn chế trong `docs/evaluation-protocol.md`.*

## EXP-3 — phân loại mã lỗi

| Cấu hình | macro-F1 | accuracy | đúng tầng lỗi | bịa mã |
|---|---|---|---|---|
| qwen2.5:3b-instruct few-shot 6 | 0,343 | 35,3% | 49,3% | 0,0% |
| qwen2.5:3b-instruct zero-shot | 0,358 | 38,0% | 48,7% | 1,3% |
| qwen2.5:7b-instruct zero-shot | 0,415 | 46,7% | 63,3% | 2,7% |
| Qwen2.5-1.5B-Instruct (base) | 0,098 | 15,7% | 29,3% | 16,0% |
| Qwen2.5-1.5B-Instruct (**+ LoRA**) | 0,921 | 95,0% | 97,3% | 0,0% |

## EXP-4 — truy xuất giáo trình (Recall@5)

| Ngôn ngữ câu hỏi | BM25 | dense | hybrid |
|---|---|---|---|
| tiếng Việt | 0,167 | 0,595 | 0,310 |
| tiếng Anh | 0,929 | 0,833 | 0,976 |

## EXP-5 — mô hình theo dõi năng lực

| Mô hình | **ASSISTments** (người thật) | MAD101 (mô phỏng) | MAE101 (mô phỏng) |
|---|---|---|---|
| majority | 0,500 | 0,500 | 0,500 |
| BKT | 0,729 | 0,551 | 0,639 |
| **DKT** | 0,849 | 0,706 | 0,852 |
| SAKT | 0,792 | 0,681 | 0,776 |

## EXP-6 — chiến lược chọn bài (6 chương, 4 môn)

| Chương | tuần tự | ZPD | ZPD + phủ kỹ năng |
|---|---|---|---|
| | *đúng / kỹ năng thạo* | | |
| MAD101 · MAD.COUNT | 78% / 2.8 | 79% / 2.2 | 78% / 3.0 |
| MAD101 · MAD.GRAPH | 72% / 3.6 | 76% / 1.2 | 69% / 2.8 |
| MAE101 · MAE.INT | 65% / 4.9 | 70% / 4.0 | 57% / 4.7 |
| MAE101 · MAE.LA | 69% / 3.5 | 70% / 1.9 | 68% / 2.9 |
| MAI391 · MAI.DEC | 71% / 2.1 | 76% / 1.0 | 64% / 3.0 |
| MAS291 · MAS.DIST | 78% / 2.8 | 77% / 2.5 | 76% / 3.9 |

## EXP-7a — bỏ tầng kiểm chứng ký hiệu

| Bộ chấm | Chính xác | Báo ĐÚNG cho bài SAI | Báo SAI cho bài ĐÚNG |
|---|---|---|---|
| qwen2.5:3b-instruct làm giám khảo | 50,0% | 35,0% | 65,0% |
| **Kiểm chứng ký hiệu** | **100,0%** | **0,0%** | **0,0%** |

## EXP-7b — bỏ RAG khỏi prompt sinh gợi ý

| Cấu hình | Lộ đáp án | Về template | Lượt TB | Độ dài | Bám giáo trình |
|---|---|---|---|---|---|
| có RAG | 0,0% | 1,2% | 1.09 | 125 | 7,5% |
| không RAG | 0,0% | 2,5% | 1.10 | 105 | 7,5% |

## EXP-8 — chống lộ đáp án

| Model | Cấu hình | Lộ đáp án | Về template | Lượt TB |
|---|---|---|---|---|
| qwen2.5:3b-instruct | không guardrail, prompt không có đáp án | 6,2% | 0,0% | 1.00 |
| qwen2.5:3b-instruct | không guardrail, prompt CÓ đáp án | 8,3% | 0,0% | 1.00 |
| qwen2.5:3b-instruct | hệ thống thật (guardrail + viết lại) | 0,0% | 1,0% | 1.09 |
| qwen2.5:3b-instruct | guardrail, prompt CÓ đáp án | 0,0% | 2,1% | 1.10 |
| qwen2.5:7b-instruct | không guardrail, prompt không có đáp án | 5,0% | 0,0% | 1.00 |
| qwen2.5:7b-instruct | không guardrail, prompt CÓ đáp án | 7,5% | 0,0% | 1.00 |
| qwen2.5:7b-instruct | hệ thống thật (guardrail + viết lại) | 0,0% | 2,5% | 1.10 |
| qwen2.5:7b-instruct | guardrail, prompt CÓ đáp án | 0,0% | 1,2% | 1.10 |
