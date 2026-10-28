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
      <span className="status-pill" title="Hệ thống đang hoạt động">
        <Dot color="var(--ok)" /> Trực tuyến
      </span>
    );
  }

  return (
    <span className="status-pill offline" title={`Không thể kết nối ${API_URL}`}>
      <Dot color="var(--wrong)" /> Mất kết nối
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
        <strong>Không thể kết nối</strong>
        <div className="meta" style={{ marginTop: 4 }}>
          Dịch vụ đang tạm gián đoạn. Vui lòng thử lại sau ít phút.
        </div>
      </div>
    </div>
  );
}
