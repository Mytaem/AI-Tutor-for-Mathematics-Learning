"use client";

import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import { loadAdminToken, saveAdminToken } from "../../lib/prefs";

/**
 * Cửa vào phần quản trị.
 *
 * Nói thẳng điều này để không ai hiểu sai: đây KHÔNG phải lớp bảo mật. Nó chỉ
 * giữ hộ cái khoá và gắn vào mỗi lời gọi. Chỗ chặn thật là server — mọi
 * endpoint `/admin/*` đều so khoá bằng `secrets.compare_digest`, nên xoá đoạn
 * JavaScript này trong trình duyệt cũng không mở được gì.
 *
 * Khoá nằm ở `sessionStorage`, đóng tab là mất.
 */
export function AdminGate({
  children,
}: {
  children: (token: string) => React.ReactNode;
}) {
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [token, setToken] = useState("");
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api
      .adminEnabled()
      .then((body) => setEnabled(body.enabled))
      .catch(() => setEnabled(false));
    setToken(loadAdminToken());
  }, []);

  async function unlock(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      // Thử gọi một endpoint thật để biết khoá đúng hay sai, thay vì nhận bừa
      // rồi để người dùng lạc vào trang trống toàn lỗi.
      await api.adminOverview(draft.trim());
      saveAdminToken(draft.trim());
      setToken(draft.trim());
    } catch (exc) {
      setError((exc as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (enabled === null) {
    return (
      <div className="panel">
        <div className="skeleton tall w40" />
        <div className="skeleton" />
      </div>
    );
  }

  if (!enabled) {
    return (
      <div className="banner info">
        <span aria-hidden="true">i</span>
        <div>
          <strong>Phần quản trị đang tắt</strong>
          <div className="meta" style={{ marginTop: 4 }}>
            Mặc định là tắt vì dữ liệu ở đây là bài làm của người thật. Bật bằng cách
            đặt biến môi trường rồi khởi động lại API:
            <br />
            <code>ADMIN_TOKEN=khoá-của-bạn python -m uvicorn src.api.app:create_app --factory --port 8000</code>
          </div>
        </div>
      </div>
    );
  }

  if (!token) {
    return (
      <form className="panel" onSubmit={unlock} style={{ maxWidth: 420 }}>
        <label htmlFor="admin-token">Khoá quản trị</label>
        <input
          id="admin-token"
          type="password"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="giá trị của ADMIN_TOKEN"
          autoComplete="off"
        />
        <div className="row" style={{ marginTop: 14 }}>
          <button type="submit" disabled={busy || !draft.trim()}>
            {busy && <span className="spin" aria-hidden="true" />}
            Mở
          </button>
        </div>
        {error && <p className="error">{error}</p>}
        <p className="meta" style={{ marginTop: 12 }}>
          Khoá chỉ giữ trong tab này, đóng tab là mất.
        </p>
      </form>
    );
  }

  return (
    <>
      <div className="row spread" style={{ marginBottom: 14 }}>
        <span className="chip ok">Đã mở bằng khoá quản trị</span>
        <button
          type="button"
          className="ghost small"
          onClick={() => {
            saveAdminToken("");
            setToken("");
            setDraft("");
          }}
        >
          Khoá lại
        </button>
      </div>
      {children(token)}
    </>
  );
}
