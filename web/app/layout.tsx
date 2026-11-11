import type { Metadata } from "next";
import "katex/dist/katex.min.css";
import "./globals.css";
import { Be_Vietnam_Pro } from "next/font/google";
import { Providers } from "./providers";

// Be Vietnam Pro: thiết kế cho tiếng Việt — dấu đặt đúng chỗ, không chồng lên nhau
// như nhiều phông Latin. Next tự lưu phông về server lúc build, không gọi Google lúc chạy.
const font = Be_Vietnam_Pro({
  subsets: ["vietnamese", "latin"],
  weight: ["400", "500", "600", "700"],
  display: "swap",
  variable: "--font-brand",
});

export const metadata: Metadata = {
  title: "Numeris — Học toán chủ động",
  description: "Luyện tập, hỏi đáp và theo dõi tiến độ cho MAE101, MAD101, MAI391, MAS291",
};

/**
 * Đặt chủ đề TRƯỚC khi trang vẽ lần đầu.
 *
 * Chủ đề nằm ở localStorage, mà localStorage chỉ đọc được ở trình duyệt. Nếu
 * để React đặt trong useEffect thì người chọn chủ đề Đen sẽ thấy một nháy
 * TRẮNG mỗi lần tải trang. Đoạn script nhỏ này chạy đồng bộ trong <head> nên
 * không có nháy nào.
 */
const THEME_BOOT = `
try {
  var t = localStorage.getItem("ai-tutor-theme");
  if (t === "light" || t === "dark") document.documentElement.setAttribute("data-theme", t);
} catch (e) {}
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="vi" suppressHydrationWarning className={font.variable}>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOT }} />
      </head>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
