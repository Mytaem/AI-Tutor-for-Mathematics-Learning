"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "../lib/api";
import { loadSession, saveSession } from "../lib/session";

const SUBJECT_NAMES: Record<string, string> = {
  MAE101: "Toán cho kỹ thuật — giải tích và đại số tuyến tính",
  MAD101: "Toán rời rạc — logic, tổ hợp, đồ thị",
  MAI391: "Toán cho học máy — ma trận, gradient, PCA",
  MAS291: "Xác suất và thống kê — phân phối, ước lượng, kiểm định",
};

export default function HomePage() {
  const router = useRouter();
  const [subjects, setSubjects] = useState<string[]>([]);
  const [userId, setUserId] = useState("");
  const [subject, setSubject] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api
      .subjects()
      .then((list) => {
        setSubjects(list);
        setSubject((current) => current || list[0] || "");
      })
      .catch((exc: Error) => setError(`Không gọi được API: ${exc.message}`));

    const saved = loadSession();
    if (saved) setUserId(saved.userId);
  }, []);

  async function start(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const session = await api.startSession(userId.trim(), subject);
      saveSession({ sessionId: session.session_id, userId: session.user_id, subject: session.subject });
      router.push("/practice");
    } catch (exc) {
      setError((exc as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main>
      <h1>Bắt đầu luyện tập</h1>
      <p className="lead">
        Hệ thống chấm bằng kiểm chứng ký hiệu (SymPy, NetworkX, Monte Carlo), không
        chấm bằng cách hỏi mô hình ngôn ngữ. Gợi ý cho dần theo bậc và không nói đáp
        án trước mức 4.
      </p>

      <form className="panel" onSubmit={start}>
        <label htmlFor="user">Tên hoặc mã sinh viên</label>
        <input
          id="user"
          type="text"
          value={userId}
          onChange={(e) => setUserId(e.target.value)}
          placeholder="ví dụ: SE170001"
          required
          minLength={2}
        />

        <label htmlFor="subject" style={{ marginTop: 12 }}>
          Môn học
        </label>
        <select id="subject" value={subject} onChange={(e) => setSubject(e.target.value)}>
          {subjects.map((code) => (
            <option key={code} value={code}>
              {code} — {SUBJECT_NAMES[code] ?? code}
            </option>
          ))}
        </select>

        <div className="row" style={{ marginTop: 16 }}>
          <button type="submit" disabled={busy || !subject || userId.trim().length < 2}>
            {busy ? "Đang tạo phiên…" : "Vào luyện tập"}
          </button>
          <span className="meta">
            Buổi đầu sẽ có vài câu đo đầu vào để hệ thống ước lượng trình độ.
          </span>
        </div>

        {error && <p className="error">{error}</p>}
      </form>
    </main>
  );
}
