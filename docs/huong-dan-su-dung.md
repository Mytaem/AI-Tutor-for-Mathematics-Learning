# Hướng dẫn sử dụng

Tài liệu này viết cho **người dùng hệ thống**: sinh viên luyện tập và giảng viên theo
dõi lớp. Không cần biết lập trình.

Cần dựng máy để chạy thì xem [huong-dan-cai-dat.md](huong-dan-cai-dat.md).

---

## Phần A — Dành cho sinh viên

### A1. Vào hệ thống

Mở **http://localhost:3000** (hoặc địa chỉ giảng viên cho).

Trang đầu có hai bước:

1. **Chọn môn** — bấm vào một trong bốn thẻ. Mỗi thẻ ghi số đề và số kỹ năng thật của
   môn đó.

   | Mã môn | Tên | Nội dung |
   |---|---|---|
   | MAE101 | Toán cho kỹ thuật | Giới hạn · Đạo hàm · Tích phân · Đại số tuyến tính |
   | MAD101 | Toán rời rạc | Logic · Tổ hợp · Truy hồi · Đồ thị |
   | MAI391 | Toán cho học máy | Ma trận · Trị riêng · Chéo hoá · Chuẩn vector |
   | MAS291 | Xác suất và thống kê | Xác suất · Phân phối · Ước lượng · Kiểm định |

2. **Nhập tên hoặc mã sinh viên** — ví dụ `SE170001`.

   Không cần mật khẩu. Chuỗi này chỉ để nối các lượt làm bài của **cùng một người** lại
   với nhau; nhờ vậy hệ thống mới theo dõi được em tiến bộ tới đâu. **Dùng đúng một
   chuỗi cho mọi buổi học** — đổi chuỗi là mất hết tiến độ cũ.

Bấm **Vào luyện tập**.

> **Buổi đầu sẽ có vài câu đo đầu vào.** Hệ thống cố ý chọn những câu *cho nhiều thông
> tin nhất* về trình độ, không phải câu vừa sức nhất — nên đừng lo nếu thấy khó hoặc
> dễ bất thường ở mấy câu đầu.

### A2. Luyện tập

Màn hình chia hai phần: **đề bài và ô nhập ở bên trái**, **bảng điều khiển ở bên phải**.

Thẻ đề bài ghi rõ ba thứ: **Mã đề**, **Độ khó** (dễ / vừa / khó), và **Kỹ năng** mà bài
này rèn.

#### Nhập đáp án

Ô nhập có dòng gợi ý định dạng ngay bên dưới. Hệ thống chấp nhận nhiều cách viết:

| Dạng đề | Viết thế nào |
|---|---|
| Nguyên hàm | `x**3/3 + C` — nhớ `+ C` |
| Biểu thức | `2*x + 1`, viết `x**2` cho x², `sqrt(x)` cho √x |
| Một con số | `0.75` **hoặc** `0,75` — dấu phẩy kiểu Việt Nam cũng được |
| Phân số | `3/4` |
| Nghiệm hệ | `[2, 1]` **hoặc** `x = 2, y = 1` |
| Ma trận | `[[1, 2], [3, 4]]` |
| Vector | `[1, 2]` |
| Tập hợp | `[1, 3]`, `{1, 3}`, `1, 3`, `1,3` — cách nào cũng được |
| Đúng/sai | trả lời bằng lời |
| Vô nghiệm | `vô nghiệm`, `Vô nghiệm`, `hệ vô nghiệm` đều được |

Mấy điều đáng biết:

- **Viết hoa chữ cái của hàm cũng được**: `Log(x)`, `SIN(x)` đều hiểu.
- **Dấu chấm cuối câu không sao**: `x**3/3 + C.` vẫn được chấm.
- Nhưng **chữ hoa ở TÊN BIẾN thì khác nghĩa**: `X` và `x` là hai biến khác nhau, nên
  đừng viết `X**2` khi đề dùng `x`.

Gõ xong nhấn **Enter** hoặc bấm **Nộp bài**.

#### Trình bày từng bước (nên dùng)

Bấm **"+ Trình bày từng bước"** rồi gõ mỗi dòng một bước.

Việc này đáng làm: có bước thì hệ thống chỉ được **bước sai đầu tiên** của em, thay vì
chỉ nói "đáp án chưa đúng". Ví dụ:

```
u = x**2 + 1
du = 2*x dx
```

#### Ba kết quả có thể nhận được

| Kết quả | Nghĩa là gì |
|---|---|
| ✓ **Đúng rồi** | bài làm đúng, bấm **Bài tiếp theo** |
| ✕ **Chưa đúng** | sai thật — đọc lời nhắn rồi thử lại, hoặc xin gợi ý |
| ? **Chưa đọc được đáp án** | **không phải em sai** — chỉ là viết sai định dạng. Mức thành thạo **giữ nguyên**. Đọc dòng gợi ý định dạng rồi gõ lại |

Phân biệt ba trạng thái này là cố ý: lỗi gõ phím không phải lỗ hổng kiến thức, nên hệ
thống không trừ điểm năng lực vì chuyện đó.

### A3. Xin gợi ý — thang 6 mức

Bấm **Xin gợi ý**. Mỗi lần bấm thêm thì gợi ý rõ hơn một bậc. Thanh 5 vạch ở đầu khối
gợi ý cho biết em đang ở mức nào.

| Mức | Tên | Hệ thống nói gì |
|---|---|---|
| 0 | Khơi gợi | hỏi lại để em tự nhìn ra đề cho gì, hỏi gì |
| 1 | Nhắc khái niệm | nhắc định nghĩa hoặc công thức liên quan |
| 2 | Cảnh báo bẫy | cảnh báo đúng cái bẫy ứng với loại lỗi em đang mắc |
| 3 | Chỉ bước sai | nói bước nào sai, **chưa nói sai thế nào** |
| 4 | Sửa và giải thích | sửa bước đó và giải thích vì sao sai |
| 5 | Lời giải đầy đủ | toàn bộ lời giải theo bước |

**Thang gợi ý DỪNG ở mức 4.** Bấm "Gợi ý thêm" bao nhiêu lần cũng không tự lên mức 5 —
muốn xem lời giải đầy đủ phải bấm **"Cho em xem lời giải đầy đủ"**, và phải bấm **hai
lần**. Đây không phải lỗi: hệ thống cố ý không đưa đáp án quá sớm, vì xem đáp án ngay
thì không học được gì.

Mỗi gợi ý có ghi **do mô hình diễn đạt** hay **mẫu có sẵn**. Cả hai đều đã qua bộ kiểm
tra tự động chặn lộ đáp án.

### A4. Xem tiến độ

Bấm **Tiến độ** ở cột phải.

Bốn ô số tổng quan: số lượt làm bài, tỉ lệ làm đúng, số kỹ năng đạt từ 60% trở lên, số
kỹ năng còn dưới 35%.

Bảng dưới liệt kê **toàn bộ kỹ năng của môn**, xếp từ yếu nhất lên, với bốn mức:

| Xếp loại | Mức thành thạo |
|---|---|
| còn yếu | dưới 35% |
| đang học | 35–60% |
| gần vững | 60–85% |
| đã vững | từ 85% |

> **Con số này KHÔNG phải điểm trung bình.** Nó do mô hình BKT ước lượng: làm đúng một
> bài dễ khi đang yếu thì tăng ít, làm đúng bài khó thì tăng nhiều. Làm đúng một bài
> còn kéo tăng cả các kỹ năng tiên quyết của nó.

Nhóm **"Nên luyện trước"** chỉ ra các kỹ năng dưới 35%. Nhưng để ý: **bộ chọn bài không
nhất thiết đưa ngay bài khó nhất trong nhóm đó** — nó chọn bài có xác suất làm đúng
quanh 75%, tức vừa đủ sức để học được chứ không phải để thất vọng.

### A5. Chọn phạm vi luyện tập

Ở cột phải, khối **Phạm vi luyện** có ba ô chọn, thu hẹp dần:

```
Chương  →  Bài  →  Dạng bài
```

Ví dụ: `Tổ hợp` → `Nguyên lý bù trừ` → `Đếm số chia hết`

Mỗi lựa chọn **hiện sẵn số đề**, và nhánh không có đề thì không bấm được — nên em không
bao giờ chọn vào chỗ trống.

Chọn xong là **đổi ngay sang đề của phạm vi đó**, không phải bấm thêm. Muốn luyện cả
môn thì bấm **Bỏ lọc**.

Dùng khi nào: ôn đúng chương sắp thi, hoặc luyện riêng một dạng bài đang vướng.

### A6. Hỏi lý thuyết

Bấm **Hỏi lý thuyết**. Gõ câu hỏi bằng tiếng Việt, ví dụ *"Chu trình Euler là gì?"*

Câu trả lời **luôn kèm nguồn**: tên file giáo trình, chương, số trang — để em tự kiểm
lại, không phải tin suông.

Có thể nhận **ba kiểu trả lời khác nhau**, và phân biệt được chúng là có ích:

| Kiểu | Khi nào | Nghĩa là gì |
|---|---|---|
| Trả lời kèm nguồn | câu hỏi trong giáo trình | dùng được, nhớ mở nguồn kiểm lại |
| **"Ngoài phạm vi"** | hỏi ngoài 4 môn | hệ thống không đoán bừa |
| **"Chưa có tài liệu chương này"** | câu hỏi đúng chương trình nhưng kho còn thiếu | **lỗi của hệ thống, không phải em hỏi sai** — hỏi thầy cô nhé |

Chọn chương ở cột phải thì câu hỏi chỉ tìm trong chương đó — hữu ích khi thuật ngữ dùng
chung giữa nhiều chương.

> **Một điều nên biết:** giáo trình phần lớn bằng tiếng Anh. Hệ thống tự dịch thuật ngữ
> trong câu hỏi sang tiếng Anh trước khi tìm, nên hỏi tiếng Việt vẫn tốt. Nhưng nếu một
> thuật ngữ lạ không tìm ra gì, thử gõ thẳng tên tiếng Anh của nó.

### A7. Dùng qua Telegram

Nếu giảng viên có bật bot, mở Telegram và tìm tên bot được cho.

| Lệnh | Tác dụng |
|---|---|
| `/start` | bắt đầu, xem danh sách lệnh |
| `/subject` | chọn môn |
| `/practice` | nhận một bài tập |
| `/hint` | xin gợi ý (cho dần từng mức) |
| `/solution` | xin lời giải đầy đủ |
| `/explain <khái niệm>` | hỏi lý thuyết, có trích nguồn |
| `/progress` | xem mức thành thạo |
| `/stop` | kết thúc |

Nhận đề rồi thì **gõ đáp án trực tiếp vào chat**, không cần lệnh gì.

Bot và web **dùng chung một hệ thống chấm**: cùng một bài làm cho cùng một kết quả, và
tiến độ của em là một, không tách theo kênh.

---

## Phần B — Dành cho giảng viên

### B1. Mở trang quản trị

Trang quản trị chỉ hiện khi người dựng hệ thống đã bật nó (đặt biến `ADMIN_TOKEN`).

1. Ở cột phải, khối **Vai**, chuyển sang **Quản trị**.
2. Nhập khoá quản trị được cấp.

Khoá chỉ giữ trong tab đang mở — đóng tab là phải nhập lại. Đây là cố ý, vì dữ liệu sau
đó là bài làm của sinh viên thật.

### B2. Trang Tổng quan

**Bốn ô số**: số lượt làm bài, số người học, số gợi ý đã cấp, số đề trong ngân hàng.

**Bảng theo môn** có một cột đáng chú ý:

- **Tỉ lệ đúng** tính trên số lượt *chấm được*.
- **Không đọc được** đếm riêng những bài mà bộ chấm từ chối kết luận vì sai định dạng.
  Đó là lỗi gõ, không phải lỗi kiến thức, nên không trộn vào tỉ lệ đúng.

> Cột **"không đọc được" tăng bất thường** là tín hiệu ô nhập đáp án đang khó dùng với
> lớp, chứ không phải sinh viên kém.

**Mã lỗi hay gặp** — đây là bảng đáng xem nhất. Một mã lỗi nhảy lên đầu nghĩa là cả lớp
đang hiểu sai **cùng một điều**, và đó là chỗ nên dạy lại.

**Mức gợi ý đã dùng** — nhiều lượt dồn ở mức 4–5 nghĩa là thang gợi ý chưa đủ sức giúp
ở các mức thấp, sinh viên phải leo tới tận lời giải.

**Danh sách người học** — số lượt, số bài đúng, số môn, lần cuối hoạt động.

### B3. Trang Bài làm

200 bài làm gần nhất, lọc được theo môn. Mỗi dòng có thời điểm, người học, mã đề, **bài
làm nguyên văn**, kết quả chấm và mã lỗi.

Nút **Xuất CSV** lấy tới 500 dòng. File có BOM nên Excel trên Windows đọc đúng tiếng
Việt.

Dùng CSV này để phân tích ngoài hệ thống, hoặc đưa vào công cụ gán nhãn lỗi
(`scripts/label_real_errors.py`) khi cần dữ liệu cho nghiên cứu.

### B4. Giới hạn cần biết

Nói rõ để không dùng sai bối cảnh:

- **Phân quyền chỉ có MỘT khoá dùng chung**, không có tài khoản riêng, không ghi vết ai
  đã xem gì. Đủ cho một lớp trong mạng nội bộ; **không đủ** để mở ra Internet.
- **Danh tính sinh viên là chuỗi họ tự đặt**, hệ thống không xác thực. Hai người gõ
  cùng một chuỗi sẽ dùng chung tiến độ.
- **Mức thành thạo là ước lượng**, không phải điểm. Đừng dùng nó để cho điểm chính thức.
- **Kho giáo trình chưa phủ hết mọi chương.** Chạy `python scripts/rag_coverage.py` để
  biết chương nào còn thiếu. Chương thiếu thì phần Hỏi lý thuyết nói thẳng là chưa có
  tài liệu, chứ không đoán.

---

## Phần C — Giao diện

### Chủ đề màu

Cột phải, khối **Giao diện**: **Trắng**, **Đen**, hoặc **Theo máy**. Lựa chọn được ghi
nhớ cho lần sau.

### Đèn báo kết nối

Ngay dưới phần chọn chủ đề:

- **Đã nối backend** (xanh) — mọi thứ bình thường.
- **Mất kết nối backend** (đỏ) — chưa bật máy chủ. Trên các trang sẽ có một bảng chỉ
  dẫn kèm lệnh cần chạy.

Nếu bấm nút mà không thấy gì xảy ra, **xem đèn này trước tiên**.

### Dùng bằng bàn phím

- `Tab` di chuyển giữa các ô, `Enter` trong ô đáp án là nộp bài.
- Con trỏ **tự nhảy vào ô đáp án** sau mỗi bài mới, không cần với chuột.
- Mọi ô đang focus đều có viền rõ.

### Trên điện thoại

Bảng điều khiển nhảy lên **trên** nội dung, vì phải chọn môn và phạm vi trước đã.

---

## Câu hỏi thường gặp

**Em làm đúng mà hệ thống nói "chưa đọc được đáp án"?**
Viết sai định dạng, không phải sai toán. Đọc dòng gợi ý ngay dưới ô nhập. Mức thành
thạo của em **không bị trừ** trong trường hợp này.

**Vì sao bấm "Gợi ý thêm" mãi mà không ra lời giải?**
Thang gợi ý dừng ở mức 4. Bấm **"Cho em xem lời giải đầy đủ"** hai lần.

**Vì sao hệ thống không cho em bài của kỹ năng em yếu nhất?**
Nó chọn bài có xác suất làm đúng quanh 75% — vừa đủ sức để học. Bài quá khó chỉ gây
thất vọng. Muốn luyện đúng chỗ yếu thì tự chọn ở khối **Phạm vi luyện**.

**Câu trả lời đầu tiên chậm?**
Mô hình chạy trên CPU. Các câu sau nhanh hơn nhờ cache.

**Em đổi tên đăng nhập, tiến độ mất rồi?**
Tiến độ gắn với chuỗi tên. Gõ lại đúng chuỗi cũ là có lại.

**Hệ thống có thể chấm sai không?**
Có, và đó là lý do mọi gợi ý đều kèm nguồn hoặc lời giải để em tự kiểm. Bài chấm đúng
đáp án thì rất đáng tin (kiểm chứng bằng SymPy, Monte Carlo, liệt kê vét cạn), nhưng
phần *gọi tên loại lỗi* thì chưa hoàn hảo. Thấy chỗ nào sai, báo giảng viên.
