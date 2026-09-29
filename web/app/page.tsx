"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "../lib/api";
import { loadSession, saveSession } from "../lib/session";
import { ApiDownBanner } from "./api-status";

const SUBJECTS: Record<string, { name: string; topics: string }> = {
  MAE101: {
    name: "Toán cho kỹ thuật",
    topics: "Giới hạn · Đạo hàm · Tích phân · Đại số tuyến tính",
  },
  MAD101: {
    name: "Toán rời rạc",
    topics: "Logic · Tổ hợp · Truy hồi · Đồ thị",
  },
  MAI391: {
    name: "Toán cho học máy",
    topics: "Ma trận · Trị riêng · Chéo hoá · Chuẩn vector",
  },
  MAS291: {
    name: "Xác suất và thống kê",
    topics: "Xác suất · Phân phối · Ước lượng · Kiểm định",
  },
};

type Health = { subjects: Record<string, { items: number; skills: number }> };

export default function HomePage() {
  const router = useRouter();
  const [subjects, setSubjects] = useState<string[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [userId, setUserId] = useState("");
  const [subject, setSubject] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [down, setDown] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    Promise.all([api.subjects(), api.health() as Promise<unknown>])
      .then(([list, info]) => {
        setSubjects(list);
        setHealth(info as Health);
        setSubject((current) => current || list[0] || "");
        setDown(false);
      })
      .catch(() => setDown(true));

    const saved = loadSession();
    if (saved) {
      setUserId(saved.userId);
      setSubject(saved.subject);
    }
  }, []);

  async function start(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const session = await api.startSession(userId.trim(), subject);
      saveSession({
        sessionId: session.session_id,
        userId: session.user_id,
        subject: session.subject,
      });
      router.push("/practice");
    } catch (exc) {
      setError((exc as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const ready = Boolean(subject) && userId.trim().length >= 2;

  return (
    <main>
      <h1>Bắt đầu luyện tập</h1>
      <p className="lead">
        Bài làm được chấm bằng kiểm chứng ký hiệu — SymPy, NetworkX, Monte Carlo — chứ
        không phải bằng cách hỏi mô hình ngôn ngữ. Gợi ý cho dần theo bậc và không nói
        đáp án trước mức 4.
      </p>

      {down && <ApiDownBanner />}

      <form onSubmit={start}>
        <h2 style={{ marginTop: 0 }}>1. Chọn môn</h2>
        <div className="cards">
          {subjects.map((code) => {
            const info = SUBJECTS[code] ?? { name: code, topics: "" };
            const stat = health?.subjects?.[code];
            return (
              <button
                type="button"
                key={code}
                className="card"
                aria-pressed={subject === code}
                onClick={() => setSubject(code)}
              >
                <span className="code">
                  {code}
                  {subject === code && <span className="chip accent">đang chọn</span>}
                </span>
                <div className="desc">{info.name}</div>
                <div className="meta">{info.topics}</div>
                {stat && (
                  <div className="meta" style={{ marginTop: 8 }}>
                    {stat.items.toLocaleString("vi-VN")} đề · {stat.skills} kỹ năng
                  </div>
                )}
              </button>
            );
          })}
          {subjects.length === 0 && !down && (
            <>
              <div className="card"><div className="skeleton tall w40" /><div className="skeleton" /><div className="skeleton w60" /></div>
              <div className="card"><div className="skeleton tall w40" /><div className="skeleton" /><div className="skeleton w60" /></div>
            </>
          )}
        </div>

        <h2>2. Cho hệ thống biết em là ai</h2>
        <div className="panel">
          <label htmlFor="user">Tên hoặc mã sinh viên</label>
          <input
            id="user"
            type="text"
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            placeholder="ví dụ: SE170001"
            required
            minLength={2}
            autoComplete="off"
          />
          <p className="meta" style={{ marginTop: 8 }}>
            Không cần mật khẩu. Chuỗi này chỉ để nối các lượt làm bài của cùng một người
            lại với nhau, nhờ đó mô hình năng lực mới theo dõi được tiến bộ.
          </p>

          <div className="row" style={{ marginTop: 18 }}>
            <button type="submit" disabled={busy || !ready}>
              {busy && <span className="spin" aria-hidden="true" />}
              {busy ? "Đang tạo phiên…" : "Vào luyện tập"}
            </button>
            <span className="meta">
              Buổi đầu có vài câu đo đầu vào để hệ thống ước lượng trình độ.
            </span>
          </div>

          {error && <p className="error">{error}</p>}
        </div>
      </form>
    </main>
  );
}
