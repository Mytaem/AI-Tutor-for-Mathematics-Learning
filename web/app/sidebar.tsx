"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { loadSession } from "../lib/session";
import { useApp } from "./providers";
import { ScopePicker } from "./scope-picker";
import { ApiStatus } from "./api-status";

const STUDENT = [
  { href: "/", label: "Chọn môn", icon: "◫" },
  { href: "/practice", label: "Luyện tập", icon: "✎" },
  { href: "/ask", label: "Hỏi lý thuyết", icon: "?" },
  { href: "/progress", label: "Tiến độ", icon: "▤" },
];

const ADMIN = [
  { href: "/admin", label: "Tổng quan", icon: "▦" },
  { href: "/admin/attempts", label: "Bài làm", icon: "☰" },
];

/** Bộ chọn phạm vi chỉ có nghĩa ở những trang thật sự dùng tới nó. */
const SCOPED = ["/practice", "/ask"];

export function Sidebar() {
  const path = usePathname();
  const { role, setRole, theme, setTheme, ready } = useApp();
  const [subject, setSubject] = useState<string | null>(null);
  const [adminEnabled, setAdminEnabled] = useState<boolean | null>(null);

  useEffect(() => {
    setSubject(loadSession()?.subject ?? null);
  }, [path]);

  useEffect(() => {
    api
      .adminEnabled()
      .then((body) => setAdminEnabled(body.enabled))
      .catch(() => setAdminEnabled(false));
  }, []);

  const links = role === "admin" ? ADMIN : STUDENT;

  return (
    <>
      {/* Chỉ hiện chuyển vai khi server ĐÃ bật phần quản trị. Hiện sẵn rồi để
          người dùng bấm vào mới nhận lỗi 403 là bắt họ đâm vào tường. */}
      {adminEnabled && (
        <div className="card-box">
          <div className="title">Vai</div>
          <div className="inner">
            <div className="seg" role="group" aria-label="Chọn vai">
              <button
                type="button"
                aria-pressed={role === "student"}
                onClick={() => setRole("student")}
              >
                Sinh viên
              </button>
              <button
                type="button"
                aria-pressed={role === "admin"}
                onClick={() => setRole("admin")}
              >
                Quản trị
              </button>
            </div>
            {role === "admin" && (
              <p className="meta" style={{ marginTop: 9 }}>
                Chuyển vai ở đây chỉ đổi điều hướng. Quyền thật do server kiểm bằng
                khoá quản trị.
              </p>
            )}
          </div>
        </div>
      )}

      <div className="card-box">
        <div className="title">Chức năng</div>
        <nav className="funcs" aria-label="Chức năng">
          {links.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              aria-current={path === link.href ? "page" : undefined}
            >
              <span className="ico" aria-hidden="true">
                {link.icon}
              </span>
              {link.label}
            </Link>
          ))}
        </nav>
      </div>

      {role === "student" && SCOPED.includes(path) && (
        <div className="card-box">
          <div className="title">Phạm vi luyện</div>
          <div className="inner">
            <ScopePicker subject={subject} />
          </div>
        </div>
      )}

      <div className="card-box">
        <div className="title">Giao diện</div>
        <div className="inner">
          <div className="seg" role="group" aria-label="Chủ đề màu">
            <button type="button" aria-pressed={ready && theme === "light"} onClick={() => setTheme("light")}>
              Trắng
            </button>
            <button type="button" aria-pressed={ready && theme === "dark"} onClick={() => setTheme("dark")}>
              Đen
            </button>
            <button type="button" aria-pressed={ready && theme === "system"} onClick={() => setTheme("system")}>
              Theo máy
            </button>
          </div>
          <div style={{ marginTop: 11 }}>
            <ApiStatus />
          </div>
        </div>
      </div>
    </>
  );
}
