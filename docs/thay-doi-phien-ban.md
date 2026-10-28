# Thay đổi của phiên bản hiện tại

Tài liệu này là mốc mô tả phiên bản production hiện tại, tổng hợp các cập nhật gần đây
thay vì chỉ mô tả commit mới nhất.

## Những điểm mới so với bản trước

- **Hỏi lý thuyết `/ask` ổn định hơn:** không còn phụ thuộc vào cờ bật gợi ý; câu trả
  lời dài hơn và hạn chế bị cắt giữa câu. Nếu model không hoạt động, hệ thống vẫn trả
  các đoạn tài liệu liên quan thay vì lỗi hoặc im lặng.
- **Công thức dễ đọc hơn:** đầu ra như `3*x**2` được chuyển sang dạng dễ nhìn như
  `3x²`; công thức LaTeX vẫn được giữ nguyên để hiển thị đúng.
- **Nhãn bài tập được sửa cho đúng kiến thức:** loại khoảng 330 bài MAI391 ngoài
  chương trình bị gắn nhầm với “Định thức và vết”; phân loại lại bài phủ định logic
  theo De Morgan và bài tích vô hướng vào kỹ năng phù hợp. Việc này giúp gợi ý và
  thống kê mức thành thạo sát nội dung hơn.
- **Có thêm đánh giá EXP-9:** thử nghiệm dùng model chấm phiếu đánh giá gợi ý cho thấy
  mức đồng thuận giữa các model rất thấp, nên không dùng cách này để thay đánh giá của
  con người.

## Hệ thống hiện tại

Phiên bản hiện tại là hệ thống gia sư toán cho bốn môn **MAE101, MAD101, MAI391 và
MAS291**. Hệ thống có bộ kiểm chứng đáp án, gợi ý nhiều mức kèm chặn lộ đáp án, hỏi
đáp theo giáo trình, theo dõi năng lực và chọn bài luyện thích ứng. Người dùng có thể
truy cập bằng web app hoặc Telegram bot.

## Cải tiến độ ổn định production

- Web tự dừng request và báo lỗi rõ ràng khi backend hoặc model phản hồi quá lâu.
- API giới hạn độ dài câu hỏi, đáp án, mã định danh và số bước lời giải để request lỗi
  không chiếm tài nguyên không giới hạn.
- Web production gửi các header bảo mật cơ bản và ẩn header nhận diện framework.
- Next.js được nâng từ nhánh 15 lên 16.4.3, KaTeX lên 0.19.1 và các phụ thuộc gián
  tiếp được cập nhật; `npm audit` hiện không báo lỗ hổng đã biết.
- SQLite dùng WAL và chờ khóa tối đa 10 giây để nhiều worker đọc/ghi ổn định hơn;
  kết nối được đóng khi API dừng.
- Chức năng xuất CSV quản trị lấy toàn bộ bài làm phù hợp bộ lọc, không còn âm thầm
  chỉ xuất 500 dòng gần nhất.
- Phản hồi API có header chống MIME sniffing và iframe; toàn bộ API gửi
  `Cache-Control: no-store` để trình duyệt hoặc proxy không lưu nhầm dữ liệu sinh viên.
- GitHub Actions kiểm tra backend bằng Python 3.12 và kiểm tra kiểu, build, audit cho
  web trên mỗi push và pull request.
