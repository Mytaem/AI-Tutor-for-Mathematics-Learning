# Trước khi bán: những gì đã sẵn sàng và những gì còn chặn

Viết cho **chủ sản phẩm**. Phần kỹ thuật đã chuẩn bị để bán được; phần dưới đây là
những thứ **code không giải quyết được** nhưng quyết định có được bán hay không.

Đây không phải tư vấn pháp lý. Mọi mục có chữ **luật sư** cần người có chuyên môn xem.

## 1. Nội dung giáo trình: đang CHẶN

Kho giáo trình hiện dùng để phát triển **không được phép dùng thương mại**:

| Tài liệu | Môn | Vì sao không bán được |
|---|---|---|
| OpenStax *Calculus*, *Introductory Statistics 2e* | MAE101, MAS291 | CC BY-NC-SA: **NC** cấm mục đích thương mại |
| Deisenroth, *Mathematics for Machine Learning* | MAI391 | tác giả chỉ cho đọc miễn phí, không cho phát tán |
| Rosen, *Discrete Mathematics* | MAD101 | có bản quyền |
| Slide FPT University | cả 4 môn | thuộc về FPT |

**Đã làm:** bộ cài cho khách không chứa kho giáo trình, nên khách không nhận được nội
dung này ([trien-khai.md](trien-khai.md)).

**Bạn chọn một trong hai hướng:**

- **Bán cho trường (B2B):** mỗi trường dựng kho từ slide của chính giảng viên trường đó.
  Họ có quyền với tài liệu của họ, còn bạn bán phần mềm. Hợp đồng ghi rõ khách chịu
  trách nhiệm về quyền với tài liệu họ nạp vào. **Đây là hướng ít rủi ro nhất.**
- **Bán trực tiếp cho sinh viên (B2C):** cần kho giáo trình của riêng bạn, gồm tài liệu
  có giấy phép cho phép thương mại (CC BY, CC BY-SA) hoặc tài liệu tự viết. Một số ứng
  viên cần kiểm lại giấy phép trước khi dùng: Levin, *Discrete Mathematics: An Open
  Introduction* (CC BY-SA); Hefferon, *Linear Algebra*; *OpenIntro Statistics*. MAI391
  chưa có giáo trình mở thay thế, phải tự viết.

**Phần không bị ảnh hưởng:** ngân hàng 4.955 đề, lời giải từng bước, gợi ý và chấm bài
đều do máy sinh từ template, không chép từ sách.

## 2. Mô hình AI: đã xử lý

| Thành phần | Giấy phép | Trạng thái |
|---|---|---|
| qwen2.5:7b-instruct (mặc định) | Apache-2.0 | bán được |
| qwen2.5:3b-instruct | Qwen Research License | **cấm thương mại**, đã bỏ khỏi mặc định |
| bge-m3 (truy xuất) | MIT | bán được |
| LoRA phân loại lỗi (gốc Qwen2.5-1.5B) | Apache-2.0 | bán được |
| DKT | tự huấn luyện trên dữ liệu mô phỏng | bán được |

Nếu đổi mô hình, kiểm giấy phép trước: nhiều mô hình "mở" cấm dùng thương mại.

## 3. Dữ liệu cá nhân người học: cần luật sư

Hệ thống lưu mã sinh viên, bài làm và tiến độ, tức là có xử lý dữ liệu cá nhân. Ở Việt
Nam việc này chịu sự điều chỉnh của quy định về bảo vệ dữ liệu cá nhân (Nghị định
13/2023/NĐ-CP và Luật Bảo vệ dữ liệu cá nhân). Cần:

- [ ] Chính sách quyền riêng tư và điều khoản sử dụng (**luật sư**), hiện trong ứng dụng.
- [ ] Hợp đồng xử lý dữ liệu với trường (B2B): ai là bên kiểm soát dữ liệu, ai là bên xử lý.
- [ ] Quy trình xoá dữ liệu khi người học yêu cầu. Hiện chưa có chức năng này.

**Đã có:** dữ liệu ở máy chủ của khách, không gửi ra ngoài; mô hình chạy cục bộ qua
Ollama; trang quản trị tắt mặc định và cần khoá.

## 4. Tài khoản người dùng: đã có email + mật khẩu

**Đã làm:** đăng ký, đăng nhập, đăng xuất, đổi mật khẩu (tự đăng xuất các thiết bị
khác). Mật khẩu băm scrypt có muối; phiên đăng nhập là cookie httpOnly, cơ sở dữ liệu
chỉ giữ bản băm của token. Sai mật khẩu 5 lần trong 15 phút thì tạm khoá theo email
và theo IP. Danh tính lấy từ phiên đăng nhập, nên không ai xem hay nộp bài vào dữ liệu
của người khác bằng cách đổi tham số (có test cho từng trường hợp).

**Còn thiếu, cần trước khi mở bán rộng:**

- [ ] **Quên mật khẩu**: cần dịch vụ gửi email (SMTP hoặc nhà cung cấp gửi mail).
- [ ] **Xác thực email** khi đăng ký: chặn tài khoản rác.
- [ ] **Xoá tài khoản và dữ liệu** theo yêu cầu người học (quy định bảo vệ dữ liệu cá nhân).
- [ ] Trang quản trị vẫn dùng một khoá chung; nên đổi thành tài khoản quản trị riêng.

## 5. Còn thiếu nếu bán trực tiếp cho sinh viên

Thanh toán, gói cước, hoá đơn; trang giới thiệu; kênh hỗ trợ khách hàng; theo dõi lỗi
và thời gian phản hồi; máy chủ có GPU (không có GPU thì hỏi đáp mất 20–60 giây mỗi câu).
