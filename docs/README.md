# Tài liệu

Mỗi file viết cho **một người đọc cụ thể**. Chọn đúng cái bạn cần để đỡ mất thời gian.

## Bắt đầu từ đâu

| Bạn là | Đọc |
|---|---|
| **Dùng** hệ thống — sinh viên, giảng viên | [huong-dan-su-dung.md](huong-dan-su-dung.md) |
| **Demo** hệ thống trên máy khác | [cho-nguoi-demo.md](cho-nguoi-demo.md) |
| **Dựng lại** toàn bộ từ đầu | [huong-dan-cai-dat.md](huong-dan-cai-dat.md) |
| **Đọc và sửa code** | [kien-truc.md](kien-truc.md) |

## Hướng dẫn

| File | Nội dung |
|---|---|
| [huong-dan-su-dung.md](huong-dan-su-dung.md) | Luyện tập, thang gợi ý, tiến độ, chọn phạm vi, hỏi lý thuyết, bot Telegram, trang quản trị |
| [cho-nguoi-demo.md](cho-nguoi-demo.md) | Dựng máy để demo trong ~20 phút. **`git pull` một mình không đủ** — 284 MB dữ liệu cố ý không nằm trong git |
| [huong-dan-cai-dat.md](huong-dan-cai-dat.md) | Cài từ đầu, dựng kho giáo trình, dựng ngân hàng đề, huấn luyện DKT và LoRA, bảng xử lý sự cố |
| [running.md](running.md) | Tham chiếu nhanh: lệnh, biến môi trường, endpoint |
| [kien-truc.md](kien-truc.md) | Bản đồ mã nguồn, luồng một lượt làm bài, cách thêm môn / mã lỗi / dạng bài, những chỗ dễ sập |

## Đánh giá và báo cáo

| File | Nội dung |
|---|---|
| [evaluation-protocol.md](evaluation-protocol.md) | Cách đo từng thí nghiệm, kết quả, và **hạn chế của từng phép đo** |
| [results.md](results.md) | Bảng kết quả — **sinh tự động**, đừng sửa tay |
| [report-outline.md](report-outline.md) | Khung 8 chương của báo cáo |
| [report-draft.md](report-draft.md) | Bản thảo báo cáo |
| [demo-script.md](demo-script.md) | Kịch bản video demo, 8 cảnh, kèm câu trả lời cho 5 câu hội đồng hay hỏi |

## Dữ liệu và việc còn phải làm

| File | Nội dung |
|---|---|
| [nguon-tai-lieu.md](nguon-tai-lieu.md) | Nguồn và **giấy phép** của mọi tài liệu trong kho tri thức |
| [viec-can-lam.md](viec-can-lam.md) | Việc cần người thật làm, kèm sẵn tin nhắn và hướng dẫn để gửi đi |

---

## Ba điều đọc trước khi sửa code

Chi tiết ở [kien-truc.md](kien-truc.md), nhưng nhắc lại vì phần lớn quyết định thiết kế
là hệ quả của chúng:

1. **Không kiểm chứng được thì im lặng, không kết tội.** `final_answer_correct` có ba
   giá trị, và `None` không được cập nhật mô hình năng lực.
2. **Tầng gợi ý chỉ đọc `VerificationResult`**, không đọc lại đầu ra thô của LLM.
3. **Đáp án không rời khỏi server** trước khi sinh viên được phép thấy — đó là lý do có
   lớp `PublicItem`.
