/** Định dạng dùng chung cho các bảng. */

/** Dấu thời gian kiểu Unix (giây) -> chuỗi ngắn kiểu Việt Nam. */
export function when(seconds: number | null): string {
  if (!seconds) return "—";
  return new Date(seconds * 1000).toLocaleString("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Ô tiêu đề hàng: là <th> để trình đọc màn hình hiểu, nhưng trông như <td>. */
export const rowHeadStyle: React.CSSProperties = {
  fontWeight: 400,
  textTransform: "none",
  letterSpacing: 0,
  fontSize: "0.9rem",
  color: "var(--ink)",
  padding: "10px 8px",
};
