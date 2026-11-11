"use client";

import { useState } from "react";
import { api } from "../lib/api";
import { useApp } from "./providers";

/** Nhắc xác thực email: chưa xác thực thì quên mật khẩu không có đường lấy lại. */
export function VerifyBanner() {
  const { user } = useApp();
  const [state, setState] = useState<"idle" | "busy" | "sent" | "hidden">("idle");
  const [error, setError] = useState<string | null>(null);

  if (!user || user.email_verified || state === "hidden") return null;

  async function resend() {
    setState("busy");
    setError(null);
    try {
      await api.resendVerification();
      setState("sent");
    } catch (exc) {
      setError((exc as Error).message);
      setState("idle");
    }
  }

  return (
    <div className="verify-banner" role="status">
      <div className="inner">
        <span>
          {state === "sent"
            ? `Đã gửi thư xác thực tới ${user.email}. Mở thư và bấm vào link nhé.`
            : "Xác thực email để có thể lấy lại mật khẩu khi quên."}
          {error && <span className="error-inline"> {error}</span>}
        </span>
        {state !== "sent" && (
          <button type="button" className="secondary small" disabled={state === "busy"} onClick={() => void resend()}>
            Gửi lại thư xác thực
          </button>
        )}
        <button type="button" className="ghost small" aria-label="Ẩn thông báo" onClick={() => setState("hidden")}>
          ✕
        </button>
      </div>
    </div>
  );
}
