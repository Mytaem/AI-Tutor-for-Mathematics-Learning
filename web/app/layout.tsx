import type { Metadata } from "next";
import "katex/dist/katex.min.css";
import "./globals.css";
import { Nav } from "./nav";
import { ApiStatus } from "./api-status";

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
            <a className="brand" href="/">
              <span className="mark" aria-hidden="true">∫</span>
              <span>AI Tutor Toán</span>
            </a>
            <Nav />
            <div className="spacer" />
            <ApiStatus />
          </div>
        </header>
        {children}
      </body>
    </html>
  );
}
