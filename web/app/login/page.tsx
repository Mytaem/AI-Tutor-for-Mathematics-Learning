"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "../../lib/api";
import { useApp } from "../providers";

type Mode = "login" | "register";

/** Chỉ chuyển tới đường dẫn nội bộ — `?next=https://...` không được đưa người dùng ra ngoài. */
function safeNext(value: string | null): string {
  return value && value.startsWith("/") && !value.startsWith("//") ? value : "/";
}

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const next = safeNext(params.get("next"));
  const { user, setUser } = useApp();
  const [mode, setMode] = useState<Mode>(params.get("mode") === "register" ? "register" : "login");
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (user) router.replace(next);
  }, [user, next, router]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    if (mode === "register" && password !== confirm) {
      setError("Hai mật khẩu chưa khớp nhau");
      return;
    }
    setBusy(true);
    try {
      const account =
        mode === "login"
          ? await api.login(email.trim(), password)
          : await api.register(email.trim(), password, name.trim());
      setUser(account);
      router.replace(next);
    } catch (exc) {
      setError((exc as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const registering = mode === "register";

  return (
    <main className="auth-page">
      <section className="auth-card">
        <span className="eyebrow">Numeris</span>
        <h1>{registering ? "Tạo tài khoản" : "Đăng nhập"}</h1>
        <p className="meta">
          {registering
            ? "Tài khoản giữ tiến độ học của bạn trên mọi thiết bị."
            : "Đăng nhập để học tiếp đúng chỗ bạn dừng lại."}
        </p>

        <div className="seg auth-switch" role="tablist" aria-label="Chọn đăng nhập hoặc đăng ký">
          <button type="button" role="tab" aria-selected={!registering} aria-pressed={!registering}
            onClick={() => { setMode("login"); setError(null); }}>Đăng nhập</button>
          <button type="button" role="tab" aria-selected={registering} aria-pressed={registering}
            onClick={() => { setMode("register"); setError(null); }}>Tạo tài khoản</button>
        </div>

        <form onSubmit={submit} noValidate>
          {registering && (
            <div className="field-group">
              <label htmlFor="name">Tên hiển thị</label>
              <input id="name" type="text" value={name} onChange={(e) => setName(e.target.value)}
                placeholder="Nguyễn Văn An" autoComplete="name" maxLength={80} />
            </div>
          )}
          <div className="field-group">
            <label htmlFor="email">Email</label>
            <input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)}
              placeholder="ban@gmail.com" autoComplete="email" required inputMode="email" />
          </div>
          <div className="field-group">
            <label htmlFor="password">Mật khẩu</label>
            <div className="password-row">
              <input id="password" type={showPassword ? "text" : "password"} value={password}
                onChange={(e) => setPassword(e.target.value)} required minLength={registering ? 8 : 1}
                autoComplete={registering ? "new-password" : "current-password"} />
              <button type="button" className="ghost small" onClick={() => setShowPassword((v) => !v)}
                aria-label={showPassword ? "Ẩn mật khẩu" : "Hiện mật khẩu"}>
                {showPassword ? "Ẩn" : "Hiện"}
              </button>
            </div>
            {registering ? (
              <p className="meta" style={{ marginTop: 6 }}>Ít nhất 8 ký tự, có cả chữ và số.</p>
            ) : (
              <p className="meta" style={{ marginTop: 6 }}><Link href="/forgot">Quên mật khẩu?</Link></p>
            )}
          </div>
          {registering && (
            <div className="field-group">
              <label htmlFor="confirm">Nhập lại mật khẩu</label>
              <input id="confirm" type={showPassword ? "text" : "password"} value={confirm}
                onChange={(e) => setConfirm(e.target.value)} required autoComplete="new-password" />
            </div>
          )}

          {error && <p className="error" role="alert">{error}</p>}

          <button type="submit" className="block start-button" disabled={busy || !email || !password}>
            {busy && <span className="spin" aria-hidden="true" />}
            {busy ? "Đang xử lý…" : registering ? "Tạo tài khoản" : "Đăng nhập"}
          </button>
        </form>
      </section>
    </main>
  );
}

export default function LoginPage() {
  // useSearchParams cần Suspense để Next dựng sẵn được trang tĩnh.
  return (
    <Suspense fallback={<main className="auth-page"><section className="auth-card"><div className="skeleton tall" /></section></main>}>
      <LoginForm />
    </Suspense>
  );
}
