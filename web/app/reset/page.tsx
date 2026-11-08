"use client";

import Link from "next/link";
import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api } from "../../lib/api";

function Reset() {
  const token = useSearchParams().get("token") ?? "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    if (password !== confirm) {
      setError("Hai mật khẩu chưa khớp nhau");
      return;
    }
    setBusy(true);
    try {
      await api.resetPassword(token, password);
      setDone(true);
    } catch (exc) {
      setError((exc as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-card">
        <span className="eyebrow">Numeris</span>
        <h1>Đặt mật khẩu mới</h1>
        {done ? (
          <>
            <p className="lead">Đã đổi mật khẩu. Mọi thiết bị đã được đăng xuất để bảo đảm an toàn.</p>
            <Link className="button block start-button" href="/login">Đăng nhập bằng mật khẩu mới</Link>
          </>
        ) : !token ? (
          <>
            <p className="error" role="alert">Đường link thiếu mã đặt lại mật khẩu.</p>
            <Link className="button block start-button" href="/forgot">Yêu cầu link mới</Link>
          </>
        ) : (
          <form onSubmit={submit} noValidate>
            <div className="field-group">
              <label htmlFor="password">Mật khẩu mới</label>
              <input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                autoComplete="new-password" />
              <p className="meta" style={{ marginTop: 6 }}>Ít nhất 8 ký tự, có cả chữ và số.</p>
            </div>
            <div className="field-group">
              <label htmlFor="confirm">Nhập lại mật khẩu mới</label>
              <input id="confirm" type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)}
                autoComplete="new-password" />
            </div>
            {error && (
              <p className="error" role="alert">
                {error} {error.includes("hết hạn") && <Link href="/forgot">Yêu cầu link mới</Link>}
              </p>
            )}
            <button type="submit" className="block start-button" disabled={busy || !password}>
              {busy && <span className="spin" aria-hidden="true" />}Đặt mật khẩu mới
            </button>
          </form>
        )}
      </section>
    </main>
  );
}

export default function ResetPage() {
  return (
    <Suspense fallback={<main className="auth-page"><section className="auth-card"><div className="skeleton tall" /></section></main>}>
      <Reset />
    </Suspense>
  );
}
