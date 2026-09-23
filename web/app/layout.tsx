import type { Metadata } from "next";
import Link from "next/link";
import "katex/dist/katex.min.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Tutor Toán",
  description: "Gia sư toán có kiểm chứng ký hiệu — MAE101, MAD101, MAI391, MAS291",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="vi">
      <body>
        <header className="site">
          <div className="inner">
            <span className="brand">AI Tutor Toán</span>
            <Link href="/">Chọn môn</Link>
            <Link href="/practice">Luyện tập</Link>
            <Link href="/ask">Hỏi lý thuyết</Link>
            <Link href="/progress">Tiến độ</Link>
          </div>
        </header>
        {children}
      </body>
    </html>
  );
}
