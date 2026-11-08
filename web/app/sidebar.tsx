"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { api } from "../lib/api";
import { loadSession } from "../lib/session";
import { ApiStatus } from "./api-status";
import { useApp } from "./providers";
import { ScopePicker } from "./scope-picker";

const STUDENT = [
  { href: "/", label: "Trang chủ", icon: "home" },
  { href: "/practice", label: "Luyện tập", icon: "practice" },
  { href: "/ask", label: "Hỏi đáp", icon: "ask" },
  { href: "/progress", label: "Tiến độ", icon: "progress" },
];

const ADMIN = [
  { href: "/admin", label: "Tổng quan", icon: "progress" },
  { href: "/admin/attempts", label: "Bài làm", icon: "list" },
];

const SCOPED = ["/practice", "/ask"];

export function Sidebar() {
  const path = usePathname();
  const { role, setRole, theme, setTheme, ready } = useApp();
  const [subject, setSubject] = useState<string | null>(null);
  const [adminEnabled, setAdminEnabled] = useState<boolean | null>(null);
  // Màn hẹp: khung phạm vi thu gọn, để đề bài nằm ngay màn hình đầu tiên.
  const [scopeOpen, setScopeOpen] = useState(true);
  useEffect(() => {
    if (window.matchMedia("(max-width: 980px)").matches) setScopeOpen(false);
  }, []);

  useEffect(() => setSubject(loadSession()?.subject ?? null), [path]);
  useEffect(() => {
    api.adminEnabled().then((body) => setAdminEnabled(body.enabled)).catch(() => setAdminEnabled(false));
  }, []);

  const links = role === "admin" ? ADMIN : STUDENT;

  return (
    <div className="side-inner">
      {adminEnabled && (
        <div className="side-section role-card">
          <div className="side-label">Chế độ</div>
          <div className="inner">
            <div className="seg" role="group" aria-label="Chọn chế độ">
              <button type="button" aria-pressed={role === "student"} onClick={() => setRole("student")}>Học tập</button>
              <button type="button" aria-pressed={role === "admin"} onClick={() => setRole("admin")}>Quản trị</button>
            </div>
          </div>
        </div>
      )}

      <nav className="funcs" aria-label="Điều hướng chính">
        {links.map((link) => (
          <Link key={link.href} href={link.href} aria-current={path === link.href ? "page" : undefined}>
            <span className="ico" aria-hidden="true"><NavIcon name={link.icon} /></span>
            {link.label}
          </Link>
        ))}
      </nav>

      {role === "student" && SCOPED.includes(path) && (
        <div className="side-section scope-card">
          <button
            type="button"
            className="scope-toggle"
            aria-expanded={scopeOpen}
            onClick={() => setScopeOpen((open) => !open)}
          >
            Phạm vi luyện tập <span aria-hidden="true">{scopeOpen ? "▴" : "▾"}</span>
          </button>
          <div className="side-label scope-label">Phạm vi</div>
          {scopeOpen && <div className="inner"><ScopePicker subject={subject} /></div>}
        </div>
      )}

      <div className="side-section side-footer">
        <div className="side-label">Giao diện</div>
        <div className="inner">
          <div className="seg" role="group" aria-label="Chủ đề màu">
            <button type="button" aria-pressed={ready && theme === "light"} onClick={() => setTheme("light")}>Sáng</button>
            <button type="button" aria-pressed={ready && theme === "dark"} onClick={() => setTheme("dark")}>Tối</button>
            <button type="button" aria-pressed={ready && theme === "system"} onClick={() => setTheme("system")}>Tự động</button>
          </div>
          <div className="connection-status"><ApiStatus /></div>
        </div>
      </div>
    </div>
  );
}

function NavIcon({ name }: { name: string }) {
  const paths: Record<string, ReactNode> = {
    home: <><path d="M3 10.5 12 3l9 7.5"/><path d="M5.5 9.5V21h13V9.5M9 21v-7h6v7"/></>,
    practice: <><path d="M4 19.5V5a2 2 0 0 1 2-2h12v16H6a2 2 0 0 0-2 2Z"/><path d="M8 7h6M8 11h7"/></>,
    ask: <><path d="M21 15a4 4 0 0 1-4 4H8l-5 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4Z"/><path d="M9.5 9a2.5 2.5 0 1 1 3.3 2.37c-.8.3-1.3.88-1.3 1.63M11.5 16h.01"/></>,
    progress: <><path d="M4 19V9M10 19V5M16 19v-7M22 19H2"/></>,
    list: <><path d="M8 6h13M8 12h13M8 18h13"/><path d="M3 6h.01M3 12h.01M3 18h.01"/></>,
  };
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg>;
}
