# Dữ liệu bài tập và lời giải từng bước

Viết cho người **mở rộng dữ liệu**: thêm dạng bài, tăng số đề, nạp đề thi thật, hoặc
dùng mô hình AI mạnh để làm nhanh hơn. Đọc [kien-truc.md](kien-truc.md) trước nếu chưa
quen mã nguồn.

## Nguyên tắc: máy tính ra số, AI chỉ được đề xuất

Mọi con số trong đề, đáp án và lời giải do **SymPy / NumPy / networkx** tính, rồi được
**bộ chấm** xác nhận lại. Mô hình ngôn ngữ, kể cả mô hình rất mạnh, chỉ được *đề xuất*
(một dạng bài mới, cách diễn đạt, tham số đọc từ đề thi). Đề xuất nào không qua bộ chấm
thì bị loại, không có ngoại lệ.

Lý do: một mô hình viết lời giải trôi chảy nhưng sai một hệ số là kiểu lỗi người học
không có cách nào tự phát hiện. Chốt kiểm bằng máy đã bắt được những lỗi như vậy ngay
trong dữ liệu của chính dự án. Ví dụ: 17 đề giới hạn từng có đáp án sai, và sinh viên trả
lời đúng thì bị chấm sai.

## Quy trình một đề đi qua

```
template (src/data_gen/*_items.py)   gieo tham số ngẫu nhiên → meta của đề
        ↓
bộ chấm (src/verify/)                đáp án phải tự chấm được, không thì loại đề
        ↓
bộ giải (src/solve/)                 tính Bước 1..n từ meta: việc cần làm, công thức,
        ↓                            phép tính có số, kết quả
chốt kiểm (solve())                  bước cuối phải được bộ chấm nhận là đúng đáp án,
                                     không thì lời giải không bao giờ hiện cho người học
```

Mỗi bước (`src/solve/base.py`) có bốn phần, tách riêng vì từng mức gợi ý dùng một phần
khác nhau:

| Phần | Ví dụ | Mức gợi ý được dùng |
|---|---|---|
| `action`: làm gì | "Tính sai số chuẩn" | từ mức 0 (không có số) |
| `formula`: công thức | "SE = s / √n" | từ mức 1 (không có số) |
| `work`: thay số | "SE = 4 / √16" | từ mức 3, qua bộ chặn lộ đáp án từng dòng |
| `result`: kết quả | "SE = 1" | từ mức 3; kết quả bước cuối chỉ hiện ở mức 5 |

## Các lệnh

```bash
# Rà toàn bộ ngân hàng: dạng nào chưa có hàm giải, lời giải nào hỏng
python scripts/audit_solutions.py
python scripts/audit_solutions.py MAS291 --show 3      # in mẫu lời giải

# Xuất tập lời giải chuẩn hoá đã kiểm (JSONL): đề, kiến thức, công thức, các bước, đáp án
python scripts/audit_solutions.py --export data/sft/solutions_verified.jsonl

# Tăng số đề: cùng template, đổi số lượng (seed cố định nên tái lập được)
python scripts/build_bank.py MAS291 5000
python scripts/build_error_dataset.py MAS291            # tập bài làm sai có nhãn tương ứng
```

Hiện tại: **4.955/4.955 đề** của 4 môn có lời giải qua chốt kiểm. Số đề không bị giới
hạn bởi công sức: mỗi template sinh được hàng nghìn biến thể. Giới hạn thật là **số dạng
bài**: hiện có 102 template trên 4 môn, giải bằng 70 hàm giải.

## Thêm một dạng bài mới

1. **Template** trong `src/data_gen/<môn>_items.py`: gieo tham số, ghi vào `meta` (có
   `task`), đặt kỹ năng đúng chương trình môn (đối chiếu `data/skills/<môn>.json`).
2. **Bộ chấm**: nếu `task` mới chưa có cách chấm thì thêm vào `src/verify/<mảng>.py`.
   Bộ chấm phải **tự tính lại** đáp án từ `meta`, không chỉ so với đáp án đã lưu. Đây là
   chỗ để lọt lỗi giới hạn nói ở trên.
3. **Hàm giải**: `@solver("<task>")` trong `src/solve/<mảng>.py`, trả `Solution` với
   `theory`, `formula`, các `Step` và `answer` ở dạng nộp được.
4. Dựng lại ngân hàng, chạy `audit_solutions.py` (phải 100%), chạy `pytest`.
   `tests/test_solve.py` tự bắt dạng bài mới chưa có hàm giải.

## Dùng AI mạnh ở đâu cho đúng

| Việc | AI làm | Máy kiểm |
|---|---|---|
| **Nạp đề thi / bài tập thật** | đọc đề (PDF, ảnh), trích ra `task` + tham số dạng `meta` | bộ chấm tính lại đáp án; lệch với đáp án in trong đề thì đưa người xem |
| **Viết template / hàm giải mới** | đề xuất mã theo khuôn có sẵn | `audit_solutions.py` phải 100%, `pytest` phải xanh, người duyệt diff |
| **Diễn đạt lời giải tự nhiên hơn** | viết lại `action`/`theory` | không được đụng `work`/`result`; diff phải chỉ là chữ |
| **Phân tích lỗi của sinh viên thật** | đề xuất mã lỗi cho bài sai | người gán nhãn quyết định (`scripts/label_real_errors.py`) |

Không dùng AI để **tự tính** đáp án hay các bước có số rồi lưu thẳng vào dữ liệu.

## Giới hạn

- Lời giải là của **dạng bài**, không phải của **bài làm**. Hệ thống biết lời giải
  chuẩn từng bước, nhưng chỉ chỉ ra được bước sai *trong bài làm của sinh viên* khi sinh
  viên nộp kèm các bước (MAE101 phần giải tích và hệ phương trình).
- Đề chép tay không có `meta` đủ tham số thì không giải được tự động. Hiện tất cả đề đều
  có đủ; đề nạp mới phải theo khuôn `meta`.
