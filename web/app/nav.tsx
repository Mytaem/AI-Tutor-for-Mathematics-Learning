"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Chọn môn" },
  { href: "/practice", label: "Luyện tập" },
  { href: "/ask", label: "Hỏi lý thuyết" },
  { href: "/progress", label: "Tiến độ" },
];

export function Nav() {
  const path = usePathname();
  return (
    <nav aria-label="Điều hướng chính">
      {LINKS.map((link) => (
        <Link
          key={link.href}
          href={link.href}
          // aria-current làm hai việc một lúc: tô sáng mục đang mở (CSS bắt
          // vào chính thuộc tính này) và cho trình đọc màn hình biết vị trí.
          aria-current={path === link.href ? "page" : undefined}
        >
          {link.label}
        </Link>
      ))}
    </nav>
  );
}
