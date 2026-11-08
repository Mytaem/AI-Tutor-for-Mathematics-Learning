"use client";

import Link from "next/link";
import { useState } from "react";
import { api } from "../../lib/api";

export default function ForgotPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.forgotPassword(email.trim());
      setSent(true);
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
        <h1>Quên mật khẩu</h1>
        {sent ? (
          <>
            <p className="lead">
              Nếu <strong>{email.trim()}</strong> đã đăng ký, một thư có link đặt lại mật khẩu vừa được gửi tới.
            </p>
            <p className="meta">Link có hiệu lực trong 1 giờ. Không thấy thư thì xem cả mục Spam/Quảng cáo.</p>
            <Link className="button block start-button" href="/login">Quay lại đăng nhập</Link>
          </>
        ) : (
          <form onSubmit={submit} noValidate>
            <p className="meta">Nhập email bạn đã dùng để đăng ký. Chúng tôi sẽ gửi link đặt lại mật khẩu.</p>
            <div className="field-group">
              <label htmlFor="email">Email</label>
              <input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                autoComplete="email" inputMode="email" placeholder="ban@gmail.com" />
            </div>
            {error && <p className="error" role="alert">{error}</p>}
            <button type="submit" className="block start-button" disabled={busy || !email.trim()}>
              {busy && <span className="spin" aria-hidden="true" />}Gửi link đặt lại mật khẩu
            </button>
            <p className="privacy-note"><Link href="/login">Quay lại đăng nhập</Link></p>
          </form>
        )}
      </section>
    </main>
  );
}
