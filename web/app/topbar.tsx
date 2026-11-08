"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useApp } from "./providers";

export function Topbar() {
  const { user, logout } = useApp();
  const path = usePathname();
  const [open, setOpen] = useState(false);
  const menu = useRef<HTMLDivElement>(null);

  useEffect(() => setOpen(false), [path]);
  useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent) => {
      if (!menu.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  return (
    <header className="topbar">
      <div className="inner">
        <Link className="brand" href="/">
          <span className="mark" aria-hidden="true">N</span>
          <span className="brand-copy">
            <strong>Numeris</strong>
            <small>Trợ lý học toán</small>
          </span>
        </Link>
        <div className="spacer" />
        {user === undefined ? null : user ? (
          <div className="account" ref={menu}>
            <button type="button" className="account-button" aria-expanded={open} aria-haspopup="menu"
              onClick={() => setOpen((v) => !v)}>
              <span className="avatar" aria-hidden="true">{user.display_name.slice(0, 1).toUpperCase()}</span>
              <span className="account-name">{user.display_name}</span>
            </button>
            {open && (
              <div className="account-menu" role="menu">
                <div className="account-email">{user.email}</div>
                <Link role="menuitem" href="/account">Tài khoản</Link>
                <button type="button" role="menuitem" onClick={() => void logout()}>Đăng xuất</button>
              </div>
            )}
          </div>
        ) : (
          path !== "/login" && <Link className="button small" href={`/login?next=${encodeURIComponent(path)}`}>Đăng nhập</Link>
        )}
      </div>
    </header>
  );
}
