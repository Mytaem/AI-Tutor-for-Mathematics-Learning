"use client";

import { useState } from "react";
import { api } from "../../lib/api";
import { useApp } from "../providers";

export default function AccountPage() {
  const { user, logout } = useApp();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function change(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setMessage(null);
    if (next !== confirm) {
      setError("Hai mật khẩu mới chưa khớp nhau");
      return;
    }
    setBusy(true);
    try {
      await api.changePassword(current, next);
      setCurrent(""); setNext(""); setConfirm("");
      setMessage("Đã đổi mật khẩu. Các thiết bị khác đã được đăng xuất.");
    } catch (exc) {
      setError((exc as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (!user) {
    return <main><div className="panel"><div className="skeleton tall w60" /><div className="skeleton" /></div></main>;
  }

  return (
    <main>
      <span className="eyebrow">Tài khoản</span>
      <h1>{user.display_name}</h1>
      <p className="lead">{user.email}</p>

      <form className="panel" onSubmit={change} style={{ maxWidth: 520 }}>
        <h2 style={{ marginTop: 0 }}>Đổi mật khẩu</h2>
        <div className="field-group">
          <label htmlFor="current">Mật khẩu hiện tại</label>
          <input id="current" type="password" value={current} onChange={(e) => setCurrent(e.target.value)}
            required autoComplete="current-password" />
        </div>
        <div className="field-group">
          <label htmlFor="new">Mật khẩu mới</label>
          <input id="new" type="password" value={next} onChange={(e) => setNext(e.target.value)}
            required minLength={8} autoComplete="new-password" />
          <p className="meta" style={{ marginTop: 6 }}>Ít nhất 8 ký tự, có cả chữ và số.</p>
        </div>
        <div className="field-group">
          <label htmlFor="confirm">Nhập lại mật khẩu mới</label>
          <input id="confirm" type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)}
            required autoComplete="new-password" />
        </div>
        {error && <p className="error" role="alert">{error}</p>}
        {message && <p className="meta" role="status" style={{ color: "var(--ok)" }}>{message}</p>}
        <div className="row" style={{ marginTop: 18 }}>
          <button type="submit" disabled={busy || !current || !next}>
            {busy && <span className="spin" aria-hidden="true" />}Đổi mật khẩu
          </button>
          <button type="button" className="ghost" onClick={() => void logout()}>Đăng xuất</button>
        </div>
      </form>
    </main>
  );
}
