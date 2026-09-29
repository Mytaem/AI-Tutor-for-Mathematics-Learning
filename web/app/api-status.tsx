"use client";

import { useEffect, useState } from "react";
import { API_URL, api } from "../lib/api";

type State = "checking" | "up" | "down";

/**
 * Đèn báo API còn sống hay không.
 *
 * Có component này vì một lỗi thật: API thiếu CORS, trình duyệt chặn mọi lời
 * gọi, và giao diện vẫn dựng ra đầy đủ — nhìn hệt như "app mới chỉ có phần
 * vỏ". Người dùng không có cách nào biết hỏng ở đâu, còn bộ test thì xanh vì
 * TestClient không thi hành same-origin policy.
 *
 * Đèn đỏ ở đây nói thẳng "không gọi được backend" và chỉ luôn việc cần làm,
 * thay vì để người dùng tự đoán.
 */
export function ApiStatus() {
  const [state, setState] = useState<State>("checking");

  useEffect(() => {
    let alive = true;
    const ping = () =>
      api
        .health()
        .then(() => alive && setState("up"))
        .catch(() => alive && setState("down"));
    void ping();
    const timer = setInterval(ping, 20000);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, []);

  if (state === "checking") return null;

  if (state === "up") {
    return (
      <span className="chip ok" title={`Đang nối tới ${API_URL}`}>
        <Dot color="var(--ok)" /> Đã nối backend
      </span>
    );
  }

  return (
    <span className="chip wrong" title={`Không gọi được ${API_URL}`}>
      <Dot color="var(--wrong)" /> Mất kết nối backend
    </span>
  );
}

function Dot({ color }: { color: string }) {
  return (
    <span
      aria-hidden="true"
      style={{ width: 7, height: 7, borderRadius: "50%", background: color, display: "inline-block" }}
    />
  );
}

/** Bảng chỉ dẫn to, hiện giữa trang khi backend không trả lời. */
export function ApiDownBanner() {
  return (
    <div className="banner">
      <span aria-hidden="true">⚠</span>
      <div>
        <strong>Không gọi được backend</strong>
        <div className="meta" style={{ marginTop: 4 }}>
          Web đang trỏ tới <code>{API_URL}</code>. Mở một cửa sổ dòng lệnh khác rồi chạy:
          <br />
          <code>python -m uvicorn src.api.app:create_app --factory --port 8000</code>
          <br />
          Nếu API đang chạy mà vẫn báo lỗi này, kiểm tra <code>CORS_ORIGINS</code> có chứa
          địa chỉ của trang web không.
        </div>
      </div>
    </div>
  );
}
