import type { Metadata } from "next";
import "katex/dist/katex.min.css";
import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "AI Tutor Toán",
  description: "Gia sư toán có kiểm chứng ký hiệu — MAE101, MAD101, MAI391, MAS291",
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
    <html lang="vi">
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOT }} />
      </head>
      <body>
        <header className="topbar">
          <div className="inner">
            <a className="brand" href="/">
              <span className="mark" aria-hidden="true">∫</span>
              <span>AI Tutor Toán</span>
            </a>
            <div className="spacer" />
            <span className="meta">MAE101 · MAD101 · MAI391 · MAS291</span>
          </div>
        </header>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
