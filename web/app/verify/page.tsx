"use client";

import Link from "next/link";
import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api } from "../../lib/api";
import { useApp } from "../providers";

function Verify() {
  const token = useSearchParams().get("token") ?? "";
  const { user, setUser } = useApp();
  const [status, setStatus] = useState<"working" | "done" | "failed">("working");
  const [message, setMessage] = useState("");
  const started = useRef(false);

  useEffect(() => {
    // Link chỉ dùng được một lần: StrictMode chạy effect hai lần thì lần hai sẽ báo hỏng.
    if (started.current) return;
    started.current = true;
    if (!token) {
      setStatus("failed");
      setMessage("Thiếu mã xác thực trong đường link.");
      return;
    }
    api
      .verifyEmail(token)
      .then((verified) => {
        setStatus("done");
        if (user && user.user_id === verified.user_id) setUser(verified);
      })
      .catch((exc: Error) => {
        setStatus("failed");
        setMessage(exc.message);
      });
  }, [token, user, setUser]);

  return (
    <main className="auth-page">
      <section className="auth-card">
        <span className="eyebrow">Numeris</span>
        <h1>Xác thực email</h1>
        {status === "working" && <div className="skeleton tall" />}
        {status === "done" && (
          <>
            <p className="lead">Email của bạn đã được xác thực.</p>
            <Link className="button block start-button" href="/">Vào học <span aria-hidden="true">→</span></Link>
          </>
        )}
        {status === "failed" && (
          <>
            <p className="error" role="alert">{message}</p>
            <p className="meta">Đăng nhập rồi bấm “Gửi lại thư xác thực” ở đầu trang để nhận link mới.</p>
            <Link className="button block start-button" href="/login">Đăng nhập</Link>
          </>
        )}
      </section>
    </main>
  );
}

export default function VerifyPage() {
  return (
    <Suspense fallback={<main className="auth-page"><section className="auth-card"><div className="skeleton tall" /></section></main>}>
      <Verify />
    </Suspense>
  );
}
