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
  const [deletePassword, setDeletePassword] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [dataError, setDataError] = useState<string | null>(null);

  async function download() {
    setDataError(null);
    try {
      const blob = await api.exportMyData();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "numeris-du-lieu-cua-toi.json";
      link.click();
      URL.revokeObjectURL(url);
    } catch (exc) {
      setDataError((exc as Error).message);
    }
  }

  async function removeAccount(event: React.FormEvent) {
    event.preventDefault();
    setDataError(null);
    try {
      await api.deleteAccount(deletePassword);
      window.location.assign("/");
    } catch (exc) {
      setDataError((exc as Error).message);
    }
  }

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
      <p className="lead">
        {user.email}{" "}
        <span className={`chip ${user.email_verified ? "ok" : "warn"}`}>
          {user.email_verified ? "đã xác thực" : "chưa xác thực"}
        </span>
      </p>

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

      <section className="panel" style={{ maxWidth: 520 }}>
        <h2 style={{ marginTop: 0 }}>Dữ liệu của bạn</h2>
        <p className="meta">
          Tải về toàn bộ dữ liệu hệ thống đang giữ về bạn: tài khoản, bài làm, gợi ý đã nhận, mức thành thạo.
        </p>
        <button type="button" className="secondary" onClick={() => void download()}>Tải dữ liệu (JSON)</button>

        <div className="danger-zone">
          <h3>Xoá tài khoản</h3>
          <p className="meta">
            Xoá vĩnh viễn tài khoản và <strong>mọi</strong> dữ liệu học tập. Không thể khôi phục.
          </p>
          {confirmDelete ? (
            <form onSubmit={removeAccount}>
              <div className="field-group">
                <label htmlFor="delete-password">Nhập mật khẩu để xác nhận</label>
                <input id="delete-password" type="password" value={deletePassword}
                  onChange={(e) => setDeletePassword(e.target.value)} autoComplete="current-password" />
              </div>
              <div className="row" style={{ marginTop: 12 }}>
                <button type="submit" className="danger" disabled={!deletePassword}>Xoá vĩnh viễn</button>
                <button type="button" className="ghost" onClick={() => setConfirmDelete(false)}>Huỷ</button>
              </div>
            </form>
          ) : (
            <button type="button" className="danger-outline" onClick={() => setConfirmDelete(true)}>
              Xoá tài khoản…
            </button>
          )}
        </div>
        {dataError && <p className="error" role="alert">{dataError}</p>}
      </section>
    </main>
  );
}
